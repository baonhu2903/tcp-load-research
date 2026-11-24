# Khảo sát ảnh hưởng của số lượng Client đồng thời đến hiệu năng TCP Server

Đồ án research — xây dựng một TCP Server đơn giản (dịch vụ **Echo Benchmark**) và đo
xem **latency, throughput, CPU** thay đổi thế nào khi số Client đồng thời tăng
(1 → 10 → 50).

**Câu hỏi research:** Khi số lượng Client đồng thời tăng, latency, throughput và mức
sử dụng CPU của TCP Server thay đổi như thế nào?

---

## 1. Yêu cầu môi trường

| Mục | Giá trị |
|---|---|
| Python | 3.10 trở lên (dự án test trên 3.13) |
| Thư viện bắt buộc | không có — Server và load generator chỉ dùng thư viện chuẩn |
| Thư viện tùy chọn | `psutil` (đo CPU của Server), `matplotlib` (vẽ biểu đồ) |

```bash
python -m pip install -r requirements.txt
```

Không cài 2 thư viện tùy chọn thì chương trình **vẫn chạy**: cột CPU sẽ trống và
bước vẽ biểu đồ bị bỏ qua (có cảnh báo trên màn hình).

---

## 2. Cấu trúc thư mục

```
tcp-load-research/
  README.md                         hướng dẫn này
  requirements.txt
  run_experiments.py                chạy toàn bộ bộ thí nghiệm theo file cấu hình
  src/
    common/protocol.py              định dạng message + tách message (framing)
    server/tcp_server.py            TCP Server (blocking socket + thread pool)
    load-generator/load_client.py   sinh tải N Client đồng thời, đo latency
  tests/
    test_protocol.py                16 test cho lớp protocol
    test_server.py                  20 test cho Server (1/nhiều Client, lỗi, timeout)
  experiments/
    configs/                        file cấu hình thí nghiệm (JSON)
    raw-data/                       dữ liệu thô sinh ra khi chạy
    analysis/analyze.py             tổng hợp + vẽ biểu đồ
    analysis/verify.py              kiểm chứng độc lập từ dữ liệu thô
    figures/                        biểu đồ PNG
  docs/
    report-outline.md               khung báo cáo (điền số liệu vào)
    contributions.md                bảng phân công & đóng góp
    ai-usage.md                     khai báo sử dụng AI
```

---

## 3. Chạy nhanh (5 phút)

### 3.1. Chạy bộ test

```bash
python -m unittest discover -s tests -v
```

Kết quả mong đợi: `Ran 36 tests ... OK`.

### 3.2. Chạy thử 1 Server + 1 Client bằng tay (2 cửa sổ terminal)

Cửa sổ 1 — Server:

```bash
python src/server/tcp_server.py --host 127.0.0.1 --port 5050 --max-workers 128
```

Cửa sổ 2 — load generator:

```bash
python src/load-generator/load_client.py --host 127.0.0.1 --port 5050 ^
    --clients 10 --warmup 5 --duration 20 --payload-size 1024 ^
    --out-dir experiments/raw-data/thu-tay --run-id c10_thu
```

(Trên Linux/macOS thay `^` cuối dòng bằng `\`.)

Dừng Server bằng `Ctrl+C` — Server sẽ in thống kê cuối cùng trước khi thoát.

---

## 4. Tái tạo thí nghiệm chính

Toàn bộ 9 lần chạy (3 mức Client × 3 lần lặp, mỗi lần warm-up 5 s + đo 20 s) chỉ
cần **một lệnh**:

```bash
python run_experiments.py --config experiments/configs/baseline-1kb.json
```

Script tự động, với mỗi lần chạy:

1. Khởi động Server ở **process riêng** (bắt buộc theo đề bài), port `0` để hệ
   điều hành tự chọn port trống → không bao giờ gặp lỗi "port đang bị chiếm".
2. Chờ Server ghi file `*_ready.txt` rồi đọc host:port thật.
3. Chạy load generator ở **process riêng** với số Client tương ứng.
4. Dừng Server "nhẹ nhàng" để nó kịp ghi file thống kê, rồi nghỉ (cooldown) 5 s.

Thời gian: khoảng **5 phút**. Dữ liệu ra ở `experiments/raw-data/baseline-1kb/`.

Sau đó tổng hợp và vẽ biểu đồ:

```bash
python experiments/analysis/analyze.py --data-dir experiments/raw-data/baseline-1kb
python experiments/analysis/verify.py  --data-dir experiments/raw-data/baseline-1kb
```

### Tái tạo chỉ MỘT thí nghiệm (nhanh nhất, ~1 phút)

```bash
python run_experiments.py --config experiments/configs/baseline-1kb.json --levels 50 --repetitions 1
python experiments/analysis/verify.py --data-dir experiments/raw-data/baseline-1kb --runs c50_r1
```

### Chạy thử đường ống trước khi đo thật (~20 giây)

```bash
python run_experiments.py --config experiments/configs/smoke.json
```

### Kết quả đã đo được (lần chạy 24/11/2026)

Dữ liệu trong `experiments/raw-data/baseline-1kb/` là **số liệu thật**, chạy trên
Windows 11, 24 core logic, Python 3.13.1 — tổng cộng **4,7 triệu request**, 0 lỗi.

| Client | Latency TB (ms) | p95 (ms) | Throughput (req/s) | CPU Server (%) | Error rate |
|---:|---:|---:|---:|---:|---:|
| 1 | 0,048 ± 0,007 | 0,116 ± 0,026 | 19 842 ± 2 563 | 56,7 | 0% |
| 10 | 0,318 ± 0,042 | 0,627 ± 0,089 | 31 327 ± 4 267 | 226,4 | 0% |
| 50 | 1,843 ± 0,092 | 4,056 ± 0,164 | 27 104 ± 1 353 | 202,7 | 0% |

Tóm tắt: từ 1 → 50 Client, latency trung bình tăng **38 lần** và p95 tăng **35 lần**,
trong khi throughput **bão hòa từ khoảng 10 Client** (thậm chí giảm nhẹ ở 50 Client).
CPU của process Server dừng ở khoảng 2 core (≈ 9% của máy 24 core) → nút cổ chai
**không phải** là CPU của máy mà là khả năng xử lý song song của chính mô hình
(GIL + chi phí chuyển ngữ cảnh). Phân tích chi tiết: `experiments/analysis/summary.md`.

Chạy lại các lệnh ở trên sẽ **ghi đè** bộ số liệu này bằng số đo trên máy của nhóm.

---

## 5. Các file dữ liệu sinh ra

Với mỗi lần chạy `<run_id>` (ví dụ `c50_r2` = 50 Client, lần lặp 2):

| File | Nội dung |
|---|---|
| `<run_id>_requests.csv.gz` | **dữ liệu thô** — mỗi request một dòng: `client_id, request_id, send_ts_unix, latency_us, status` |
| `<run_id>_timeline.csv` | tổng hợp theo từng giây (số request OK/lỗi, latency TB, p95) |
| `<run_id>_histogram.csv` | phân bố latency theo bucket 50 µs (nguồn độc lập để kiểm chứng p95) |
| `<run_id>_summary.json` | cấu hình + toàn bộ số liệu tổng hợp của lần chạy |
| `<run_id>_server_cpu.csv` | mẫu CPU/RAM/số thread của **process Server**, 0,5 s một mẫu |
| `<run_id>_server_stats.json` | thống kê phía Server: số kết nối, request, lỗi, byte |
| `<run_id>_server.log` | log của Server |
| `runs.csv`, `environment.json` | danh mục các lần chạy + thông tin máy/cấu hình |

Dữ liệu thô được nén gzip vì một lần chạy 50 Client × 20 s sinh hơn 1 triệu dòng.
Mở bằng Excel: giải nén `.gz` trước, hoặc đọc trực tiếp bằng pandas
(`pd.read_csv("c50_r1_requests.csv.gz")`).

Kết quả tổng hợp nằm ở `experiments/analysis/`:
`aggregate.csv` (mỗi lần chạy một dòng), `summary_by_level.csv` (trung bình ±
độ lệch chuẩn theo mức Client), `summary.md` (bảng dán thẳng vào báo cáo),
`verification.csv` (kết quả kiểm chứng).

---

## 6. Protocol

TCP là dòng byte, **một lần `recv()` không đảm bảo trả về đúng một message**. Vì
vậy mỗi message được đóng gói theo kiểu length-prefixed:

```
+-----------------+--------+------------------+-------------------+
| body_len (4 B)  | type   | request_id (8 B) | payload           |
| uint32 big-end  | 1 byte | uint64 big-end   | body_len - 9 byte |
+-----------------+--------+------------------+-------------------+

body_len = 1 (type) + 8 (request_id) + len(payload)
type: 1 = REQUEST, 2 = RESPONSE, 3 = ERROR
```

- Bên nhận dùng `FrameDecoder`: nạp byte vào buffer, chỉ lấy ra message khi **đủ**
  `4 + body_len` byte; phần dư giữ lại chờ lần `recv()` sau. Một lần `recv()` chứa
  nhiều message thì tất cả đều được xếp hàng, không mất message nào.
- Giới hạn `body_len` ≤ 64 KiB. Vượt giới hạn → Server trả `ERROR` và **chỉ đóng
  kết nối đó**, các Client khác không bị ảnh hưởng.
- Client kiểm tra response: đúng `type`, đúng `request_id`, payload **khớp từng byte**
  với request đã gửi. Sai bất kỳ điều nào → tính là lỗi, ghi lý do vào dữ liệu thô.

---

## 7. Mô hình xử lý của Server

**Blocking socket + thread pool** (`concurrent.futures.ThreadPoolExecutor`):

- Luồng chính chỉ `accept()` kết nối mới.
- Mỗi kết nối được giao cho một worker thread trong pool cố định
  (`--max-workers`, mặc định 128) và được thread đó phục vụ đến khi đóng.
- Thread được **tái sử dụng** từ pool, không tạo mới cho mỗi kết nối.

Giới hạn cần nêu trong báo cáo: nếu số kết nối đồng thời vượt `--max-workers`, các
kết nối dư phải **nằm chờ trong hàng đợi của pool** — chúng đã được `accept()`
nhưng chưa có thread nào đọc dữ liệu. Cấu hình `experiments/configs/thread-limit.json`
hạ pool xuống 16 worker để quan sát đúng hiện tượng này.

Server còn xử lý: Client ngắt kết nối đột ngột (RST), Client đóng giữa chừng một
message, kết nối ngồi im quá `--idle-timeout` (tự đóng, đếm vào `conn_timeout`), và
dữ liệu rác. **Một kết nối lỗi không bao giờ làm chết Server** — mọi handler đều
được bọc trong `try/except`.

---

## 8. Cách đo

| Đại lượng | Cách đo |
|---|---|
| Latency | Đo ở **phía Client**, bằng `time.perf_counter_ns()`, tính từ ngay trước `sendall()` đến khi nhận đủ response và kiểm tra xong. Đơn vị µs. |
| p95 | Nearest-rank: sắp xếp tăng dần, lấy phần tử thứ `ceil(0,95 × n)`. Không nội suy, dễ kiểm tra lại bằng Excel. |
| Throughput | Số request **thành công** trong cửa sổ đo ÷ độ dài cửa sổ (20 s). |
| Error rate | Số request lỗi ÷ tổng số request trong cửa sổ đo. |
| CPU | `psutil` lấy mẫu **chính process Server** 0,5 s/lần. `cpu_percent` là % trên **một core** (200 % = 2 core đầy tải); `cpu_percent_norm` chia cho số core logic. Khi tổng hợp, chỉ lấy các mẫu **nằm trong cửa sổ đo**, bỏ phần warm-up. |

Mô hình tải là **closed-loop**: mỗi Client chỉ có một request đang chờ tại một thời
điểm, gửi xong mới gửi tiếp. Do đó `throughput ≈ số_Client / latency_trung_bình` —
đây là lý do throughput bão hòa trong khi latency tăng tuyến tính theo số Client.

---

## 9. Giới hạn đã biết (phải ghi trong báo cáo)

1. **Server và load generator chạy trên cùng một máy**, qua loopback `127.0.0.1`.
   Hai process tranh chấp CPU, và loopback không có độ trễ/mất gói của mạng thật.
   Con số latency vì vậy là **cận dưới**, không đại diện cho mạng LAN/WAN.
2. **Load generator cũng tốn CPU.** Ở mức 50 Client, phần CPU đo được của Server
   không phải toàn bộ tải của máy — phải đọc kèm cột `cpu_norm_avg`.
3. Python có **GIL**: thread pool không tận dụng hết nhiều core cho phần xử lý
   Python. Kết quả phản ánh đúng mô hình đã chọn, không phải giới hạn của TCP.
4. Mức 50 Client vẫn **chưa làm bão hòa** máy test nhiều core. Muốn thấy rõ điểm
   gãy, cần tăng số Client hoặc hạ `--max-workers` (xem `thread-limit.json`).
5. Mỗi mức Client chạy 3 lần; độ lệch chuẩn trong `summary_by_level.csv` cho biết
   độ dao động. **Không được chỉ báo cáo giá trị trung bình.**

---

## 10. Kiểm thử

```bash
python -m unittest discover -s tests -v
```

36 test, bao phủ đủ 5 nhóm yêu cầu kiểm thử của đề bài:

| Yêu cầu đề bài | Test tương ứng |
|---|---|
| Một Client và nhiều Client đồng thời | `TestSingleClient`, `TestConcurrentClients.test_ten_clients_concurrently` |
| Response đúng requestId và payload | `test_response_matches_request_id_and_payload`, `test_pipelined_requests_keep_order` |
| Client đóng kết nối bất thường | `TestClientFailures` (RST giữa message, đóng không đọc, connect rồi ngắt) |
| Dữ liệu không hợp lệ / payload vượt giới hạn | `TestInvalidInput` (body_len 100 MB, payload vượt hạn, type lạ, rác HTTP) |
| Server vẫn hoạt động sau khi một Client gặp lỗi | `test_server_survives_many_failing_clients` + mọi test lỗi đều mở kết nối mới kiểm tra lại |

Ngoài ra: framing byte-by-byte, nhiều message trong một `recv()`, idle timeout,
và hai test hồi quy cho lỗi thật đã gặp khi làm: "mất message khi một `recv()`
chứa nhiều message" và "một kết nối bị đếm đóng hai lần".

Kiểm chứng số liệu (`verify.py`) tính lại **từ dữ liệu thô**, không tin
`summary.json`: số request thành công, throughput, error rate, latency trung bình,
p95 (hai cách độc lập), tổng theo từng giây, số kết nối phía Server, và tính duy
nhất của `request_id`.
