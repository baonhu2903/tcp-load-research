"""Test Server: 1 Client, nhiều Client, ngắt kết nối, dữ liệu rác, timeout.

Bao phủ đúng 5 nhóm yêu cầu kiểm thử của đề bài:
    1. Một Client và nhiều Client đồng thời.
    2. Response đúng requestId và payload.
    3. Client đóng kết nối bất thường.
    4. Dữ liệu không hợp lệ hoặc payload vượt giới hạn.
    5. Server vẫn hoạt động sau khi một Client gặp lỗi.

Server được bật bằng subprocess (đúng như lúc chạy thật), không gọi hàm trực
tiếp, nên test này cũng kiểm tra luôn phần dòng lệnh của Server.

Chạy: python -m unittest discover -s tests -v
"""

import os
import socket
import struct
import subprocess
import sys
import threading
import time
import unittest

THU_MUC_TEST = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(THU_MUC_TEST, "..", "src", "common"))
import protocol

FILE_SERVER = os.path.join(THU_MUC_TEST, "..", "src", "server",
                           "tcp_server.py")


def tim_port_trong():
    """Mượn hệ điều hành một port trống rồi trả lại số port đó."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class ServerTestBase(unittest.TestCase):
    """Bật một Server thật cho mỗi lớp test, tắt đi khi xong."""

    IDLE_TIMEOUT = 30.0

    @classmethod
    def setUpClass(cls):
        cls.host = "127.0.0.1"
        cls.port = tim_port_trong()
        cls.proc = subprocess.Popen(
            [sys.executable, "-u", FILE_SERVER,
             "--host", cls.host, "--port", str(cls.port),
             "--idle-timeout", str(cls.IDLE_TIMEOUT)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Chờ Server chịu nhận kết nối
        het_han = time.time() + 15
        while time.time() < het_han:
            try:
                s = socket.create_connection((cls.host, cls.port), timeout=1)
                s.close()
                return
            except OSError:
                time.sleep(0.05)
        cls.proc.terminate()
        raise RuntimeError("Server khong khoi dong duoc")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.proc.kill()

    # --- tiện ích ---
    def ket_noi(self, timeout=5.0):
        s = socket.create_connection((self.host, self.port), timeout=timeout)
        s.settimeout(timeout)
        self.addCleanup(self.dong_im_lang, s)
        return s

    @staticmethod
    def dong_im_lang(s):
        try:
            s.close()
        except OSError:
            pass

    def goi_va_nhan(self, sock, request_id, payload):
        protocol.gui_message(sock, request_id, payload)
        return protocol.nhan_message(sock)

    def kiem_tra_server_con_song(self):
        """Mở kết nối MỚI và gửi thử - dùng sau mỗi tình huống lỗi."""
        s = self.ket_noi()
        self.assertEqual(self.goi_va_nhan(s, 999, b"con-song"),
                         (999, b"con-song"))


class TestMotClient(ServerTestBase):
    def test_echo_mot_request(self):
        s = self.ket_noi()
        self.assertEqual(self.goi_va_nhan(s, 1, b"ping"), (1, b"ping"))

    def test_dung_request_id_va_payload(self):
        """Yêu cầu 2: gửi 200 request, từng cái phải khớp cả id lẫn payload."""
        s = self.ket_noi()
        for i in range(1, 201):
            request_id = i * 7919
            payload = b"so-%d-" % i + protocol.tao_payload(i * 3)
            self.assertEqual(self.goi_va_nhan(s, request_id, payload),
                             (request_id, payload))

    def test_payload_1kb(self):
        s = self.ket_noi()
        payload = protocol.tao_payload(1024)
        request_id, nhan_duoc = self.goi_va_nhan(s, 55, payload)
        self.assertEqual(len(nhan_duoc), 1024)
        self.assertEqual(nhan_duoc, payload)

    def test_gui_tung_byte_mot(self):
        """Server không được giả định một lần recv là đủ một message."""
        s = self.ket_noi()
        payload = protocol.tao_payload(2000)
        than = (321).to_bytes(8, "big") + payload
        goi = len(than).to_bytes(4, "big") + than
        for i in range(len(goi)):
            s.sendall(goi[i:i + 1])
        self.assertEqual(protocol.nhan_message(s), (321, payload))

    def test_gui_lien_tiep_roi_moi_doc(self):
        """Gửi 10 request một lượt rồi mới đọc: đủ 10, đúng thứ tự."""
        s = self.ket_noi()
        for i in range(100, 110):
            protocol.gui_message(s, i, b"id=%d" % i)
        for i in range(100, 110):
            self.assertEqual(protocol.nhan_message(s), (i, b"id=%d" % i))


class TestNhieuClient(ServerTestBase):
    def test_10_client_dong_thoi(self):
        """Yêu cầu 1: 10 Client chạy song song, mỗi Client một kết nối riêng."""
        so_client, so_request = 10, 50
        cac_loi = []
        vach_xuat_phat = threading.Barrier(so_client)

        def mot_client(client_id):
            try:
                s = socket.create_connection((self.host, self.port),
                                             timeout=15)
                s.settimeout(15)
                vach_xuat_phat.wait(timeout=15)   # cho cùng xuất phát
                for k in range(so_request):
                    request_id = client_id * 10_000_000 + k
                    payload = b"c%d-k%d-" % (client_id, k) + \
                        protocol.tao_payload(512)
                    protocol.gui_message(s, request_id, payload)
                    tra_loi = protocol.nhan_message(s)
                    if tra_loi != (request_id, payload):
                        cac_loi.append("client %d sai o request %d"
                                       % (client_id, k))
                        return
                s.close()
            except Exception as loi:
                cac_loi.append("client %d: %r" % (client_id, loi))

        cac_thread = [threading.Thread(target=mot_client, args=(i,))
                      for i in range(1, so_client + 1)]
        for t in cac_thread:
            t.start()
        for t in cac_thread:
            t.join(timeout=60)
        self.assertEqual(cac_loi, [])

    def test_nhieu_client_ket_noi_roi_ngat_ngay(self):
        for _ in range(30):
            s = socket.create_connection((self.host, self.port), timeout=5)
            s.close()
        self.kiem_tra_server_con_song()


class TestClientGapSuCo(ServerTestBase):
    def test_ngat_dot_ngot_giua_message(self):
        """Yêu cầu 3 + 5: gửi nửa message rồi ngắt phũ (RST)."""
        s = self.ket_noi()
        payload = protocol.tao_payload(4096)
        than = (1).to_bytes(8, "big") + payload
        goi = len(than).to_bytes(4, "big") + than
        s.sendall(goi[:20])                   # mới gửi 20 byte đầu
        # SO_LINGER = 0 -> đóng bằng RST, giả lập Client bị kill
        s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                     struct.pack("ii", 1, 0))
        s.close()
        time.sleep(0.3)
        self.kiem_tra_server_con_song()

    def test_gui_xong_dong_luon_khong_doc(self):
        s = self.ket_noi()
        protocol.gui_message(s, 1, protocol.tao_payload(1024))
        s.close()
        time.sleep(0.3)
        self.kiem_tra_server_con_song()

    def test_20_client_loi_lien_tuc(self):
        """Yêu cầu 5: nhiều Client gây lỗi liên tục, Server vẫn phục vụ đúng."""
        for i in range(20):
            s = socket.create_connection((self.host, self.port), timeout=5)
            s.sendall(b"\xff\xff\xff\xff" if i % 2 else b"\x00\x00")
            s.close()
        time.sleep(0.5)
        # Kiểm tra kỹ: một Client tốt gửi 10 request liên tiếp vẫn đúng hết
        s = self.ket_noi()
        for k in range(10):
            self.assertEqual(self.goi_va_nhan(s, k, b"khoe-manh"),
                             (k, b"khoe-manh"))


class TestDuLieuKhongHopLe(ServerTestBase):
    """Yêu cầu 4.

    Lưu ý về TCP: khi Server từ chối và đóng kết nối trong lúc bộ đệm nhận
    của nó vẫn còn dữ liệu chưa đọc, hệ điều hành sẽ đóng kiểu phũ (gửi RST).
    Khi đó Client có thể nhận ConnectionReset thay vì đọc được gì. Cả hai
    kết cục đều hợp lệ - điều bắt buộc là Server phát hiện được và vẫn sống.
    """

    def kiem_tra_bi_tu_choi(self, s):
        try:
            self.assertIsNone(protocol.nhan_message(s))
        except (ConnectionResetError, ConnectionAbortedError):
            pass        # bị đóng bằng RST, cũng là "đã từ chối"
        except protocol.LoiGiaoThuc:
            pass        # Server trả về thứ không đúng định dạng

    def test_khai_bao_do_dai_100MB(self):
        s = self.ket_noi()
        s.sendall((100 * 1024 * 1024).to_bytes(4, "big") + b"rac")
        self.kiem_tra_bi_tu_choi(s)
        self.kiem_tra_server_con_song()

    def test_payload_vuot_gioi_han(self):
        """Tự tay dựng gói vượt giới hạn (gui_message bình thường sẽ không tạo
        ra gói như vậy)."""
        s = self.ket_noi()
        payload = protocol.tao_payload(protocol.MAX_BODY + 1)
        than = (1).to_bytes(8, "big") + payload
        s.sendall(len(than).to_bytes(4, "big") + than)
        self.kiem_tra_bi_tu_choi(s)
        self.kiem_tra_server_con_song()

    def test_rac_kieu_HTTP(self):
        s = self.ket_noi()
        s.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        self.kiem_tra_bi_tu_choi(s)
        self.kiem_tra_server_con_song()

    def test_do_dai_bang_0(self):
        s = self.ket_noi()
        s.sendall((0).to_bytes(4, "big"))
        self.kiem_tra_bi_tu_choi(s)
        self.kiem_tra_server_con_song()


class TestIdleTimeout(ServerTestBase):
    IDLE_TIMEOUT = 2.0          # rút ngắn để test chạy nhanh

    def test_ket_noi_ngoi_im_bi_dong(self):
        s = self.ket_noi(timeout=15)
        self.assertEqual(self.goi_va_nhan(s, 1, b"chao"), (1, b"chao"))
        time.sleep(self.IDLE_TIMEOUT + 1.5)
        # Server đã đóng -> recv trả về b""
        self.assertEqual(s.recv(100), b"")

    def test_ket_noi_van_gui_thi_khong_bi_dong(self):
        s = self.ket_noi(timeout=15)
        het_han = time.time() + self.IDLE_TIMEOUT * 2
        so_lan = 0
        while time.time() < het_han:
            self.assertEqual(self.goi_va_nhan(s, so_lan, b"con-day"),
                             (so_lan, b"con-day"),
                             "bi dong oan o request %d" % so_lan)
            so_lan += 1
            time.sleep(0.2)
        self.assertGreater(so_lan, 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
