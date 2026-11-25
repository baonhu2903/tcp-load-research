"""Chạy toàn bộ bộ thí nghiệm theo file cấu hình JSON.

Với mỗi mức Client và mỗi lần lặp, script làm 4 việc:
    1. Bật Server ở MỘT TIẾN TRÌNH RIÊNG (đề bài bắt buộc).
    2. Chờ tới khi kết nối được vào Server.
    3. Bật thread đo CPU của tiến trình Server đó (bằng psutil).
    4. Chạy load generator ở tiến trình riêng, xong thì tắt Server.

Chạy:
    python run_experiments.py --config experiments/configs/baseline-1kb.json
"""

import argparse
import csv
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time

try:
    import psutil
except ImportError:
    psutil = None

THU_MUC_GOC = os.path.dirname(os.path.abspath(__file__))
FILE_SERVER = os.path.join(THU_MUC_GOC, "src", "server", "tcp_server.py")
FILE_LOADGEN = os.path.join(THU_MUC_GOC, "src", "load-generator",
                            "load_client.py")


def cho_server_san_sang(host, port, so_giay=20):
    """Thử kết nối liên tục cho tới khi Server chịu nhận (hoặc hết giờ)."""
    het_han = time.time() + so_giay
    while time.time() < het_han:
        try:
            s = socket.create_connection((host, port), timeout=1)
            s.close()
            return True
        except OSError:
            time.sleep(0.1)
    return False


class DoCpuServer(threading.Thread):
    """Đo CPU/RAM của tiến trình Server từ BÊN NGOÀI, ghi ra file CSV.

    Đo từ bên ngoài nên file tcp_server.py không cần dính dáng gì tới psutil.
    Lưu ý đơn vị: psutil tính % trên MỘT core, nên 200% = 2 core chạy hết sức.
    Cột cpu_percent_norm là % so với toàn bộ máy.
    """

    def __init__(self, pid, duong_dan, chu_ky=0.5):
        super().__init__(daemon=True)
        self.pid = pid
        self.duong_dan = duong_dan
        self.chu_ky = chu_ky
        self.co_dung = threading.Event()
        self.so_core = os.cpu_count() or 1

    def dung(self):
        self.co_dung.set()

    def run(self):
        if psutil is None:
            print("[exp] CANH BAO: chua cai psutil -> khong do duoc CPU")
            return
        try:
            proc = psutil.Process(self.pid)
            proc.cpu_percent(None)      # lần gọi đầu luôn trả 0, bỏ đi
        except psutil.Error:
            return
        with open(self.duong_dan, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ts_unix", "cpu_percent", "cpu_percent_norm",
                             "n_cpu", "rss_mb", "num_threads"])
            while not self.co_dung.wait(self.chu_ky):
                try:
                    cpu = proc.cpu_percent(None)
                    rss = proc.memory_info().rss / (1024 * 1024)
                    so_thread = proc.num_threads()
                except psutil.Error:
                    break               # Server đã tắt
                writer.writerow(["%.3f" % time.time(), "%.2f" % cpu,
                                 "%.2f" % (cpu / self.so_core), self.so_core,
                                 "%.2f" % rss, so_thread])
                f.flush()


def bat_server(cau_hinh, thu_muc_ra, run_id):
    sv = cau_hinh["server"]
    lenh = [
        sys.executable, "-u", FILE_SERVER,
        "--host", sv.get("host", "127.0.0.1"),
        "--port", str(sv.get("port", 5050)),
        "--backlog", str(sv.get("backlog", 512)),
        "--idle-timeout", str(sv.get("idle_timeout", 30)),
        "--stats-interval", str(sv.get("stats_interval", 0)),
    ]
    log = open(os.path.join(thu_muc_ra, "%s_server.log" % run_id),
               "w", encoding="utf-8")
    return subprocess.Popen(lenh, stdout=log, stderr=subprocess.STDOUT), log


def chay_load(cau_hinh, so_client, thu_muc_ra, run_id):
    sv = cau_hinh["server"]
    ld = cau_hinh["load"]
    lenh = [
        sys.executable, "-u", FILE_LOADGEN,
        "--host", sv.get("host", "127.0.0.1"),
        "--port", str(sv.get("port", 5050)),
        "--clients", str(so_client),
        "--duration", str(ld.get("duration", 20)),
        "--warmup", str(ld.get("warmup", 5)),
        "--payload-size", str(ld.get("payload_size", 1024)),
        "--timeout", str(ld.get("timeout", 5)),
        "--reconnect", str(ld.get("reconnect", 5)),
        "--out-dir", thu_muc_ra,
        "--run-id", run_id,
    ]
    return subprocess.call(lenh)


def main():
    parser = argparse.ArgumentParser(description="Chay bo thi nghiem")
    parser.add_argument("--config", required=True, help="file cau hinh JSON")
    parser.add_argument("--out-root", default="experiments/raw-data")
    parser.add_argument("--levels", help="ghi de so Client, vi du: 1,10,50")
    parser.add_argument("--repetitions", type=int, help="ghi de so lan lap")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cau_hinh = json.load(f)
    if args.levels:
        cau_hinh["client_levels"] = [int(x) for x in args.levels.split(",")]
    if args.repetitions:
        cau_hinh["repetitions"] = args.repetitions

    thu_muc_ra = os.path.join(args.out_root, cau_hinh["name"])
    os.makedirs(thu_muc_ra, exist_ok=True)

    cac_muc = cau_hinh["client_levels"]
    so_lan_lap = cau_hinh.get("repetitions", 3)
    nghi = cau_hinh.get("cooldown_seconds", 5)
    host = cau_hinh["server"].get("host", "127.0.0.1")
    port = cau_hinh["server"].get("port", 5050)
    tong = len(cac_muc) * so_lan_lap

    ld = cau_hinh["load"]
    uoc_tinh = tong * (ld.get("warmup", 5) + ld.get("duration", 20) + nghi + 3)
    print("[exp] '%s': %d muc Client x %d lan = %d lan chay (~%.0f phut)"
          % (cau_hinh["name"], len(cac_muc), so_lan_lap, tong, uoc_tinh / 60))

    # Ghi lại thông tin máy để đưa vào báo cáo
    with open(os.path.join(thu_muc_ra, "environment.json"), "w",
              encoding="utf-8") as f:
        json.dump({
            "config": cau_hinh,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count_logical": os.cpu_count(),
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "note": "Server va load generator chay tren CUNG mot may nen hai "
                    "tien trinh phai chia nhau CPU. Day la gioi han can neu "
                    "ro trong bao cao.",
        }, f, ensure_ascii=False, indent=2)

    bang_ke = open(os.path.join(thu_muc_ra, "runs.csv"), "w", newline="",
                   encoding="utf-8")
    writer = csv.writer(bang_ke)
    writer.writerow(["run_id", "clients", "repetition", "bat_dau_luc",
                     "ma_thoat"])

    lan = 0
    try:
        for so_client in cac_muc:
            for rep in range(1, so_lan_lap + 1):
                lan += 1
                run_id = "c%d_r%d" % (so_client, rep)
                print("[exp] (%d/%d) %s: %d client"
                      % (lan, tong, run_id, so_client))

                proc, log = bat_server(cau_hinh, thu_muc_ra, run_id)
                ma_thoat = -1
                do_cpu = None
                try:
                    if not cho_server_san_sang(host, port):
                        print("[exp]     LOI: Server khong san sang, bo qua")
                        continue
                    do_cpu = DoCpuServer(
                        proc.pid,
                        os.path.join(thu_muc_ra, "%s_server_cpu.csv" % run_id),
                        cau_hinh.get("cpu_sample_interval", 0.5))
                    do_cpu.start()
                    ma_thoat = chay_load(cau_hinh, so_client, thu_muc_ra,
                                         run_id)
                finally:
                    if do_cpu is not None:
                        do_cpu.dung()
                        do_cpu.join(timeout=3)
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    log.close()

                writer.writerow([run_id, so_client, rep,
                                 time.strftime("%Y-%m-%d %H:%M:%S"), ma_thoat])
                bang_ke.flush()
                if lan < tong:
                    time.sleep(nghi)
    except KeyboardInterrupt:
        print("[exp] bi nguoi dung ngat")
    finally:
        bang_ke.close()

    print("[exp] xong. du lieu tho nam o: %s" % thu_muc_ra)
    print("[exp] buoc tiep: python experiments/analysis/analyze.py "
          "--data-dir %s" % thu_muc_ra)


if __name__ == "__main__":
    main()
