"""TCP Echo Server - nhận request, trả lại y nguyên request đó.

MÔ HÌNH XỬ LÝ (phải ghi rõ trong báo cáo):
    blocking socket + mỗi kết nối một thread (thread-per-connection)

    - Luồng chính chỉ làm một việc: accept() kết nối mới.
    - Mỗi khi có Client kết nối, tạo một thread mới chạy hàm phuc_vu_client().
    - Thread đó dùng blocking socket: recv -> xử lý -> send, lặp lại cho đến
      khi Client đóng kết nối.

    Ưu điểm: dễ hiểu, dễ viết. Nhược điểm: mỗi kết nối tốn một thread, nên
    khi số Client rất lớn thì tốn RAM và tốn chi phí chuyển ngữ cảnh.

Chạy:
    python src/server/tcp_server.py --host 127.0.0.1 --port 5050
Dừng: Ctrl+C
"""

import argparse
import os
import socket
import sys
import threading
import time

# Cho Python tìm thấy file protocol.py nằm ở thư mục src/common
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "common"))
import protocol


# --- Các biến đếm dùng chung cho mọi thread ---------------------------------
# Nhiều thread cùng cộng vào một biến có thể làm sai số đếm, nên mỗi lần sửa
# phải khoá lại (lock) để tại một thời điểm chỉ một thread được sửa.
khoa = threading.Lock()
dem = {
    "ket_noi": 0,          # tổng số kết nối đã nhận
    "dang_mo": 0,          # số kết nối đang mở
    "request_ok": 0,       # số request đã trả lời xong
    "loi_du_lieu": 0,      # số lần nhận dữ liệu không hợp lệ
    "loi_timeout": 0,      # số kết nối bị đóng vì ngồi im quá lâu
    "ngat_dot_ngot": 0,    # số kết nối bị Client ngắt đột ngột
}


def cong_them(ten, so=1):
    with khoa:
        dem[ten] += so


def phuc_vu_client(conn, dia_chi, idle_timeout):
    """Phục vụ MỘT Client cho tới khi kết nối đóng. Chạy trong thread riêng.

    Toàn bộ thân hàm nằm trong try/except: một Client bị lỗi chỉ làm hỏng
    kết nối của chính nó, KHÔNG được làm chết Server.
    """
    protocol.bat_tcp_nodelay(conn)
    # Nếu Client không gửi gì trong idle_timeout giây thì recv() sẽ ném
    # socket.timeout -> ta đóng kết nối để khỏi giữ thread vô ích.
    conn.settimeout(idle_timeout)
    cong_them("ket_noi")
    cong_them("dang_mo")

    try:
        while True:
            ket_qua = protocol.nhan_message(conn)
            if ket_qua is None:          # Client đóng kết nối bình thường
                break
            request_id, payload = ket_qua
            # Dịch vụ echo: trả lại đúng request_id và đúng payload.
            protocol.gui_message(conn, request_id, payload)
            cong_them("request_ok")

    except socket.timeout:
        cong_them("loi_timeout")
        print("[server] %s: khong gui gi qua %.0fs -> dong ket noi"
              % (str(dia_chi), idle_timeout))

    except protocol.LoiGiaoThuc as loi:
        # Dữ liệu không hợp lệ hoặc payload vượt giới hạn.
        cong_them("loi_du_lieu")
        print("[server] %s: du lieu khong hop le (%s) -> dong ket noi"
              % (str(dia_chi), loi))

    except OSError:
        # Client bị tắt đột ngột (mất mạng, kill tiến trình...).
        cong_them("ngat_dot_ngot")

    finally:
        with khoa:
            dem["dang_mo"] -= 1
        try:
            conn.close()
        except OSError:
            pass


def in_thong_ke_dinh_ky(chu_ky):
    """Cứ mỗi chu_ky giây in một dòng thống kê. Chạy trong thread nền."""
    while True:
        time.sleep(chu_ky)
        with khoa:
            print("[server] dang_mo=%d ket_noi=%d request_ok=%d loi_du_lieu=%d"
                  % (dem["dang_mo"], dem["ket_noi"], dem["request_ok"],
                     dem["loi_du_lieu"]), flush=True)


def main():
    parser = argparse.ArgumentParser(description="TCP Echo Server")
    parser.add_argument("--host", default="127.0.0.1", help="dia chi lang nghe")
    parser.add_argument("--port", type=int, default=5050, help="cong lang nghe")
    parser.add_argument("--backlog", type=int, default=512,
                        help="so ket noi cho trong hang doi accept")
    parser.add_argument("--idle-timeout", type=float, default=30.0,
                        help="giay: Client khong gui gi thi dong ket noi")
    parser.add_argument("--stats-interval", type=float, default=0,
                        help="giay: in thong ke dinh ky (0 = tat)")
    args = parser.parse_args()

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((args.host, args.port))
    server_sock.listen(args.backlog)
    # Chờ tối đa 1 giây trong accept() rồi quay lại vòng lặp. Nhờ vậy khi
    # bấm Ctrl+C, Python mới có dịp xử lý và thoát được.
    server_sock.settimeout(1.0)

    print("[server] dang lang nghe tai %s:%d (idle-timeout %.0fs)"
          % (args.host, args.port, args.idle_timeout), flush=True)

    if args.stats_interval > 0:
        t = threading.Thread(target=in_thong_ke_dinh_ky,
                             args=(args.stats_interval,), daemon=True)
        t.start()

    bat_dau = time.time()
    try:
        while True:
            try:
                conn, dia_chi = server_sock.accept()
            except socket.timeout:
                continue            # hết 1 giây chờ, quay lại chờ tiếp
            # daemon=True: thread này sẽ tự chết khi chương trình chính thoát.
            t = threading.Thread(target=phuc_vu_client,
                                 args=(conn, dia_chi, args.idle_timeout),
                                 daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[server] nhan Ctrl+C, dang dung...")
    finally:
        server_sock.close()
        with khoa:
            print("[server] THONG KE CUOI sau %.1fs: %s"
                  % (time.time() - bat_dau, dem), flush=True)


if __name__ == "__main__":
    main()
