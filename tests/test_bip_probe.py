"""Testy tools/bip_probe.py - bez sprzetu. Uruchamiac z katalogu repo:

    .\\.venv\\Scripts\\python.exe -m pytest tests/test_bip_probe.py -q
"""
from __future__ import annotations

import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest  # noqa: E402

from pinecone_bot.base import (  # noqa: E402
    BIP_CMD_ACK,
    BIP_CMD_READ,
    BIP_CMD_READ_RESPONSE,
    BIP_CODE_HALL,
    BIP_HALL_MM_INDEX,
    BIP_HALL_STRUCT,
    BIP_SOM_ACK,
    BIP_SOM_NOACK,
    build_frame,
    parse_frames,
)
from tools import bip_probe  # noqa: E402


# ---------------------------------------------------------------------------
# atrapa portu
# ---------------------------------------------------------------------------
class FakeSerial:
    """
    Atrapa pyserial dla sondy: write() moze zakolejkowac scenariusz odpowiedzi
    na podstawie tego, co bylo wyslane (`scripts`: lista (predykat, bajty)).
    Kazdy fragment z kolejki trafia do bufora rx dopiero, gdy poprzedni zostal
    w calosci odczytany - to pozwala testowac odbior rozlozony na kilka read().
    """

    def __init__(self, scripts=None):
        self.writes: list[bytes] = []
        self._rx = bytearray()
        self._pending: list[bytes] = []
        self.closed = False
        self.scripts = scripts or []

    def write(self, data):
        data = bytes(data)
        self.writes.append(data)
        for predicate, response in self.scripts:
            if predicate(data):
                self._pending.append(bytes(response))
        return len(data)

    def queue(self, chunk: bytes) -> None:
        self._pending.append(bytes(chunk))

    def _pull_pending(self) -> None:
        if not self._rx and self._pending:
            self._rx += self._pending.pop(0)

    @property
    def in_waiting(self) -> int:
        self._pull_pending()
        return len(self._rx)

    def read(self, n=1):
        self._pull_pending()
        out = bytes(self._rx[:n])
        del self._rx[:n]
        return out

    def close(self):
        self.closed = True


def factory_for(fake: FakeSerial):
    def factory(port, baud):
        return fake
    return factory


def _pack_hall(posn_mm: int, speed_mm_s: int = 0) -> bytes:
    # HallPosn, HallSpeed, HallPosnMultiplier, HallPosn_lastread, HallPosn_mm,
    # HallPosn_mm_lastread, HallSpeed_mm_per_s, HallTimeDiff, HallSkipped
    return BIP_HALL_STRUCT.pack(0, 0, 1.0, 0, posn_mm, 0, speed_mm_s, 0, 0)


def no_writes_have_w_cmd(fake: FakeSerial) -> None:
    """Wsrod wszystkich ramek, ktore probka wyslala, zaden byte cmd nie jest 'W'."""
    for data in fake.writes:
        frames, _ = parse_frames(data)
        for _som, _ci, payload in frames:
            assert payload[:1] != b"W", "sonda wyslala ramke z cmd=W (komenda silnikow): %r" % data


@pytest.fixture(autouse=True)
def fast_waits(monkeypatch):
    """Zeruje stale opoznienia (0.5 s / 0.3 s), zeby testy nie czekaly naprawde."""
    monkeypatch.setattr(bip_probe, "UNSOLICITED_WAIT_S", 0.0)
    monkeypatch.setattr(bip_probe, "ASCII_UNLOCK_WAIT_S", 0.0)


# ---------------------------------------------------------------------------
# 1) detekcja ASCII - pozytyw i negatyw
# ---------------------------------------------------------------------------
def test_ascii_detected_positive():
    fake = FakeSerial(scripts=[
        (lambda d: d.startswith(b"?"), b"Options:\r\na - speed\r\nb - steer\r\n"),
        (lambda d: d.startswith(b"H"), b"Hall: L=100 R=100\r\n"),
    ])
    result = bip_probe.probe_ascii(fake, seconds=0.02)
    assert result["detected"] is True
    assert "Options" in result["raw"].decode("ascii")
    assert "Hall" in result["hall_text"]
    assert fake.writes[0] == b"unlockASCII\r\n"
    assert fake.writes[1] == b"?\r\n"
    assert fake.writes[2] == b"H\r\n"
    no_writes_have_w_cmd(fake)


def test_ascii_detected_negative_on_silence():
    fake = FakeSerial()  # zadnych zaprogramowanych odpowiedzi - czysta cisza
    result = bip_probe.probe_ascii(fake, seconds=0.02)
    assert result["detected"] is False
    assert result["raw"] == b""


def test_ascii_detected_negative_on_short_garbage():
    # krotki smiec bez zadnego markera i ponizej progu 20 znakow drukowalnych
    fake = FakeSerial(scripts=[(lambda d: d.startswith(b"?"), b"\x00\x01xy")])
    result = bip_probe.probe_ascii(fake, seconds=0.02)
    assert result["detected"] is False


# ---------------------------------------------------------------------------
# 2) detekcja binarna - ACK, TESTRESPONSE, wersja, hall
# ---------------------------------------------------------------------------
def _binary_fake() -> FakeSerial:
    def is_test_frame(data: bytes) -> bool:
        frames, _ = parse_frames(data)
        return any(f[2][:1] == bytes([bip_probe.BIP_CMD_TEST]) for f in frames)

    def is_version_read(data: bytes) -> bool:
        frames, _ = parse_frames(data)
        return any(f[2][:2] == bytes([BIP_CMD_READ, 0x00]) for f in frames)

    def is_hall_read(data: bytes) -> bool:
        frames, _ = parse_frames(data)
        return any(f[2][:2] == bytes([BIP_CMD_READ, BIP_CODE_HALL]) for f in frames)

    ack_and_test = (
        build_frame(BIP_SOM_NOACK, 1, bytes([BIP_CMD_ACK]))
        + build_frame(BIP_SOM_NOACK, 2, bytes([bip_probe.BIP_CMD_TESTRESPONSE]) + b"ABCD")
    )
    version_resp = build_frame(BIP_SOM_NOACK, 3, bytes([BIP_CMD_READ_RESPONSE, 0x00]) + struct.pack("<i", 42))
    hall_payload = _pack_hall(123, 10) + _pack_hall(456, 20)
    hall_resp = build_frame(BIP_SOM_NOACK, 4, bytes([BIP_CMD_READ_RESPONSE, BIP_CODE_HALL]) + hall_payload)

    return FakeSerial(scripts=[
        (is_test_frame, ack_and_test),
        (is_version_read, version_resp),
        (is_hall_read, hall_resp),
    ])


def test_binary_decodes_ack_test_version_hall():
    fake = _binary_fake()
    result = bip_probe.probe_binary(fake, seconds=0.02)
    assert result["ack"] is True
    assert result["test_response"] == b"ABCD"
    assert result["version"] == 42
    assert result["hall"] is not None
    h0, h1 = result["hall"]
    assert h0[BIP_HALL_MM_INDEX] == 123
    assert h1[BIP_HALL_MM_INDEX] == 456
    no_writes_have_w_cmd(fake)


def test_verdict_line_reports_hit_for_binary_answer():
    fake = _binary_fake()
    baud_result = bip_probe.probe_baud("COMX", 115200, 0.02, factory_for(fake), ascii_only=False, binary_only=True)
    assert baud_result["hit"] is True
    line = bip_probe.verdict_line(baud_result)
    assert line.startswith("115200: ")
    assert "binarny TAK" in line
    assert "version=42" in line


# ---------------------------------------------------------------------------
# 3) cisza totalna -> werdykt + kod wyjscia 2, przez main()
# ---------------------------------------------------------------------------
def test_total_silence_gives_exit_code_2(monkeypatch, capsys):
    fake = FakeSerial()  # nigdy nic nie odpowiada
    monkeypatch.setattr(bip_probe, "_default_serial_factory", lambda port, baud: fake)
    code = bip_probe.main(["--port", "/dev/fake", "--baud", "115200,9600", "--seconds", "0.01"])
    assert code == 2
    out = capsys.readouterr().out
    assert "Ten test nie rusza silnikow." in out
    assert "115200: ASCII NIE, binarny NIE" in out
    assert "9600: ASCII NIE, binarny NIE" in out
    assert "Brak odpowiedzi na zadnym baudzie" in out
    no_writes_have_w_cmd(fake)


def test_run_probe_stops_after_first_hit_unless_all():
    fake_hit = _binary_fake()
    calls = []

    def factory(port, baud):
        calls.append(baud)
        return fake_hit

    results, code = bip_probe.run_probe("COMX", [115200, 9600, 38400], 0.02, serial_factory=factory,
                                         binary_only=True)
    assert code == 0
    assert calls == [115200]  # przerwane po pierwszym trafieniu
    assert len(results) == 1

    calls.clear()
    results_all, code_all = bip_probe.run_probe("COMX", [115200, 9600], 0.02, serial_factory=factory,
                                                 binary_only=True, all_bauds=True)
    assert calls == [115200, 9600]
    assert len(results_all) == 2


# ---------------------------------------------------------------------------
# 4) sonda nigdy nie wysyla ramki z cmd='W'
# ---------------------------------------------------------------------------
def test_never_sends_motor_write_frame():
    fake = _binary_fake()
    result = bip_probe.probe_baud("COMX", 115200, 0.02, factory_for(fake))
    assert result["hit"] is True
    no_writes_have_w_cmd(fake)
    # kontrola negatywna: no_writes_have_w_cmd faktycznie potrafi wykryc 'W'
    bad = FakeSerial()
    bad.writes.append(build_frame(BIP_SOM_NOACK, 1, b"W" + b"\x00" * 4))
    with pytest.raises(AssertionError):
        no_writes_have_w_cmd(bad)


# ---------------------------------------------------------------------------
# 5) odbior rozlozony na dwa read()
# ---------------------------------------------------------------------------
def test_read_for_assembles_response_split_across_two_reads():
    frame = build_frame(BIP_SOM_NOACK, 7, bytes([BIP_CMD_READ_RESPONSE, 0x00]) + struct.pack("<i", 99))
    assert len(frame) > 2
    split_at = len(frame) // 2
    fake = FakeSerial()
    fake.queue(frame[:split_at])
    fake.queue(frame[split_at:])

    raw = bip_probe.read_for(fake, seconds=0.08, poll_s=0.01)
    assert raw == frame

    frames, rest = parse_frames(raw)
    assert rest == b""
    assert len(frames) == 1
    som, ci, data = frames[0]
    assert ci == 7
    assert data[0] == BIP_CMD_READ_RESPONSE
    assert data[1] == 0x00
    assert struct.unpack_from("<i", data[2:])[0] == 99


def test_probe_binary_decodes_version_split_across_reads():
    version_resp = build_frame(BIP_SOM_NOACK, 3, bytes([BIP_CMD_READ_RESPONSE, 0x00]) + struct.pack("<i", 7))
    split_at = len(version_resp) // 2

    class SplitFakeSerial(FakeSerial):
        def write(self, data):
            data = bytes(data)
            self.writes.append(data)
            frames, _ = parse_frames(data)
            if any(f[2][:2] == bytes([BIP_CMD_READ, 0x00]) for f in frames):
                self.queue(version_resp[:split_at])
                self.queue(version_resp[split_at:])
            return len(data)

    fake = SplitFakeSerial()
    result = bip_probe.probe_binary(fake, seconds=0.08)
    assert result["version"] == 7
    no_writes_have_w_cmd(fake)


# ---------------------------------------------------------------------------
# drobiazgi (hexdump, podsumowanie/rekomendacja)
# ---------------------------------------------------------------------------
def test_hexdump_limits_and_formats():
    assert bip_probe.hexdump(b"") == "(brak)"
    assert bip_probe.hexdump(bytes([0, 255, 16])) == "00 ff 10"
    long = bytes(range(40))
    dumped = bip_probe.hexdump(long, limit=32)
    assert dumped.endswith("...")
    assert dumped.count(" ") >= 31


def test_build_summary_recommends_bipropellant_on_binary_hit():
    fake = _binary_fake()
    result = bip_probe.probe_baud("COMX", 38400, 0.02, factory_for(fake), binary_only=True)
    lines = bip_probe.build_summary([result])
    assert any("bipropellant" in line and "38400" in line for line in lines)


def test_build_summary_stays_xiao_on_total_silence():
    fake = FakeSerial()
    result = bip_probe.probe_baud("COMX", 115200, 0.02, factory_for(fake))
    lines = bip_probe.build_summary([result])
    assert any("xiao" in line for line in lines)
    assert not any("driver = \"bipropellant\"" in line for line in lines)
