"""Tổng hợp kết quả tất cả các lần chạy và vẽ biểu đồ.

Đầu vào: thư mục raw-data của một cấu hình.
Đầu ra:
    analysis/aggregate.csv        - mỗi lần chạy một dòng
    analysis/summary_by_level.csv - mỗi mức Client một dòng (trung bình ± độ lệch chuẩn)
    analysis/summary.md           - bảng markdown dán thẳng vào báo cáo
    figures/fig1..fig4.png

Chạy:
    python experiments/analysis/analyze.py --data-dir experiments/raw-data/baseline-1kb
"""

import argparse
import csv
import glob
import gzip
import json
import math
import os
import statistics

try:
    import matplotlib
    matplotlib.use("Agg")          # không cần màn hình, chỉ ghi file PNG
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

THU_MUC_GOC = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))


def doc_cpu(duong_dan, tu_luc, den_luc):
    """Trung bình/đỉnh CPU của Server, CHỈ tính các mẫu trong cửa sổ đo."""
    if not os.path.exists(duong_dan):
        return {}
    cpu, chuan_hoa, threads, rss = [], [], [], []
    with open(duong_dan, encoding="utf-8") as f:
        for dong in csv.DictReader(f):
            ts = float(dong["ts_unix"])
            if tu_luc <= ts <= den_luc:
                cpu.append(float(dong["cpu_percent"]))
                chuan_hoa.append(float(dong["cpu_percent_norm"]))
                threads.append(int(dong["num_threads"]))
                rss.append(float(dong["rss_mb"]))
    if not cpu:
        return {}
    return {
        "cpu_percent_avg": statistics.fmean(cpu),
        "cpu_percent_max": max(cpu),
        "cpu_norm_avg": statistics.fmean(chuan_hoa),
        "cpu_samples": len(cpu),
        "server_threads_max": max(threads),
        "server_rss_mb_max": max(rss),
    }


def doc_cac_lan_chay(thu_muc):
    """Đọc mọi file *_summary.json và ghép thêm số liệu CPU."""
    ket_qua = []
    for duong_dan in sorted(glob.glob(os.path.join(thu_muc,
                                                   "*_summary.json"))):
        with open(duong_dan, encoding="utf-8") as f:
            s = json.load(f)
        run_id = s["run_id"]
        dong = {
            "run_id": run_id,
            "clients": s["clients"],
            "repetition": int(run_id.split("_r")[-1]) if "_r" in run_id else 1,
            "payload_size": s["payload_size"],
            "measure_seconds": s["measure_seconds"],
            "requests_ok": s["requests_ok"],
            "requests_error": s["requests_error"],
            "error_rate": s["error_rate"],
            "throughput_rps": s["throughput_rps"],
            "latency_avg_ms": s["latency_us"]["avg"] / 1000.0,
            "latency_p50_ms": s["latency_us"]["p50"] / 1000.0,
            "latency_p95_ms": s["latency_us"]["p95"] / 1000.0,
            "latency_p99_ms": s["latency_us"]["p99"] / 1000.0,
            "latency_max_ms": s["latency_us"]["max"] / 1000.0,
            "raw_file": s["raw_file"],
        }
        dong.update(doc_cpu(
            os.path.join(thu_muc, "%s_server_cpu.csv" % run_id),
            s["measure_start_unix"], s["measure_end_unix"]))
        ket_qua.append(dong)
    ket_qua.sort(key=lambda d: (d["clients"], d["repetition"]))
    return ket_qua


COT_AGGREGATE = [
    "run_id", "clients", "repetition", "payload_size", "measure_seconds",
    "requests_ok", "requests_error", "error_rate", "throughput_rps",
    "latency_avg_ms", "latency_p50_ms", "latency_p95_ms", "latency_p99_ms",
    "latency_max_ms", "cpu_percent_avg", "cpu_percent_max", "cpu_norm_avg",
    "cpu_samples", "server_threads_max", "server_rss_mb_max",
]

CHI_SO_GOP = ["latency_avg_ms", "latency_p95_ms", "latency_p99_ms",
              "throughput_rps", "error_rate", "cpu_percent_avg",
              "cpu_norm_avg"]


def trung_binh_va_do_lech(cac_gia_tri):
    cac_gia_tri = [v for v in cac_gia_tri
                   if v is not None and not math.isnan(v)]
    if not cac_gia_tri:
        return float("nan"), float("nan")
    tb = statistics.fmean(cac_gia_tri)
    sd = statistics.stdev(cac_gia_tri) if len(cac_gia_tri) > 1 else 0.0
    return tb, sd


def gop_theo_muc(cac_lan):
    """Gộp các lần lặp của cùng một mức Client.

    Phải có độ lệch chuẩn: đề bài yêu cầu giải thích độ dao động, không được
    chỉ đưa giá trị trung bình.
    """
    cac_muc = sorted({d["clients"] for d in cac_lan})
    ket_qua = []
    for muc in cac_muc:
        nhom = [d for d in cac_lan if d["clients"] == muc]
        dong = {"clients": muc, "runs": len(nhom)}
        for chi_so in CHI_SO_GOP:
            tb, sd = trung_binh_va_do_lech([d.get(chi_so) for d in nhom])
            dong[chi_so + "_mean"] = tb
            dong[chi_so + "_sd"] = sd
            dong[chi_so + "_cv_pct"] = (sd / tb * 100) if tb else float("nan")
        dong["requests_ok_total"] = sum(d["requests_ok"] for d in nhom)
        dong["requests_error_total"] = sum(d["requests_error"] for d in nhom)
        ket_qua.append(dong)
    return ket_qua


def ghi_markdown(duong_dan, cac_muc, cac_lan, thu_muc_data):
    d = []
    d.append("# Ket qua thuc nghiem: %s\n" % os.path.basename(thu_muc_data))

    file_env = os.path.join(thu_muc_data, "environment.json")
    if os.path.exists(file_env):
        with open(file_env, encoding="utf-8") as f:
            env = json.load(f)
        cfg = env.get("config", {})
        ld = cfg.get("load", {})
        d.append("- May: `%s`" % env.get("platform", "?"))
        d.append("- CPU logic: %s" % env.get("cpu_count_logical", "?"))
        d.append("- Python: %s" % env.get("python", "?"))
        d.append("- Payload: %s B, warm-up %ss, do %ss, %s lan lap/muc"
                 % (ld.get("payload_size"), ld.get("warmup"),
                    ld.get("duration"), cfg.get("repetitions")))
        d.append("- Mo hinh Server: blocking socket + moi ket noi mot thread")
        d.append("")

    d.append("## Bang 1. Tong hop theo muc Client (trung binh +/- do lech chuan)\n")
    d.append("| Client | Lan chay | Latency TB (ms) | p95 (ms) | p99 (ms) "
             "| Throughput (req/s) | CPU server (%) | Error rate |")
    d.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for m in cac_muc:
        d.append("| %d | %d | %.3f ± %.3f | %.3f ± %.3f | %.3f ± %.3f "
                 "| %.0f ± %.0f | %.1f ± %.1f | %.4f%% |"
                 % (m["clients"], m["runs"],
                    m["latency_avg_ms_mean"], m["latency_avg_ms_sd"],
                    m["latency_p95_ms_mean"], m["latency_p95_ms_sd"],
                    m["latency_p99_ms_mean"], m["latency_p99_ms_sd"],
                    m["throughput_rps_mean"], m["throughput_rps_sd"],
                    m["cpu_percent_avg_mean"], m["cpu_percent_avg_sd"],
                    m["error_rate_mean"] * 100))
    d.append("")
    d.append("> CPU (%) la % tren MOT core (cach tinh cua psutil): 200% = 2 "
             "core chay het suc. Cot cpu_norm_avg trong aggregate.csv la % so "
             "voi toan bo may.\n")

    if len(cac_muc) > 1:
        goc = cac_muc[0]
        d.append("## Bang 2. Muc tang so voi %d Client\n" % goc["clients"])
        d.append("| Client | Latency TB | p95 | Throughput | CPU |")
        d.append("|---:|---:|---:|---:|---:|")
        for m in cac_muc:
            def ti_le(ten):
                return m[ten] / goc[ten] if goc[ten] else float("nan")
            d.append("| %d | %.2fx | %.2fx | %.2fx | %.2fx |"
                     % (m["clients"], ti_le("latency_avg_ms_mean"),
                        ti_le("latency_p95_ms_mean"),
                        ti_le("throughput_rps_mean"),
                        ti_le("cpu_percent_avg_mean")))
        d.append("")

    d.append("## Bang 3. Chi tiet tung lan chay\n")
    d.append("| run_id | Client | Lan | OK | Loi | Latency TB (ms) | p95 (ms) "
             "| req/s | CPU (%) |")
    d.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in cac_lan:
        d.append("| %s | %d | %d | %d | %d | %.3f | %.3f | %.0f | %.1f |"
                 % (r["run_id"], r["clients"], r["repetition"],
                    r["requests_ok"], r["requests_error"],
                    r["latency_avg_ms"], r["latency_p95_ms"],
                    r["throughput_rps"],
                    r.get("cpu_percent_avg", float("nan"))))
    d.append("")

    with open(duong_dan, "w", encoding="utf-8") as f:
        f.write("\n".join(d))


def doc_do_tre_tu_file_tho(duong_dan):
    """Đọc cột độ trễ của các request thành công từ file dữ liệu thô."""
    mo = gzip.open if duong_dan.endswith(".gz") else open
    gia_tri = []
    with mo(duong_dan, "rt", encoding="utf-8") as f:
        for dong in csv.DictReader(f):
            if dong["trang_thai"] == "ok":
                gia_tri.append(float(dong["do_tre_us"]) / 1000.0)   # ms
    gia_tri.sort()
    return gia_tri


def ve_bieu_do(cac_muc, cac_lan, thu_muc_data, thu_muc_hinh):
    if plt is None:
        print("[analyze] CANH BAO: chua cai matplotlib -> bo qua buoc ve "
              "bieu do. Cai bang: python -m pip install matplotlib")
        return []
    os.makedirs(thu_muc_hinh, exist_ok=True)
    da_ve = []
    vi_tri = range(len(cac_muc))
    nhan = [str(m["clients"]) for m in cac_muc]

    # Hình 1: latency trung bình và p95
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.errorbar(vi_tri, [m["latency_avg_ms_mean"] for m in cac_muc],
                yerr=[m["latency_avg_ms_sd"] for m in cac_muc],
                marker="o", capsize=4, label="Latency trung binh")
    ax.errorbar(vi_tri, [m["latency_p95_ms_mean"] for m in cac_muc],
                yerr=[m["latency_p95_ms_sd"] for m in cac_muc],
                marker="s", capsize=4, label="p95 latency")
    ax.set_xticks(list(vi_tri), nhan)
    ax.set_xlabel("So Client dong thoi")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Hinh 1. Latency theo so Client dong thoi")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    duong_dan = os.path.join(thu_muc_hinh, "fig1_latency_vs_clients.png")
    fig.savefig(duong_dan, dpi=150)
    plt.close(fig)
    da_ve.append(duong_dan)

    # Hình 2: throughput
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.errorbar(vi_tri, [m["throughput_rps_mean"] for m in cac_muc],
                yerr=[m["throughput_rps_sd"] for m in cac_muc],
                marker="o", capsize=4, color="tab:green")
    for i, m in enumerate(cac_muc):
        ax.annotate("%.0f" % m["throughput_rps_mean"],
                    (i, m["throughput_rps_mean"]),
                    textcoords="offset points", xytext=(9, 4), ha="left",
                    fontsize=8)
    ax.set_xticks(list(vi_tri), nhan)
    ax.set_xlabel("So Client dong thoi")
    ax.set_ylabel("Throughput (request/giay)")
    ax.set_title("Hinh 2. Throughput theo so Client dong thoi")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    duong_dan = os.path.join(thu_muc_hinh, "fig2_throughput_vs_clients.png")
    fig.savefig(duong_dan, dpi=150)
    plt.close(fig)
    da_ve.append(duong_dan)

    # Hình 3: CPU
    if not math.isnan(cac_muc[0]["cpu_percent_avg_mean"]):
        fig, ax = plt.subplots(figsize=(7, 4.5))
        ax.errorbar(vi_tri, [m["cpu_percent_avg_mean"] for m in cac_muc],
                    yerr=[m["cpu_percent_avg_sd"] for m in cac_muc],
                    marker="o", capsize=4, color="tab:red",
                    label="CPU Server (% tren 1 core)")
        ax.errorbar(vi_tri, [m["cpu_norm_avg_mean"] for m in cac_muc],
                    yerr=[m["cpu_norm_avg_sd"] for m in cac_muc],
                    marker="^", capsize=4, color="tab:orange",
                    label="CPU (% tren toan may)")
        ax.set_xticks(list(vi_tri), nhan)
        ax.set_xlabel("So Client dong thoi")
        ax.set_ylabel("CPU (%)")
        ax.set_title("Hinh 3. Muc su dung CPU cua Server")
        ax.grid(alpha=0.3)
        ax.legend()
        fig.tight_layout()
        duong_dan = os.path.join(thu_muc_hinh, "fig3_cpu_vs_clients.png")
        fig.savefig(duong_dan, dpi=150)
        plt.close(fig)
        da_ve.append(duong_dan)

    # Hình 4: phân bố latency (CDF), lấy lần chạy đầu tiên của mỗi mức
    fig, ax = plt.subplots(figsize=(7, 4.5))
    so_duong = 0
    for muc in sorted({r["clients"] for r in cac_lan}):
        lan_dau = next(r for r in cac_lan if r["clients"] == muc)
        duong_dan_tho = os.path.join(thu_muc_data, lan_dau["raw_file"])
        if not os.path.exists(duong_dan_tho):
            continue
        do_tre = doc_do_tre_tu_file_tho(duong_dan_tho)
        if not do_tre:
            continue
        # Vẽ tối đa 2000 điểm cho nhẹ file ảnh
        n = len(do_tre)
        buoc = max(1, n // 2000)
        x = do_tre[::buoc]
        y = [(i * buoc + 1) / n * 100 for i in range(len(x))]
        ax.plot(x, y, label="%d client" % muc)
        so_duong += 1
    if so_duong:
        ax.set_xscale("log")
        ax.set_xlabel("Latency (ms, truc log)")
        ax.set_ylabel("Ty le request <= gia tri (%)")
        ax.set_title("Hinh 4. Phan bo latency (CDF)")
        ax.axhline(95, ls="--", lw=0.8, color="gray")
        ax.grid(alpha=0.3, which="both")
        ax.legend()
        fig.tight_layout()
        duong_dan = os.path.join(thu_muc_hinh, "fig4_latency_cdf.png")
        fig.savefig(duong_dan, dpi=150)
        da_ve.append(duong_dan)
    plt.close(fig)
    return da_ve


def main():
    parser = argparse.ArgumentParser(description="Tong hop + ve bieu do")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out-dir",
                        default=os.path.join(THU_MUC_GOC, "experiments",
                                             "analysis"))
    parser.add_argument("--fig-dir",
                        default=os.path.join(THU_MUC_GOC, "experiments",
                                             "figures"))
    args = parser.parse_args()

    cac_lan = doc_cac_lan_chay(args.data_dir)
    if not cac_lan:
        print("[analyze] khong tim thay file *_summary.json trong %s"
              % args.data_dir)
        return 1
    cac_muc = gop_theo_muc(cac_lan)
    os.makedirs(args.out_dir, exist_ok=True)

    with open(os.path.join(args.out_dir, "aggregate.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COT_AGGREGATE, extrasaction="ignore")
        w.writeheader()
        w.writerows(cac_lan)

    with open(os.path.join(args.out_dir, "summary_by_level.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cac_muc[0].keys()))
        w.writeheader()
        w.writerows(cac_muc)

    ghi_markdown(os.path.join(args.out_dir, "summary.md"), cac_muc, cac_lan,
                 args.data_dir)
    cac_hinh = ve_bieu_do(cac_muc, cac_lan, args.data_dir, args.fig_dir)

    print("[analyze] %d lan chay, %d muc Client" % (len(cac_lan), len(cac_muc)))
    for m in cac_muc:
        print("  %3d client: latency TB %.3f ms | p95 %.3f ms | %.0f req/s "
              "| CPU %.1f%% | loi %.4f%%"
              % (m["clients"], m["latency_avg_ms_mean"],
                 m["latency_p95_ms_mean"], m["throughput_rps_mean"],
                 m["cpu_percent_avg_mean"], m["error_rate_mean"] * 100))
    for ten in ["aggregate.csv", "summary_by_level.csv", "summary.md"]:
        print("[analyze] da ghi: %s" % os.path.join(args.out_dir, ten))
    for h in cac_hinh:
        print("[analyze] da ve : %s" % h)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
