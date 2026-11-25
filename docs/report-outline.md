# Khung báo cáo research

> Hướng dẫn dùng file này: phần nào đã có sẵn nội dung thì giữ nguyên hoặc viết lại
> theo lời văn của nhóm; chỗ `[ĐIỀN: …]` là nơi điền số liệu thật sau khi chạy
> `analyze.py`. Số liệu lấy từ `experiments/analysis/summary.md` — **không gõ tay**
> để tránh sai lệch với dữ liệu thô.
>
> Độ dài yêu cầu: **4–6 trang nội dung chính** (không tính bìa, tài liệu tham khảo,
> phụ lục). Dồn trọng tâm vào mục 4, 5, 6 (phương pháp, kết quả, phân tích).

---

## 1. Câu hỏi research và phạm vi (~0,5 trang)

**Câu hỏi:** Khi số lượng Client đồng thời tăng, latency, throughput và mức sử dụng
CPU của TCP Server thay đổi như thế nào?

**Phạm vi:**

- Dịch vụ request/response tối giản trên TCP: **Echo Benchmark**. Client gửi
  `(requestId, payload)`, Server trả lại đúng `(requestId, payload)`, Client kiểm
  tra rồi ghi nhận thời gian.
- **Một** phiên bản Server duy nhất, mô hình blocking socket + mỗi kết nối một
  thread (thread-per-connection). Đề bài
  không yêu cầu so sánh hai mô hình xử lý — nhóm không mở rộng theo hướng đó.
- Biến độc lập **duy nhất**: số Client đồng thời (1, 10, 50). Payload, protocol,
  thời gian đo, máy chạy đều giữ nguyên giữa các lần.
- Console App, không GUI, chạy trên một máy.

**Giả thuyết trước khi đo:** vì mô hình tải là closed-loop (mỗi Client chỉ có một
request đang chờ), khi số Client vượt khả năng xử lý thì throughput sẽ bão hòa còn
latency tăng gần tuyến tính theo số Client.

---

## 2. Cơ sở lý thuyết (~0,75 trang)

Các ý cần có:

- **TCP là dòng byte (byte stream), không phải dòng message.** `send()` của bên gửi
  và `recv()` của bên nhận không tương ứng 1–1: một `recv()` có thể trả về nửa
  message, hoặc nhiều message dính liền. Nguyên nhân: TCP gom/chia dữ liệu theo MSS,
  cửa sổ gửi và thuật toán Nagle. → Bắt buộc phải có cơ chế **phân tách message
  (framing)**. Trích RFC 9293 §3.1 và Stevens ch. 3.
- **Hai kiểu framing phổ biến:** length-prefix (dự án dùng) và delimiter. So sánh
  ngắn: length-prefix xử lý được payload nhị phân bất kỳ, chi phí tách cố định.
- **Các chỉ số hiệu năng:** latency (độ trễ một request), throughput (số request/giây),
  p95/p99 (đuôi phân bố — quan trọng hơn trung bình khi đánh giá trải nghiệm),
  error rate, mức sử dụng CPU.
- **Định luật Little:** `L = λ × W`. Trong hệ closed-loop, số request đang xử lý `L`
  bằng số Client `N`, nên `throughput = N / latency`. Đây là công cụ chính để giải
  thích kết quả ở mục 6: khi throughput chạm trần, latency buộc phải tăng tỉ lệ
  thuận với `N`.
- **Mô hình xử lý đồng thời:** blocking + thread-per-connection, thread pool, và I/O
  bất đồng bộ. Nêu ngắn gọn ưu/nhược để biện minh lựa chọn của nhóm (mục 3).
- **TCP_NODELAY:** tắt thuật toán Nagle để tránh bị cộng thêm độ trễ nhân tạo khi đo
  request/response nhỏ. Cả hai phía đều bật.

---

## 3. Kiến trúc và protocol (~1 trang)

### 3.1. Kiến trúc

Vẽ sơ đồ: `load generator (N thread, N kết nối TCP)` ⇄ `TCP Server (luồng accept + mỗi kết nối một thread)`.
Nhấn mạnh: Server và load generator chạy ở **hai process riêng biệt**, mỗi Client
logic dùng **một kết nối TCP riêng**.

### 3.2. Định dạng message

```
+-----------------+------------------+--------------------+
| do_dai (4 byte) | request_id (8 B) | payload            |
+-----------------+------------------+--------------------+
                  |<--- do_dai đếm số byte từ đây ------->|
```

- `request_id` = `client_id × 10.000.000 + seq` → duy nhất toàn hệ thống, dùng để
  đối chiếu response và kiểm tra không có request nào bị trùng/mất.
- Giới hạn thân message ≤ 64 KB (`MAX_BODY`).

### 3.3. Cơ chế tách message

Nằm gọn trong hàm `doc_du_byte(sock, so_byte)`: lặp `recv` cho tới khi đọc **đủ
đúng** số byte cần mới trả về. Nhờ vậy `nhan_message()` chỉ cần đọc 4 byte đầu để
biết độ dài, rồi đọc tiếp đúng chừng đó byte — không bao giờ giả định "một lần
`recv` là một message". Test `test_gui_tung_byte_mot` gửi nhỏ giọt từng byte để
chứng minh điều này.

### 3.4. Mô hình xử lý của Server

Blocking socket + **mỗi kết nối một thread** (thread-per-connection): luồng chính
chỉ `accept()`, mỗi Client kết nối vào thì tạo một thread mới phục vụ riêng cho tới
khi kết nối đóng. Ưu điểm: đơn giản, dễ hiểu. Nhược điểm: mỗi kết nối tốn một
thread, số Client lớn thì tốn RAM và tốn chi phí chuyển ngữ cảnh.

### 3.5. Xử lý lỗi

| Tình huống | Cách xử lý |
|---|---|
| Client ngắt đột ngột (RST) | bắt `OSError`, đếm `ngat_dot_ngot`, đóng riêng kết nối đó |
| Client đóng kết nối bình thường | `nhan_message()` trả về `None` → thoát vòng lặp |
| Kết nối ngồi im quá hạn | `settimeout(--idle-timeout)` → bắt `socket.timeout`, đếm `loi_timeout` |
| Độ dài khai báo sai / dữ liệu rác | bắt `LoiGiaoThuc`, đếm `loi_du_lieu`, đóng **riêng** kết nối đó — Server vẫn phục vụ các Client khác |

---

## 4. Phương pháp thực nghiệm (~1 trang)

### 4.1. Cấu hình máy và môi trường

Lấy từ `experiments/raw-data/baseline-1kb/environment.json`:

- CPU / số core logic: `[ĐIỀN]`
- RAM: `[ĐIỀN]`
- Hệ điều hành: `[ĐIỀN]`
- Python: `[ĐIỀN]`
- Mạng: loopback `127.0.0.1`, Server và load generator **trên cùng một máy**
- Trạng thái máy khi đo: `[ĐIỀN: đã đóng trình duyệt/ứng dụng nặng, cắm sạc, không
  chạy quét virus…]`

### 4.2. Thiết kế thí nghiệm

| Tham số | Giá trị |
|---|---|
| Mức Client | 1, 10, 50 |
| Số lần lặp mỗi mức | 3 |
| Payload | 1024 B cố định, nội dung xác định trước (deterministic) |
| Warm-up | 5 s (chạy thật nhưng **không** ghi số liệu) |
| Cửa sổ đo | 20 s |
| Nghỉ giữa các lần | 5 s |
| Mô hình Server | mỗi kết nối một thread |
| Timeout socket phía Client | 5 s |

Tất cả nằm trong `experiments/configs/baseline-1kb.json` — chạy lại bằng đúng một
lệnh, không có bước thủ công nào.

### 4.3. Cách đo từng đại lượng

- **Latency:** đo ở phía Client bằng `time.perf_counter_ns()` (đồng hồ đơn điệu,
  độ phân giải ns), tính từ ngay trước `sendall()` đến khi nhận đủ response **và**
  kiểm tra xong `requestId` + payload.
- **p95:** nearest-rank, `idx = ceil(0,95 × n) - 1` trên mảng đã sắp xếp. Không nội
  suy để có thể kiểm tra lại bằng Excel.
- **Throughput:** số request thành công trong cửa sổ đo ÷ 20 s.
- **Error rate:** số request lỗi ÷ tổng số request trong cửa sổ đo. Lý do lỗi được
  phân loại (timeout, mat_ket_noi, sai_request_id, sai_payload…).
- **CPU:** `run_experiments.py` dùng `psutil` đo tiến trình Server **từ bên ngoài**,
  0,5 s/mẫu; khi tổng hợp chỉ lấy mẫu nằm trong cửa sổ đo. Lưu ý đơn vị:
  `cpu_percent` là % trên **một core** (200 % = 2 core chạy hết sức).

### 4.4. Kiểm chứng số liệu

`experiments/analysis/verify.py` mở lại **dữ liệu thô** và tính lại độc lập 7 chỉ số
(số request thành công, throughput, error rate, số request lỗi, latency trung bình,
p95, tính duy nhất của `request_id`). Kết quả: `[ĐIỀN: N ĐẠT / 0 TRƯỢT]`, chi tiết ở
`experiments/analysis/verification.csv`.

---

## 5. Kết quả (~1 trang)

Dán **Bảng 1** từ `experiments/analysis/summary.md` (trung bình ± độ lệch chuẩn của
3 lần lặp) và ít nhất **2 biểu đồ** từ `experiments/figures/`:

- **Hình 1** — Latency trung bình và p95 theo số Client (có thanh sai số).
- **Hình 2** — Throughput theo số Client.
- **Hình 3** — CPU của process Server theo số Client.
- **Hình 4** — Phân bố latency (CDF) ở các mức Client.

Mô tả kết quả bằng số, chưa giải thích (để dành mục 6):

- 1 Client: latency TB `[ĐIỀN]` ms, p95 `[ĐIỀN]` ms, throughput `[ĐIỀN]` req/s,
  CPU `[ĐIỀN]` %.
- 10 Client: `[ĐIỀN]`
- 50 Client: `[ĐIỀN]`
- Error rate ở cả ba mức: `[ĐIỀN]`.
- Độ dao động giữa 3 lần lặp (độ lệch chuẩn / hệ số biến thiên): `[ĐIỀN]`.

---

## 6. Phân tích (~1 trang)

Các ý cần có, mỗi ý **phải bám vào số liệu**:

1. **Latency tăng gần tuyến tính theo số Client.** So sánh tỉ lệ tăng trong Bảng 2
   với tỉ lệ `N`: từ 1 → 50 Client, nếu latency tăng khoảng `[ĐIỀN]` lần thì phù hợp
   với dự đoán của định luật Little khi throughput đã bão hòa.
2. **Throughput bão hòa.** Từ `[ĐIỀN]` Client trở đi throughput gần như không tăng
   thêm (`[ĐIỀN]` req/s). Giải thích bằng `throughput = N / latency`: khi hệ đã bão
   hòa, tăng `N` chỉ làm request xếp hàng lâu hơn chứ không tạo thêm công suất.
3. **p95 tăng nhanh hơn trung bình.** Tỉ số p95/trung bình ở 1 Client là `[ĐIỀN]`,
   ở 50 Client là `[ĐIỀN]`. Nguyên nhân: hàng đợi dài hơn → đuôi phân bố kéo dài,
   thấy rõ trên Hình 4. Đây là lý do không được chỉ báo cáo giá trị trung bình.
4. **CPU.** CPU của Server tăng từ `[ĐIỀN]` % lên `[ĐIỀN]` %. Nhận xét: CPU có phải
   là nút cổ chai không? Nếu CPU chưa đầy mà throughput đã bão hòa thì nút cổ chai
   nằm ở chỗ khác (GIL của Python, chi phí chuyển ngữ cảnh giữa thread, hoặc chính
   load generator). Dùng cột `server_threads_max` (số thread Server tạo ra) và
   `cpu_norm_avg` (% CPU so với toàn máy) trong `aggregate.csv` để lập luận.
5. **Error rate.** Nếu bằng 0 ở mọi mức, kết luận: trong phạm vi 1–50 Client, Server
   **không** mất request nào; giới hạn thể hiện qua latency chứ chưa đến mức gây lỗi.
6. **Độ dao động giữa các lần lặp.** Giải thích vì sao có dao động (lập lịch của hệ
   điều hành, tiến trình nền, trạng thái cache) và vì sao vẫn kết luận được (độ lệch
   chuẩn nhỏ hơn nhiều so với khoảng cách giữa các mức Client).

---

## 7. Giới hạn (~0,5 trang)

1. Server và load generator **chạy chung một máy**, qua loopback → hai process tranh
   chấp CPU; loopback không có độ trễ, mất gói, giới hạn băng thông như mạng thật.
   Latency đo được là **cận dưới**.
2. Load generator cũng tiêu tốn CPU, nên ở mức 50 Client, CPU đo của Server không
   phản ánh toàn bộ tải của máy.
3. Python có **GIL** → nhiều thread không tận dụng hết nhiều core cho phần xử lý
   Python. Kết quả phản ánh mô hình đã chọn, không phải giới hạn của giao thức TCP.
4. Chỉ thử 3 mức Client và một kích thước payload (1 KB); chưa xác định được chính
   xác điểm gãy của hệ. Mô hình mỗi kết nối một thread cũng chưa bị đẩy tới giới
   hạn ở mức 50 Client.
5. Mỗi mức chỉ lặp 3 lần — đủ để thấy xu hướng, chưa đủ cho kiểm định thống kê chặt chẽ.
6. `[ĐIỀN nếu gặp: máy bị giới hạn số kết nối, phần mềm diệt virus, pin/tiết kiệm
   điện làm giảm xung nhịp…]`

---

## 8. Kết luận (~0,25 trang)

Trả lời **thẳng** câu hỏi research bằng số liệu:

> Khi số Client đồng thời tăng từ 1 lên 50, latency trung bình tăng từ `[ĐIỀN]` ms
> lên `[ĐIỀN]` ms (≈ `[ĐIỀN]` lần) và p95 tăng từ `[ĐIỀN]` ms lên `[ĐIỀN]` ms, trong
> khi throughput chỉ thay đổi từ `[ĐIỀN]` lên `[ĐIỀN]` req/s (bão hòa từ khoảng
> `[ĐIỀN]` Client) và error rate giữ ở mức `[ĐIỀN]`. CPU của process Server tăng từ
> `[ĐIỀN]` % lên `[ĐIỀN]` %.

Thêm một câu về ý nghĩa thực tế (với mô hình này, số Client an toàn là bao nhiêu nếu
yêu cầu p95 dưới một ngưỡng cho trước) và một câu về hướng mở rộng.

---

## 9. Tài liệu tham khảo

Tối thiểu 3 nguồn, **bắt buộc** có tài liệu/slide của học phần và ít nhất một giáo
trình hoặc tài liệu kỹ thuật chính thức. Trích dẫn thống nhất một kiểu (IEEE hoặc APA).

Gợi ý (kiểm tra lại trước khi nộp, điền đúng số trang/chương đã dùng):

1. Slide/giáo trình học phần `[ĐIỀN tên học phần, chương, năm]`.
2. W. R. Stevens, B. Fenner, A. M. Rudoff, *UNIX Network Programming, Volume 1: The
   Sockets Networking API*, 3rd ed., Addison-Wesley, 2003 — chương 3 (byte stream,
   framing), chương 6 (I/O multiplexing), chương 30 (các mô hình server đồng thời).
3. J. F. Kurose, K. W. Ross, *Computer Networking: A Top-Down Approach* — chương 2
   (lập trình socket) và chương 3 (TCP).
4. W. Eddy (Ed.), *Transmission Control Protocol (TCP)*, RFC 9293, IETF, 8/2022.
5. Python Software Foundation, *Socket Programming HOWTO* và tài liệu module
   `socket`, `concurrent.futures` — https://docs.python.org/3/ `[ĐIỀN ngày truy cập]`.

**Khai báo sử dụng AI:** xem `docs/ai-usage.md`, cần đưa vào phụ lục báo cáo.

---

## 10. Phụ lục

- Bảng đóng góp của từng thành viên (`docs/contributions.md`).
- Bảng 3 — chi tiết từng lần chạy (`experiments/analysis/summary.md`).
- Kết quả kiểm chứng (`experiments/analysis/verification.csv`).
- Hướng dẫn chạy lại (`README.md`).
