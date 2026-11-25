# Khai báo sử dụng công cụ AI

> Đề bài: "Nếu sử dụng AI, nhóm phải khai báo công cụ và mục đích sử dụng; AI không
> được dùng làm nguồn kỹ thuật chính." Điền đúng thực tế của nhóm — phần dưới là
> khung mẫu, **không phải** lời khai sẵn.

## 1. Công cụ đã dùng

| Công cụ | Phiên bản/Thời điểm | Mục đích sử dụng | Phạm vi |
|---|---|---|---|
| `[ĐIỀN: tên công cụ]` | `[ĐIỀN]` | `[ĐIỀN: ví dụ sinh khung mã nguồn, giải thích khái niệm, rà soát lỗi, soát chính tả]` | `[ĐIỀN: file/phần nào]` |

## 2. Những gì AI KHÔNG được dùng để làm

- Không dùng AI làm **nguồn kỹ thuật chính**: mọi khẳng định về TCP, framing, mô
  hình server đều trích từ giáo trình / RFC / tài liệu chính thức liệt kê ở mục 9
  của báo cáo.
- Không dùng AI để **sinh ra số liệu đo**. Toàn bộ số liệu trong báo cáo đến từ các
  lần chạy thật trên máy của nhóm, lưu trong `experiments/raw-data/`, và được
  `experiments/analysis/verify.py` tính lại độc lập từ dữ liệu thô.

## 3. Cách nhóm kiểm chứng phần có AI hỗ trợ

- Chạy `python -m unittest discover -s tests` — 35 test phải PASS.
- Chạy `verify.py` — toàn bộ kiểm tra phải PASS.
- Mỗi thành viên đọc lại và giải thích được phần mã mình phụ trách (xem bảng xác
  nhận trong `contributions.md`).
