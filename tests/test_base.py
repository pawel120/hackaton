"""Testy pinecone_bot/base.py - bez sprzetu. Uruchamiac z katalogu repo:

    .\\.venv\\Scripts\\python.exe -m pytest tests/test_base.py -q
"""
from __future__ import annotations

import math
import os
import struct
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest  # noqa: E402

from pinecone_bot.base import (  # noqa: E402
    BIP_CMD_ACK,
    BIP_CMD_READ,
    BIP_CMD_READ_RESPONSE,
    BIP_CMD_WRITE,
    BIP_CODE_DISABLE_POWEROFF,
    BIP_CODE_ENABLE,
    BIP_CODE_HALL,
    BIP_CODE_SPEED,
    BIP_HALL_STRUCT,
    BIP_SOM_ACK,
    BIP_SOM_NOACK,
    BIP_SPEED_STRUCT,
    BipropellantBase,
    SimBase,
    XiaoBase,
    build_frame,
    make_base,
    parse_frames,
)
from pinecone_bot.config import Config  # noqa: E402


class FakeSerial:
    """Atrapa pyserial: zapamietuje write(), read() zwraca to, co dosypiemy feed()."""

    def __init__(self):
        self.writes: list[bytes] = []
        self.rx = b""
        self.closed = False
        self._lock = threading.Lock()

    def write(self, data):
        with self._lock:
            self.writes.append(bytes(data))
        return len(data)

    @property
    def in_waiting(self) -> int:
        with self._lock:
            return len(self.rx)

    def read(self, n=1):
        with self._lock:
            out, self.rx = self.rx[:n], self.rx[n:]
        return out

    def feed(self, data: bytes):
        with self._lock:
            self.rx += bytes(data)

    def close(self):
        self.closed = True

    def lines(self) -> list[bytes]:
        with self._lock:
            return list(self.writes)


def factory_for(fake: FakeSerial, calls: list | None = None):
    def factory(port, baud):
        if calls is not None:
            calls.append((port, baud))
        return fake
    return factory


# ---------------------------------------------------------------------------
# SimBase
# ---------------------------------------------------------------------------
def test_sim_forward_one_second():
    b = SimBase(Config())
    b.set_speed(0.2, 0.0)
    for _ in range(100):
        b.advance(0.01)
    x, y, th = b.odometry()
    assert x == pytest.approx(0.2, abs=1e-9)
    assert y == pytest.approx(0.0, abs=1e-9)
    assert th == pytest.approx(0.0, abs=1e-9)


def test_sim_turn_left_quarter():
    cfg = Config()
    cfg.control.w_max = 2.0  # domyslne 0.6 rad/s obcieloby pi/2
    b = SimBase(cfg)
    b.set_speed(0.0, math.pi / 2)
    b.advance(1.0)
    assert b.theta == pytest.approx(math.pi / 2)
    assert b.x == pytest.approx(0.0, abs=1e-9)


def test_sim_arc_is_consistent():
    b = SimBase(Config())
    b.set_speed(0.2, 0.4)  # promien 0.5 m, 1 s -> kat 0.4 rad
    b.advance(1.0)
    assert b.theta == pytest.approx(0.4)
    assert b.x == pytest.approx(0.5 * math.sin(0.4))
    assert b.y == pytest.approx(0.5 * (1 - math.cos(0.4)))


def test_sim_clamps_to_control_limits():
    cfg = Config()
    b = SimBase(cfg)
    b.set_speed(5.0, -5.0)
    assert b.v == cfg.control.v_max
    assert b.w == -cfg.control.w_max
    b.set_speed(-5.0, 5.0)
    assert b.v == cfg.control.v_min
    assert b.w == cfg.control.w_max


def test_sim_with_clock():
    t = [0.0]
    b = SimBase(Config(), clock=lambda: t[0])
    b.set_speed(0.1, 0.0)
    t[0] = 2.0
    x, _, _ = b.odometry()
    assert x == pytest.approx(0.2)
    b.stop()
    t[0] = 5.0
    assert b.odometry()[0] == pytest.approx(0.2)


def test_make_base_sim_and_unknown():
    cfg = Config()
    assert isinstance(make_base(cfg), SimBase)
    cfg.base.driver = "nope"
    with pytest.raises(ValueError):
        make_base(cfg)


# ---------------------------------------------------------------------------
# XiaoBase
# ---------------------------------------------------------------------------
@pytest.fixture
def xiao():
    fake = FakeSerial()
    calls: list = []
    cfg = Config()
    cfg.base.driver = "xiao"
    base = make_base(cfg, serial_factory=factory_for(fake, calls), settle_s=0.0)
    assert isinstance(base, XiaoBase)
    assert calls == [(cfg.base.port, 115200)]
    yield base, fake
    base.close()


def test_xiao_forward_maps_to_pwm_max(xiao):
    base, fake = xiao
    base.set_speed(0.25, 0.0)
    assert fake.lines()[-1] == b"a260 b0\n"


def test_xiao_left_turn_is_negative_steer(xiao):
    base, fake = xiao
    base.set_speed(0.0, 0.6)
    assert fake.lines()[-1] == b"a0 b-220\n"
    base.set_speed(0.0, -0.6)
    assert fake.lines()[-1] == b"a0 b220\n"


def test_xiao_static_friction_offset_and_reverse(xiao):
    base, fake = xiao
    base.set_speed(-0.1, 0.0)  # 80 + 0.1/0.25 * 180 = 152
    assert fake.lines()[-1] == b"a-152 b0\n"
    base.set_speed(0.00001, 0.0)  # ponizej epsilon -> zero, bez offsetu
    assert fake.lines()[-1] == b"a0 b0\n"


def test_xiao_clamps_before_mapping(xiao):
    base, fake = xiao
    base.set_speed(10.0, -10.0)
    assert fake.lines()[-1] == b"a260 b220\n"


def test_xiao_stop_writes_zero_immediately(xiao):
    base, fake = xiao
    base.set_speed(0.2, 0.0)
    base.stop()
    assert fake.lines()[-1] == b"a0 b0\n"
    assert base.odometry() is None


def test_xiao_thread_resends(xiao):
    base, fake = xiao
    base.set_speed(0.1, 0.0)
    n0 = len(fake.lines())
    time.sleep(0.4)
    new = fake.lines()[n0:]
    assert len(new) >= 3
    assert all(line == b"a152 b0\n" for line in new)


def test_xiao_close_stops_thread_and_zeroes():
    fake = FakeSerial()
    cfg = Config()
    base = XiaoBase(cfg, serial_factory=factory_for(fake), settle_s=0.0)
    base.set_speed(0.2, 0.1)
    base.close()
    assert not base._thread.is_alive()
    assert fake.lines()[-2:] == [b"a0 b0\n", b"a0 b0\n"]
    assert fake.closed
    n = len(fake.lines())
    time.sleep(0.2)
    assert len(fake.lines()) == n  # nic wiecej nie leci po close()


# ---------------------------------------------------------------------------
# Bipropellant - funkcje ramek
# ---------------------------------------------------------------------------
def test_build_frame_test_message():
    frame = build_frame(0x02, 0x01, b"TABCD")
    # CS = 0 - (CI + LEN + sum(DATA)) mod 256 (wiki "Protocol Defn"); dla tych
    # danych to 0x9C. Sprawdzamy tez niezmiennik: suma od CI do CS == 0 mod 256.
    assert frame == bytes.fromhex("02 01 05 54 41 42 43 44 9C")
    assert sum(frame[1:]) & 0xFF == 0


def test_build_frame_roundtrip_and_ci_wrap():
    payload = bytes(range(0, 40))
    frame = build_frame(BIP_SOM_NOACK, 0x1FF, payload)
    frames, rest = parse_frames(frame)
    assert frames == [(BIP_SOM_NOACK, 0xFF, payload)]
    assert rest == b""


def test_parse_frames_split_and_garbage():
    f1 = build_frame(0x02, 7, b"r\x03" + BIP_SPEED_STRUCT.pack(*range(9)))
    f2 = build_frame(0x04, 8, b"A")
    stream = b"\x00\xff\x02\x99" + f1 + f2  # smieci, w tym falszywy SOM 0x02
    frames, rest = parse_frames(stream[:10])
    assert frames == []
    assert stream[:10].endswith(rest)  # ogon zaczyna sie na kandydacie SOM
    frames, rest = parse_frames(rest + stream[10:])
    assert [(s, c) for s, c, _ in frames] == [(0x02, 7), (0x04, 8)]
    assert frames[0][2][:2] == b"r\x03"
    assert rest == b""


def test_parse_frames_bad_checksum_skipped():
    good = build_frame(0x04, 1, b"A")
    bad = bytearray(build_frame(0x04, 9, b"A"))  # CI=9: nie wyglada jak SOM
    bad[-1] ^= 0xFF
    frames, rest = parse_frames(bytes(bad) + good)
    assert frames == [(0x04, 1, b"A")]
    assert rest == b""
    # Falszywy SOM z duzym LEN (tu CI=0x02) legalnie czeka na dalsze bajty;
    # parser dochodzi do siebie, gdy strumien plynie dalej.
    bad2 = bytearray(build_frame(0x04, 0x02, b"A"))
    bad2[-1] ^= 0xFF
    frames, rest = parse_frames(bytes(bad2) + good)
    assert frames == []
    frames, rest = parse_frames(rest + bytes(80) + good)
    assert frames[-1] == (0x04, 1, b"A")
    assert rest == b""


# ---------------------------------------------------------------------------
# Bipropellant - sterownik
# ---------------------------------------------------------------------------
def hall_payload(mm_l: int, mm_r: int) -> bytes:
    def one(mm):
        return BIP_HALL_STRUCT.pack(0, 0, 1.0, 0, mm, 0, 0, 0, 0)
    return one(mm_l) + one(mm_r)


def hall_response(ci: int, mm_l: int, mm_r: int) -> bytes:
    return build_frame(BIP_SOM_NOACK, ci, bytes([BIP_CMD_READ_RESPONSE, BIP_CODE_HALL]) + hall_payload(mm_l, mm_r))


def decode_writes(fake: FakeSerial):
    frames, rest = parse_frames(b"".join(fake.lines()))
    assert rest == b""
    return frames


def make_bip(fake: FakeSerial, timeout: float = 0.0, autostart: bool = False) -> BipropellantBase:
    cfg = Config()
    cfg.base.driver = "bipropellant"
    base = make_base(cfg, serial_factory=factory_for(fake), connect_timeout_s=timeout, autostart=autostart)
    assert isinstance(base, BipropellantBase)
    return base


def test_bip_connect_sequence_and_defaults():
    fake = FakeSerial()
    base = make_bip(fake)
    frames = decode_writes(fake)
    heads = [(s, d[0], d[1]) for s, _, d in frames]
    assert heads == [
        (BIP_SOM_ACK, BIP_CMD_WRITE, BIP_CODE_DISABLE_POWEROFF),
        (BIP_SOM_ACK, BIP_CMD_WRITE, BIP_CODE_ENABLE),
        (BIP_SOM_ACK, BIP_CMD_READ, BIP_CODE_SPEED),
    ]
    assert [c for _, c, _ in frames] == [1, 2, 3]  # CI rosnie
    assert base.speed_limits == (600, -600, 30)
    assert base.speed_limits_source == "default"
    assert base.odometry() is None


def test_bip_adopts_firmware_speed_limits():
    fake = FakeSerial()
    fake.feed(build_frame(BIP_SOM_ACK, 9, b"r\x03" + BIP_SPEED_STRUCT.pack(0, 0, 700, -650, 40, 0, 0, 0, 0)))
    base = make_bip(fake, timeout=0.3)
    assert base.speed_limits == (700, -650, 40)
    assert base.speed_limits_source == "firmware"
    # odpowiedz miala SOM 0x02 -> odsylamy ACK z tym samym CI
    acks = [(c, d) for s, c, d in decode_writes(fake) if d == bytes([BIP_CMD_ACK])]
    assert acks == [(9, b"A")]


def test_bip_speed_frame_for_forward():
    fake = FakeSerial()
    base = make_bip(fake)
    base.set_speed(0.1, 0.0)
    frames, rest = parse_frames(base.speed_frame())
    assert rest == b"" and len(frames) == 1
    som, _, data = frames[0]
    assert som == BIP_SOM_NOACK
    assert data[0] == BIP_CMD_WRITE and data[1] == BIP_CODE_SPEED
    fields = BIP_SPEED_STRUCT.unpack(data[2:])
    assert fields[0] == 100 and fields[1] == 100
    assert fields[2:5] == (600, -600, 30)


def test_bip_turn_left_speeds_right_wheel_faster():
    fake = FakeSerial()
    base = make_bip(fake)
    base.set_speed(0.0, 0.4)  # B = 0.5 m -> +-100 mm/s
    left, right = base.wheel_speeds_mm(base.v, base.w)
    assert (left, right) == (-100, 100)


def test_bip_hall_odometry_forward():
    fake = FakeSerial()
    base = make_bip(fake)
    base.process_incoming(hall_response(1, 0, 0))
    assert base.odometry() == pytest.approx((0.0, 0.0, 0.0))
    fake.feed(hall_response(2, 500, 500))
    base.poll()
    x, y, th = base.odometry()
    assert x == pytest.approx(0.5)
    assert y == pytest.approx(0.0, abs=1e-9)
    assert th == pytest.approx(0.0, abs=1e-9)
    assert base.hall_responses == 2


def test_bip_hall_odometry_turn_in_place():
    fake = FakeSerial()
    base = make_bip(fake)
    base.process_incoming(hall_response(1, 1000, 1000))
    d = int(round(base.wheel_base_m / 2 * math.pi / 2 * 1000))  # kazde kolo +-B/2 * pi/2
    base.process_incoming(hall_response(2, 1000 - d, 1000 + d))
    x, y, th = base.odometry()
    assert th == pytest.approx(math.pi / 2, abs=5e-3)  # zaokraglenie do 1 mm na kolo
    assert abs(x) < 1e-3 and abs(y) < 1e-3


def test_bip_hall_response_split_across_reads():
    fake = FakeSerial()
    base = make_bip(fake)
    base.process_incoming(hall_response(1, 0, 0))
    resp = hall_response(2, 200, 200)
    base.process_incoming(b"\x00" + resp[:20])
    assert base.odometry()[0] == pytest.approx(0.0)
    base.process_incoming(resp[20:])
    assert base.odometry()[0] == pytest.approx(0.2)


def test_bip_tick_sends_speed_and_hall_requests():
    fake = FakeSerial()
    base = make_bip(fake)
    base.set_speed(0.05, 0.0)
    for _ in range(8):
        base.tick()
    frames = decode_writes(fake)[3:]  # pomijamy sekwencje connect
    speeds = [d for _, _, d in frames if d[0] == BIP_CMD_WRITE and d[1] == BIP_CODE_SPEED]
    halls = [d for _, _, d in frames if d[0] == BIP_CMD_READ and d[1] == BIP_CODE_HALL]
    assert len(speeds) == 8
    assert 1 <= len(halls) <= 3  # co bip_hall_every=4 ramki
    assert all(BIP_SPEED_STRUCT.unpack(d[2:])[:2] == (50, 50) for d in speeds)


def test_bip_thread_and_close():
    fake = FakeSerial()
    base = make_bip(fake, autostart=True)
    base.set_speed(0.1, 0.0)
    time.sleep(0.3)
    n_before = len(fake.lines())
    assert n_before >= 3 + 3
    base.close()
    assert not base._thread.is_alive()
    assert fake.closed
    frames = decode_writes(fake)
    speeds = [d for _, _, d in frames if d[0] == BIP_CMD_WRITE and d[1] == BIP_CODE_SPEED]
    assert BIP_SPEED_STRUCT.unpack(speeds[-1][2:])[:2] == (0, 0)
    assert BIP_SPEED_STRUCT.unpack(speeds[-2][2:])[:2] == (0, 0)
    assert frames[-1][2][:2] == bytes([BIP_CMD_WRITE, BIP_CODE_ENABLE])
    n = len(fake.lines())
    time.sleep(0.15)
    assert len(fake.lines()) == n


def test_struct_sizes():
    assert BIP_SPEED_STRUCT.size == 36
    assert BIP_HALL_STRUCT.size == 36
    assert struct.calcsize("<i") == 4
