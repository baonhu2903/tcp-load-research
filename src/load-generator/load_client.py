import argparse
import csv
import gzip
import json
import math
import os
import platform
import socket
import sys
import threading
import time

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "common"))
import protocol

# Mỗi Client ghi kết quả vào một ô riêng trong list này (theo chỉ số), nên
# các thread không ghi đè lên nhau, không cần khoá.
ket_qua_cac_client = []


def chay_mot_client(so_thu_tu, args, payload, luc_bat_dau_do, luc_dung):
    """Vòng đời của MỘT Client. Hàm này chạy trong một thread riêng."""
    client_id = so_thu_tu + 1
    cac_dong = []
    so_lan_ket_noi = 0
    cac_loi = {}
    sock = None
    seq = 0

    while time.time() < luc_dung:
        if sock is None:
            if so_lan_ket_noi > args.reconnect:
                break
            try:
                sock = socket.create_connection(
                    (args.host, args.port), timeout=args.timeout
                )
                sock.settimeout(args.timeout)
                protocol.bat_tcp_nodelay(sock)
                so_lan_ket_noi += 1
            except OSError:
                cac_loi["khong_ket_noi_duoc"] = \
                    cac_loi.get("khong_ket_noi_duoc", 0) + 1
                time.sleep(0.05)
                continue

        seq += 1
        request_id = client_id * 10_000_000 + seq
        luc_gui = time.time()
        dang_do = luc_gui >= luc_bat_dau_do

        t0 = time.perf_counter_ns()
        trang_thai = "ok"

        try:
            protocol.gui_message(sock, request_id, payload)
            tra_loi = protocol.nhan_message(sock)

            if tra_loi is None:
                trang_thai = "server_dong_ket_noi"
            elif tra_loi[0] != request_id:
                trang_thai = "sai_request_id"
            elif tra_loi[1] != payload:
                trang_thai = "sai_payload"

        except socket.timeout:
            trang_thai = "timeout"
        except protocol.LoiGiaoThuc:
            trang_thai = "du_lieu_hong"
        except OSError:
            trang_thai = "mat_ket_noi"

        do_tre_us = (time.perf_counter_ns() - t0) / 1000.0

        if dang_do:
            cac_dong.append((
                client_id,
                request_id,
                "%.6f" % luc_gui,
                "%.1f" % do_tre_us,
                trang_thai
            ))

        if trang_thai != "ok":
            cac_loi[trang_thai] = cac_loi.get(trang_thai, 0) + 1

            try:
                sock.close()
            except OSError:
                pass

            sock = None

    if sock is not None:
        try:
            sock.close()
        except OSError:
            pass

    ket_qua_cac_client[so_thu_tu] = {
        "client_id": client_id,
        "cac_dong": cac_dong,
        "so_lan_ket_noi": so_lan_ket_noi,
        "cac_loi": cac_loi,
    }


def phan_vi(danh_sach_da_sap_xep, p):
    """Tính percentile kiểu nearest-rank (không nội suy)."""
    n = len(danh_sach_da_sap_xep)

    if n == 0:
        return float("nan")

    vi_tri = math.ceil(p / 100.0 * n) - 1

    return danh_sach_da_sap_xep[
        min(max(vi_tri, 0), n - 1)
    ]


def main():
    parser = argparse.ArgumentParser(description="Load generator")

    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)

    parser.add_argument(
        "--clients",
        type=int,
        default=1,
        help="so Client dong thoi"
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=20.0,
        help="giay: thoi gian DO chinh thuc"
    )

    parser.add_argument(
        "--warmup",
        type=float,
        default=5.0,
        help="giay: chay truoc, khong ghi so lieu"
    )

    parser.add_argument(
        "--payload-size",
        type=int,
        default=1024,
        help="byte: kich thuoc payload co dinh"
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="giay: timeout cho moi request"
    )

    parser.add_argument(
        "--reconnect",
        type=int,
        default=5,
        help="so lan ket noi lai toi da khi gap loi"
    )

    parser.add_argument(
        "--out-dir",
        default="experiments/raw-data"
    )

    parser.add_argument("--run-id", help="ten lan chay")

    args = parser.parse_args()

    run_id = args.run_id or "c%d_%s" % (
        args.clients,
        time.strftime("%Y%m%d-%H%M%S")
    )

    payload = protocol.tao_payload(args.payload_size)

    os.makedirs(args.out_dir, exist_ok=True)

    luc_bat_dau_do = time.time() + 1.0 + args.warmup
    luc_dung = luc_bat_dau_do + args.duration

    print(
        "[load] run_id=%s clients=%d warmup=%.0fs do=%.0fs payload=%dB"
        % (
            run_id,
            args.clients,
            args.warmup,
            args.duration,
            args.payload_size
        )
    )

    global ket_qua_cac_client
    ket_qua_cac_client = [None] * args.clients

    cac_thread = []

    for i in range(args.clients):
        t = threading.Thread(
            target=chay_mot_client,
            args=(i, args, payload, luc_bat_dau_do, luc_dung)
        )

        t.start()
        cac_thread.append(t)

    for t in cac_thread:
        t.join()

    tat_ca_dong = []
    tong_loi = {}

    for kq in ket_qua_cac_client:
        tat_ca_dong.extend(kq["cac_dong"])

        for ly_do, so in kq["cac_loi"].items():
            tong_loi[ly_do] = tong_loi.get(ly_do, 0) + so

    do_tre_ok = sorted(
        float(dong[3])
        for dong in tat_ca_dong
        if dong[4] == "ok"
    )

    so_ok = len(do_tre_ok)
    so_loi = len(tat_ca_dong) - so_ok

    trung_binh = (
        sum(do_tre_ok) / so_ok
        if so_ok
        else float("nan")
    )

    ten_file_tho = "%s_requests.csv.gz" % run_id

    with gzip.open(
        os.path.join(args.out_dir, ten_file_tho),
        "wt",
        newline="",
        encoding="utf-8"
    ) as f:
        writer = csv.writer(f)

        writer.writerow([
            "client_id",
            "request_id",
            "luc_gui_unix",
            "do_tre_us",
            "trang_thai"
        ])

        writer.writerows(tat_ca_dong)

    tong_hop = {
        "run_id": run_id,
        "clients": args.clients,
        "payload_size": args.payload_size,
        "warmup_seconds": args.warmup,
        "measure_seconds": args.duration,
        "measure_start_unix": luc_bat_dau_do,
        "measure_end_unix": luc_dung,
        "requests_ok": so_ok,
        "requests_error": so_loi,
        "error_rate": (
            so_loi / len(tat_ca_dong)
            if tat_ca_dong
            else 0.0
        ),
        "throughput_rps": so_ok / args.duration,
        "latency_us": {
            "avg": trung_binh,
            "min": do_tre_ok[0] if so_ok else float("nan"),
            "p50": phan_vi(do_tre_ok, 50),
            "p95": phan_vi(do_tre_ok, 95),
            "p99": phan_vi(do_tre_ok, 99),
            "max": do_tre_ok[-1] if so_ok else float("nan"),
        },
        "errors_by_reason": tong_loi,
        "raw_file": ten_file_tho,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count_logical": os.cpu_count(),
        },
    }

    with open(
        os.path.join(args.out_dir, "%s_summary.json" % run_id),
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(tong_hop, f, ensure_ascii=False, indent=2)

    print(
        "[load] ok=%d loi=%d error_rate=%.4f%% throughput=%.1f req/s"
        % (
            so_ok,
            so_loi,
            tong_hop["error_rate"] * 100,
            tong_hop["throughput_rps"]
        )
    )

    print(
        "[load] latency: TB=%.3f ms  p95=%.3f ms  p99=%.3f ms  max=%.3f ms"
        % (
            trung_binh / 1000,
            phan_vi(do_tre_ok, 95) / 1000,
            phan_vi(do_tre_ok, 99) / 1000,
            (do_tre_ok[-1] if so_ok else float("nan")) / 1000
        )
    )

    if tong_loi:
        print("[load] cac loi:", tong_loi)


if __name__ == "__main__":
    main()