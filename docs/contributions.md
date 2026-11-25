# Bảng phân công và đóng góp

> Đề bài yêu cầu **mọi thành viên phải hiểu prototype, dữ liệu và kết luận của nhóm**,
> không chỉ phần mình làm. Điền tên thật, tỉ lệ đóng góp và ký xác nhận trước khi nộp.
> Tổng tỉ lệ đóng góp phải bằng 100%.

Nhóm: `[ĐIỀN]`  |  Lớp/Học phần: `[ĐIỀN]`  |  Thời gian: 4 tuần

| # | Họ và tên | MSSV | Vai trò chính | Công việc cụ thể | Sản phẩm bàn giao | Đóng góp (%) |
|---|---|---|---|---|---|---|
| 1 | `[ĐIỀN]` | | Protocol & Server | Thiết kế định dạng message, hàm `doc_du_byte`/`nhan_message`, vòng lặp Server, xử lý lỗi & timeout | `src/common/protocol.py`, `src/server/tcp_server.py` | |
| 2 | `[ĐIỀN]` | | Load generator | Mô hình closed-loop, đo latency, kiểm chứng response, ghi dữ liệu thô | `src/load-generator/load_client.py` | |
| 3 | `[ĐIỀN]` | | Kiểm thử | 31 test: 1/nhiều Client, tách message, ngắt kết nối, dữ liệu rác, idle timeout | `tests/` | |
| 4 | `[ĐIỀN]` | | Thực nghiệm & phân tích | Chạy 9 lần đo, tổng hợp, vẽ biểu đồ, script kiểm chứng | `run_experiments.py`, `experiments/analysis/`, `experiments/figures/` | |
| 5 | `[ĐIỀN]` | | Báo cáo & trình bày | Viết báo cáo, slide/video, README, tổng hợp tài liệu tham khảo | `docs/`, báo cáo PDF, slide | |
|   | **Tổng** | | | | | **100%** |

## Tiến độ theo tuần

| Tuần | Công việc chính | Người phụ trách | Trạng thái |
|---|---|---|---|
| 1 | Chốt câu hỏi, phạm vi, protocol, cách đo; dựng Server + load generator tối thiểu | | `[ ]` |
| 2 | Hoàn thiện prototype; kiểm thử kết nối, response, timeout, disconnect | | `[ ]` |
| 3 | Chạy các mức Client, lưu dữ liệu thô, kiểm chứng kết quả, tạo biểu đồ | | `[ ]` |
| 4 | Phân tích, hoàn thiện báo cáo/README/slide, chuẩn bị demo | | `[ ]` |

## Xác nhận của nhóm

Mỗi thành viên ký xác nhận đã **đọc và hiểu**: mô hình xử lý của Server, cơ chế tách
message, cách đo latency/throughput/CPU, dữ liệu thu được và kết luận của nhóm.

| Thành viên | Ngày | Ký tên |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
