"""Giao thức trao đổi message giữa Client và Server.

VẤN ĐỀ: TCP là dòng byte (byte stream), KHÔNG phải dòng message.
Một lần sock.recv(1024) có thể trả về:
  - chỉ nửa message (vì dữ liệu bị chia nhỏ khi truyền), hoặc
  - 2-3 message dính liền nhau.
Nên không được viết kiểu "mỗi lần recv là được đúng 1 message".

CÁCH GIẢI QUYẾT: gắn độ dài vào đầu mỗi message (length-prefix).

    +-----------------+------------------+--------------------+
    | do_dai (4 byte) | request_id (8 B) | payload            |
    +-----------------+------------------+--------------------+
                      |<--- do_dai đếm số byte từ đây ------->|

Bên nhận đọc 4 byte đầu để biết phải đọc thêm bao nhiêu byte nữa, rồi đọc
cho ĐÚNG đủ số byte đó (hàm doc_du_byte bên dưới lặp đến khi đủ).

Lưu ý: chú thích tiếng Việt có dấu, nhưng các câu print() để KHÔNG dấu, để
khi ghi log ra file trên Windows không bị lỗi font.
"""

import socket

DO_DAI_HEADER = 4           # 4 byte đầu ghi độ dài phần thân
DO_DAI_REQUEST_ID = 8       # request_id chiếm 8 byte
MAX_BODY = 64 * 1024        # không nhận message có thân lớn hơn 64 KB


class LoiGiaoThuc(Exception):
    """Dữ liệu nhận được không đúng định dạng (sai độ dài, quá lớn...)."""


def tao_payload(kich_thuoc):
    """Tạo payload cố định, lần nào chạy cũng y hệt nhau.

    Dùng nội dung cố định (không random) để mọi lần đo đều gửi cùng dữ liệu.
    """
    mau = b"UTH-TCP-BENCH-"
    so_lan = kich_thuoc // len(mau) + 1
    return (mau * so_lan)[:kich_thuoc]


def gui_message(sock, request_id, payload):
    """Gửi 1 message. sendall() tự lo gửi cho hết, không gửi thiếu."""
    than = request_id.to_bytes(DO_DAI_REQUEST_ID, "big") + payload
    sock.sendall(len(than).to_bytes(DO_DAI_HEADER, "big") + than)


def doc_du_byte(sock, so_byte):
    """Đọc cho ĐÚNG ĐỦ so_byte byte rồi mới trả về.

    Đây chính là chỗ xử lý việc "1 lần recv không đủ 1 message": nếu recv
    trả về thiếu thì vòng while đọc tiếp cho tới khi đủ.

    Trả về None nếu đối phương đã đóng kết nối (recv trả về b"").
    """
    du_lieu = b""
    while len(du_lieu) < so_byte:
        mieng = sock.recv(so_byte - len(du_lieu))
        if not mieng:              # b"" nghĩa là đối phương đã đóng kết nối
            return None
        du_lieu += mieng
    return du_lieu


def nhan_message(sock):
    """Nhận 1 message đầy đủ.

    Trả về (request_id, payload), hoặc None nếu đối phương đóng kết nối.
    Ném LoiGiaoThuc nếu dữ liệu không hợp lệ.
    """
    header = doc_du_byte(sock, DO_DAI_HEADER)
    if header is None:
        return None

    do_dai_than = int.from_bytes(header, "big")
    # Phải kiểm tra TRƯỚC khi đọc tiếp: nếu ai đó gửi rác khai báo độ dài
    # 1 GB mà ta cứ đọc theo thì chương trình sẽ treo.
    if do_dai_than < DO_DAI_REQUEST_ID:
        raise LoiGiaoThuc("do dai than qua nho: %d" % do_dai_than)
    if do_dai_than > MAX_BODY:
        raise LoiGiaoThuc("do dai than %d vuot gioi han %d"
                          % (do_dai_than, MAX_BODY))

    than = doc_du_byte(sock, do_dai_than)
    if than is None:
        return None

    request_id = int.from_bytes(than[:DO_DAI_REQUEST_ID], "big")
    payload = than[DO_DAI_REQUEST_ID:]
    return request_id, payload


def bat_tcp_nodelay(sock):
    """Tắt thuật toán Nagle.

    Nagle gom nhiều gói nhỏ lại rồi mới gửi -> làm latency đo được tăng giả
    tạo. Khi đo hiệu năng request/response nhỏ thì phải tắt nó đi.
    """
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass        # không bật được thì thôi, không phải lỗi nghiêm trọng
