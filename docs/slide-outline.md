# Khung slide trình bày (8–10 slide, ~7 phút)

| # | Slide | Nội dung chính | Thời lượng |
|---|---|---|---|
| 1 | Bìa | Tên đề tài, nhóm, thành viên, học phần | 15s |
| 2 | Câu hỏi research | "Khi số Client đồng thời tăng, latency / throughput / CPU của TCP Server thay đổi thế nào?" + phạm vi (1 Server, biến duy nhất là số Client) | 45s |
| 3 | Cơ sở lý thuyết | TCP là dòng byte → cần framing; các chỉ số latency/p95/throughput; định luật Little `throughput = N / latency` | 60s |
| 4 | Kiến trúc & protocol | Sơ đồ 2 tiến trình; khung message length-prefixed; mô hình mỗi kết nối một thread | 60s |
| 5 | Phương pháp đo | 1/10/50 Client × 3 lần, payload 1 KB, warm-up 5s + đo 20s, đo latency bằng `perf_counter_ns`, CPU bằng psutil | 60s |
| 6 | Kết quả — Hình 1 & 2 | Latency và p95 tăng theo số Client; throughput bão hòa. Đọc số cụ thể từ bảng | 75s |
| 7 | Kết quả — Hình 3 & 4 | CPU của Server; CDF latency cho thấy đuôi phân bố kéo dài | 45s |
| 8 | Phân tích | Vì sao throughput bão hòa còn latency tăng tuyến tính; p95/trung bình giãn ra; CPU có phải nút cổ chai không | 75s |
| 9 | Giới hạn | Cùng máy + loopback, load generator cũng tốn CPU, GIL, chỉ 3 mức Client | 45s |
| 10 | Kết luận & Demo | Trả lời thẳng câu hỏi bằng số; demo chạy `run_experiments.py --levels 50 --repetitions 1` rồi `verify.py` | 60s |

## Chuẩn bị demo (phòng khi máy chiếu chậm)

1. Mở sẵn 2 terminal ở thư mục dự án.
2. Lệnh demo ngắn (~1 phút):
   ```
   python run_experiments.py --config experiments/configs/baseline-1kb.json --levels 50 --repetitions 1
   python experiments/analysis/verify.py --data-dir experiments/raw-data/baseline-1kb --runs c50_r1
   ```
3. Có sẵn ảnh biểu đồ trong `experiments/figures/` để chiếu nếu demo lỗi.
4. Chuẩn bị trả lời 3 câu hỏi hay gặp:
   - *Vì sao không dùng một `recv()` cho mỗi message?* → TCP là dòng byte, demo hàm `doc_du_byte` và test `test_gui_tung_byte_mot`.
   - *Vì sao throughput không tăng khi thêm Client?* → hệ đã bão hòa, Little's law.
   - *Vì sao chọn mỗi kết nối một thread mà không phải async?* → đề bài chỉ yêu cầu một mô hình; nêu rõ ưu (đơn giản) và nhược (tốn thread khi nhiều Client).
