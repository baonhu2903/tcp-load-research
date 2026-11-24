"""Test phần protocol: đóng gói, tách message, dữ liệu không hợp lệ.

Chạy: python -m unittest discover -s tests -v
"""

import os
import socket
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src", "common"))
import protocol


class TestTaoPayload(unittest.TestCase):
    def test_dung_kich_thuoc(self):
        self.assertEqual(len(protocol.tao_payload(1024)), 1024)
        self.assertEqual(len(protocol.tao_payload(1)), 1)
        self.assertEqual(len(protocol.tao_payload(0)), 0)

    def test_lan_nao_cung_giong_nhau(self):
        """Payload phải cố định thì các lần đo mới so sánh được với nhau."""
        self.assertEqual(protocol.tao_payload(1024), protocol.tao_payload(1024))


class TestGuiNhanQuaSocket(unittest.TestCase):
    """Dùng socketpair: hai socket nối sẵn với nhau, không cần Server."""

    def setUp(self):
        self.a, self.b = socket.socketpair()
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)

    def test_gui_roi_nhan_lai_nguyen_ven(self):
        protocol.gui_message(self.a, 12345, b"xin chao")
        request_id, payload = protocol.nhan_message(self.b)
        self.assertEqual(request_id, 12345)
        self.assertEqual(payload, b"xin chao")

    def test_payload_1kb(self):
        payload = protocol.tao_payload(1024)
        protocol.gui_message(self.a, 7, payload)
        request_id, nhan_duoc = protocol.nhan_message(self.b)
        self.assertEqual(request_id, 7)
        self.assertEqual(nhan_duoc, payload)

    def test_payload_rong(self):
        protocol.gui_message(self.a, 1, b"")
        self.assertEqual(protocol.nhan_message(self.b), (1, b""))

    def test_request_id_rat_lon(self):
        request_id = 50 * 10_000_000 + 999999
        protocol.gui_message(self.a, request_id, b"x")
        self.assertEqual(protocol.nhan_message(self.b)[0], request_id)

    def test_nhieu_message_lien_tiep(self):
        """Gửi 5 message một lúc rồi mới đọc: phải nhận đủ 5, đúng thứ tự."""
        for i in range(5):
            protocol.gui_message(self.a, i, b"so %d" % i)
        for i in range(5):
            self.assertEqual(protocol.nhan_message(self.b), (i, b"so %d" % i))

    def test_doi_phuong_dong_ket_noi(self):
        """Đối phương đóng kết nối -> nhan_message trả về None."""
        self.a.close()
        self.assertIsNone(protocol.nhan_message(self.b))

    def test_gui_tung_byte_mot(self):
        """QUAN TRỌNG: gửi nhỏ giọt từng byte, bên nhận vẫn phải ghép đúng.

        Đây chính là test chứng minh code không giả định
        "một lần recv = một message".
        """
        payload = protocol.tao_payload(3000)
        than = (42).to_bytes(8, "big") + payload
        goi = len(than).to_bytes(4, "big") + than

        def gui_cham():
            for i in range(len(goi)):
                self.a.sendall(goi[i:i + 1])

        t = threading.Thread(target=gui_cham, daemon=True)
        t.start()
        request_id, nhan_duoc = protocol.nhan_message(self.b)
        t.join(timeout=10)
        self.assertEqual(request_id, 42)
        self.assertEqual(nhan_duoc, payload)


class TestDocDuByte(unittest.TestCase):
    def setUp(self):
        self.a, self.b = socket.socketpair()
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)

    def test_doc_dung_so_byte_yeu_cau(self):
        self.a.sendall(b"0123456789")
        self.assertEqual(protocol.doc_du_byte(self.b, 4), b"0123")
        self.assertEqual(protocol.doc_du_byte(self.b, 6), b"456789")

    def test_thieu_byte_thi_tra_None(self):
        """Gửi 3 byte rồi đóng, trong khi bên kia cần 10 byte."""
        self.a.sendall(b"abc")
        self.a.close()
        self.assertIsNone(protocol.doc_du_byte(self.b, 10))


class TestDuLieuKhongHopLe(unittest.TestCase):
    def setUp(self):
        self.a, self.b = socket.socketpair()
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)

    def test_khai_bao_do_dai_1GB(self):
        """Kẻ gửi khai độ dài 1 GB -> phải bị chặn NGAY, không được đọc theo."""
        self.a.sendall((1_000_000_000).to_bytes(4, "big") + b"rac")
        with self.assertRaises(protocol.LoiGiaoThuc):
            protocol.nhan_message(self.b)

    def test_do_dai_qua_nho(self):
        """Thân message phải chứa ít nhất 8 byte request_id."""
        self.a.sendall((3).to_bytes(4, "big") + b"abc")
        with self.assertRaises(protocol.LoiGiaoThuc):
            protocol.nhan_message(self.b)

    def test_payload_vuot_gioi_han(self):
        qua_lon = protocol.MAX_BODY + 1
        self.a.sendall(qua_lon.to_bytes(4, "big"))
        with self.assertRaises(protocol.LoiGiaoThuc):
            protocol.nhan_message(self.b)

    def test_du_lieu_rac_kieu_HTTP(self):
        """Gửi rác HTTP: 4 byte đầu "GET " thành số rất lớn -> bị chặn."""
        self.a.sendall(b"GET / HTTP/1.1\r\n\r\n")
        with self.assertRaises(protocol.LoiGiaoThuc):
            protocol.nhan_message(self.b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
