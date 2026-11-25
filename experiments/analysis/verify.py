"""Kiểm chứng lại kết quả MỘT CÁCH ĐỘC LẬP với load generator.

Đề bài yêu cầu: "dùng một script hoặc bảng tính riêng để kiểm tra lại ít nhất
ba trường hợp về số request thành công, throughput hoặc error rate".

Script này KHÔNG tin vào file *_summary.json. Nó mở lại DỮ LIỆU THÔ
(*_requests.csv.gz, mỗi request một dòng) và tự tính lại từ đầu 6 chỉ số:

    C1. số request thành công = số dòng có trang_thai == "ok"
    C2. throughput            = số request ok / thời gian đo
    C3. error rate            = số dòng lỗi / tổng số dòng
    C4. số request lỗi
    C5. latency trung bình    = trung bình cột do_tre_us
    C6. p95 latency           = nearest-rank trên cột do_tre_us đã sắp xếp
    C7. mọi request_id phải DUY NHẤT (không trùng, không mất)

Rồi so với số trong summary. Lệch quá ngưỡng -> FAIL.

Chạy:
    python experiments/analysis/verify.py --data-dir experiments/raw-data/baseline-1kb
"""

import argparse
import csv
import glob
import gzip
import json
import math
import os

NGUONG = 1e-6          # sai số tương đối cho phép (chỉ do làm tròn khi ghi file)
NGUONG_LATENCY = 2e-3  # latency ghi ra file làm tròn 0.1us -> nới lỏng hơn


def phan_vi(danh_sach_da_sap_xep, p):
    """Phải GIỐNG HỆT công thức trong load_client.py thì mới so sánh được."""
    n = len(danh_sach_da_sap_xep)
    if n == 0:
        return float("nan")
    vi_tri = math.ceil(p / 100.0 * n) - 1
    return danh_sach_da_sap_xep[min(max(vi_tri, 0), n - 1)]


def gan_bang(a, b, nguong):
    if math.isnan(a) and math.isnan(b):
        return True
    thang = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / thang <= nguong


class BangKiemTra:
    def __init__(self):
        self.cac_dong = []
        self.so_dat = 0
        self.so_truot = 0

    def so_sanh(self, run_id, ten, tinh_lai, trong_summary, nguong):
        if isinstance(tinh_lai, float) or isinstance(trong_summary, float):
            dat = gan_bang(float(tinh_lai), float(trong_summary), nguong)
        else:
            dat = tinh_lai == trong_summary
        self.ghi(run_id, ten, tinh_lai, trong_summary, dat)

    def ghi(self, run_id, ten, tinh_lai, trong_summary, dat):
        self.cac_dong.append((run_id, ten, tinh_lai, trong_summary, dat))
        if dat:
            self.so_dat += 1
        else:
            self.so_truot += 1


def kiem_tra_mot_lan_chay(thu_muc, duong_dan_summary, bang):
    with open(duong_dan_summary, encoding="utf-8") as f:
        s = json.load(f)
    run_id = s["run_id"]
    cua_so_do = s["measure_seconds"]

    duong_dan_tho = os.path.join(thu_muc, s["raw_file"])
    if not os.path.exists(duong_dan_tho):
        print("  %s: KHONG tim thay file du lieu tho -> bo qua" % run_id)
        return

    # --- Đọc lại toàn bộ dữ liệu thô và tự tính ---
    tong_dong = 0
    do_tre_ok = []
    cac_id = set()
    so_trung = 0
    thong_ke_trang_thai = {}

    mo = gzip.open if duong_dan_tho.endswith(".gz") else open
    with mo(duong_dan_tho, "rt", encoding="utf-8") as f:
        for dong in csv.DictReader(f):
            tong_dong += 1
            trang_thai = dong["trang_thai"]
            thong_ke_trang_thai[trang_thai] = \
                thong_ke_trang_thai.get(trang_thai, 0) + 1

            request_id = int(dong["request_id"])
            if request_id in cac_id:
                so_trung += 1
            else:
                cac_id.add(request_id)

            if trang_thai == "ok":
                do_tre_ok.append(float(dong["do_tre_us"]))

    do_tre_ok.sort()
    so_ok = len(do_tre_ok)
    so_loi = tong_dong - so_ok

    bang.so_sanh(run_id, "C1 so request thanh cong", so_ok, s["requests_ok"], 0)
    bang.so_sanh(run_id, "C2 throughput (req/s)", so_ok / cua_so_do,
                 s["throughput_rps"], NGUONG)
    bang.so_sanh(run_id, "C3 error rate",
                 so_loi / tong_dong if tong_dong else 0.0,
                 s["error_rate"], NGUONG)
    bang.so_sanh(run_id, "C4 so request loi", so_loi, s["requests_error"], 0)
    bang.so_sanh(run_id, "C5 latency trung binh (us)",
                 sum(do_tre_ok) / so_ok if so_ok else float("nan"),
                 s["latency_us"]["avg"], NGUONG_LATENCY)
    bang.so_sanh(run_id, "C6 p95 latency (us)", phan_vi(do_tre_ok, 95),
                 s["latency_us"]["p95"], NGUONG_LATENCY)
    bang.ghi(run_id, "C7 request_id duy nhat (so bi trung: %d)" % so_trung,
             so_trung, 0, so_trung == 0)

    print("  %s: %d dong | ok=%d loi=%d | %s"
          % (run_id, tong_dong, so_ok, so_loi,
             ", ".join("%s=%d" % kv
                       for kv in sorted(thong_ke_trang_thai.items()))))


def main():
    thu_muc_goc = os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    parser = argparse.ArgumentParser(
        description="Kiem chung doc lap tu du lieu tho")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--runs", help="chi kiem tra cac run_id nay, "
                                       "vi du: c1_r1,c50_r2")
    parser.add_argument("--report",
                        default=os.path.join(thu_muc_goc, "experiments",
                                             "analysis", "verification.csv"))
    args = parser.parse_args()

    cac_file = sorted(glob.glob(os.path.join(args.data_dir,
                                             "*_summary.json")))
    if args.runs:
        can_kiem = set(args.runs.split(","))
        cac_file = [p for p in cac_file
                    if os.path.basename(p).replace("_summary.json", "")
                    in can_kiem]
    if not cac_file:
        print("[verify] khong tim thay lan chay nao trong %s" % args.data_dir)
        return 1

    print("[verify] kiem chung %d lan chay trong %s"
          % (len(cac_file), args.data_dir))
    bang = BangKiemTra()
    for duong_dan in cac_file:
        kiem_tra_mot_lan_chay(args.data_dir, duong_dan, bang)

    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["run_id", "kiem_tra", "tinh_lai_tu_du_lieu_tho",
                    "trong_summary", "ket_qua"])
        for run_id, ten, a, b, dat in bang.cac_dong:
            w.writerow([run_id, ten, a, b, "DAT" if dat else "TRUOT"])

    print("[verify] %d DAT, %d TRUOT -> %s"
          % (bang.so_dat, bang.so_truot, args.report))
    if bang.so_truot:
        print("[verify] CAC KIEM TRA THAT BAI:")
        for run_id, ten, a, b, dat in bang.cac_dong:
            if not dat:
                print("  %s | %s | tu du lieu tho=%s | summary=%s"
                      % (run_id, ten, a, b))
        return 2
    print("[verify] TAT CA DAT: so lieu bao cao khop voi du lieu tho.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
