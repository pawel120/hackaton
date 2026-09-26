"""
Sonda protokolu plyty hoverboarda - jeden strzal, bez czlowieka w minicomie.

Odpowiada na pytanie: czy plyta glowna hoverboarda gada firmwarem
bipropellant-hoverboard-firmware (protokol binarny albo tryb ASCII), na
jakim baudzie, i czy oddaje dane z hallotronow. Nie zaklada nic o wyniku -
"cisza" jest rownie wazna odpowiedzia jak "odpowiedzial".

Dla kazdego baudu z listy (kolejnosc jak podana, domyslnie
"115200,9600,38400"; pierwsze trafienie konczy sondowanie, chyba ze --all):
  1. Otwarcie portu (timeout 0.2 s), oproznienie bufora wejsciowego, 0.5 s
     nasluchu na niesprowokowane bajty (niektore buildy pluja ASCII albo
     ramkami okresowymi) - liczba bajtow + hexdump pierwszych 32.
  2. Test ASCII (pomijany z --binary-only): "unlockASCII\\r\\n", 0.3 s
     pauzy, "?\\r\\n", zbieranie odpowiedzi przez --seconds. Wykryte, gdy
     odpowiedz zawiera jeden z markerow ("Options", "options", "?",
     "unlock") albo ma > 20 znakow drukowalnych. Potem "H\\r\\n" (odczyt
     hallotronow w trybie ASCII).
  3. Test binarny (pomijany z --ascii-only): ramki buduje/parsuje
     pinecone_bot.base (build_frame/parse_frames) - TEST ('T'+"ABCD",
     firmware ma odbic 't'+"ABCD") i READVAL wersji (kod 0x00). Osobno
     READVAL halla (kod 0x02) - przy odpowiedzi >= 72 bajtow payloadu
     dekoduje dwa HALL_DATA_STRUCT (BIP_HALL_STRUCT z base.py).

Ten test NIGDY nie wysyla komendy silnikow: zadnej ramki z cmd='W'
(BIP_CODE_SPEED) ani zadnego PWM. Tylko TEST i odczyty (R).

Uzycie:
    python tools/bip_probe.py --port /dev/ttyAMA0
    python tools/bip_probe.py --port /dev/ttyAMA0 --baud 115200,9600,38400 --seconds 2.0
    python tools/bip_probe.py --port /dev/ttyAMA0 --binary-only --dump probe.log

Kod wyjscia: 0, jesli cokolwiek odpowiedzialo (ASCII lub binarnie) na
ktoryms baudzie; 2, jesli cisza na wszystkich baudach.
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
import time
from datetime import datetime
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pinecone_bot.base import (  # noqa: E402
    BIP_CMD_ACK,
    BIP_CMD_READ,
    BIP_CMD_READ_RESPONSE,
    BIP_CMD_WRITE,
    BIP_CMD_WRITE_RESPONSE,
    BIP_CODE_HALL,
    BIP_HALL_MM_INDEX,
    BIP_HALL_STRUCT,
    BIP_LEFT,
    BIP_RIGHT,
    BIP_SOM_ACK,
    build_frame,
    parse_frames,
)

# indeks HallSpeed_mm_per_s w krotce BIP_HALL_STRUCT (patrz komentarz w base.py
# przy BIP_HALL_STRUCT: HallPosn, HallSpeed, HallPosnMultiplier, HallPosn_lastread,
# HallPosn_mm, HallPosn_mm_lastread, HallSpeed_mm_per_s, HallTimeDiff, HallSkipped)
BIP_HALL_SPEED_INDEX = 6

# PROTOCOL_CMD_TEST z bipropellant-hoverboard-firmware: 'T' -> firmware odbija 't'
# z tym samym payloadem. Nie ma go w base.py (nie jest uzywany przez BipropellantBase),
# wiec definiujemy lokalnie. ZALOZENIE DO SPRAWDZENIA na sprzecie zespolu.
BIP_CMD_TEST = ord("T")
BIP_CMD_TESTRESPONSE = ord("t")

# Komendy, po ktorych drugi bajt danych to "kod" (R/W/r/w) - reszta to payload
# wprost po cmd (np. 'A', 'N', 't').
_CODE_BEARING_CMDS = (BIP_CMD_READ, BIP_CMD_WRITE, BIP_CMD_READ_RESPONSE, BIP_CMD_WRITE_RESPONSE)

UNSOLICITED_WAIT_S = 0.5
ASCII_UNLOCK_WAIT_S = 0.3
ASCII_MARKERS = ("Options", "options", "?", "unlock")
ASCII_MIN_PRINTABLE = 20

SILENCE_HINTS = [
    "zle piny UART / zamienione RX-TX (skrzyzuj recznie i sprobuj jeszcze raz)",
    "zle zlacze - sideboard moze gadac po USART2 a nie USART3 (albo odwrotnie)",
    "brak/zly konwerter poziomow (plyta hoverboarda to zwykle 3.3 V albo 5 V UART, nie RS232)",
    "firmware zbudowany bez INCLUDE_PROTOCOL - wtedy plyta fizycznie nie odpowie",
    "nowsza wersja protokolu z ramkowaniem COBS - inny uklad ramki niz w base.py (patrz komentarz przy BIP_SOM_ACK)",
]


def _default_serial_factory(port: str, baud: int):
    import serial  # pyserial, importowane leniwie zeby testy nie wymagaly sprzetu/portu
    return serial.Serial(port, baud, timeout=0.2)


def hexdump(data: bytes, limit: int = 32) -> str:
    chunk = bytes(data)[:limit]
    if not chunk:
        return "(brak)"
    text = " ".join("%02x" % b for b in chunk)
    if len(data) > limit:
        text += " ..."
    return text


def read_for(ser, seconds: float, poll_s: float = 0.02, chunk: int = 512) -> bytes:
    """Zbiera bajty z portu przez `seconds` (rzeczywisty uplyw czasu)."""
    out = bytearray()
    deadline = time.monotonic() + max(0.0, seconds)
    while True:
        waiting = getattr(ser, "in_waiting", None)
        if waiting is None:
            data = ser.read(chunk)
        else:
            data = ser.read(int(waiting)) if waiting > 0 else b""
        if data:
            out += data
        if time.monotonic() >= deadline:
            break
        time.sleep(poll_s)
    return bytes(out)


def flush_input(ser) -> None:
    try:
        ser.reset_input_buffer()
    except Exception:  # noqa: BLE001
        pass
    try:
        waiting = getattr(ser, "in_waiting", 0) or 0
        if waiting:
            ser.read(int(waiting))
    except Exception:  # noqa: BLE001
        pass


def append_dump(path: str, baud: int, label: str, data: bytes) -> None:
    if not path or not data:
        return
    stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    line = "%s baud=%d %s: %s\n" % (stamp, baud, label, hexdump(data, limit=len(data)))
    with open(path, "a", encoding="ascii") as f:
        f.write(line)


# ---------------------------------------------------------------------------
# krok 1: niesprowokowane bajty
# ---------------------------------------------------------------------------
def probe_unsolicited(ser) -> dict:
    data = read_for(ser, UNSOLICITED_WAIT_S)
    return {"raw": data, "count": len(data), "hexdump": hexdump(data, limit=32)}


# ---------------------------------------------------------------------------
# krok 2: ASCII
# ---------------------------------------------------------------------------
def probe_ascii(ser, seconds: float) -> dict:
    ser.write(b"unlockASCII\r\n")
    time.sleep(ASCII_UNLOCK_WAIT_S)
    ser.write(b"?\r\n")
    raw = read_for(ser, seconds)
    text = raw.decode("ascii", errors="replace")
    printable = "".join(ch for ch in text if ch.isprintable())
    detected = any(marker in text for marker in ASCII_MARKERS) or len(printable) > ASCII_MIN_PRINTABLE

    ser.write(b"H\r\n")
    hall_raw = read_for(ser, seconds)
    hall_text = hall_raw.decode("ascii", errors="replace")

    return {
        "detected": detected,
        "raw": raw,
        "lines": text.splitlines()[:15],
        "hall_raw": hall_raw,
        "hall_text": hall_text,
    }


# ---------------------------------------------------------------------------
# krok 3: binarny
# ---------------------------------------------------------------------------
def format_frame(som: int, ci: int, data: bytes) -> str:
    if not data:
        return "som=0x%02x ci=%d (puste dane)" % (som, ci)
    cmd_byte = data[0]
    cmd_str = chr(cmd_byte) if 32 <= cmd_byte < 127 else ("0x%02x" % cmd_byte)
    if cmd_byte in _CODE_BEARING_CMDS and len(data) >= 2:
        code_str = "0x%02x" % data[1]
        payload = data[2:]
    else:
        code_str = "-"
        payload = data[1:]
    return "som=0x%02x ci=%d cmd=%s code=%s payload=%s" % (som, ci, cmd_str, code_str, hexdump(payload, limit=64))


def _next_ci(state: list) -> int:
    state[0] = (state[0] + 1) & 0xFF
    return state[0]


def probe_binary(ser, seconds: float) -> dict:
    ci_state = [0]

    # TEST + READVAL wersji (kod 0x00) w jednej rundzie - zadna z tych ramek
    # nie rusza silnikow (cmd 'T' i 'R', nigdy 'W').
    ser.write(build_frame(BIP_SOM_ACK, _next_ci(ci_state), bytes([BIP_CMD_TEST]) + b"ABCD"))
    ser.write(build_frame(BIP_SOM_ACK, _next_ci(ci_state), bytes([BIP_CMD_READ, 0x00])))
    raw1 = read_for(ser, seconds)
    frames1, _ = parse_frames(raw1)

    ack = False
    test_response: Optional[bytes] = None
    version: Optional[int] = None
    for som, ci, data in frames1:
        if data == bytes([BIP_CMD_ACK]):
            ack = True
        elif data[:1] == bytes([BIP_CMD_TESTRESPONSE]):
            test_response = data[1:]
        elif len(data) >= 2 and data[0] == BIP_CMD_READ_RESPONSE and data[1] == 0x00:
            payload = data[2:]
            if len(payload) >= 4:
                version = struct.unpack_from("<i", payload)[0]

    # READVAL halla (kod 0x02) - osobna runda, tez tylko odczyt.
    ser.write(build_frame(BIP_SOM_ACK, _next_ci(ci_state), bytes([BIP_CMD_READ, BIP_CODE_HALL])))
    raw2 = read_for(ser, seconds)
    frames2, _ = parse_frames(raw2)

    hall: Optional[tuple] = None
    for som, ci, data in frames2:
        if len(data) >= 2 and data[0] == BIP_CMD_READ_RESPONSE and data[1] == BIP_CODE_HALL:
            payload = data[2:]
            if len(payload) >= 2 * BIP_HALL_STRUCT.size:
                h0 = BIP_HALL_STRUCT.unpack_from(payload, 0)
                h1 = BIP_HALL_STRUCT.unpack_from(payload, BIP_HALL_STRUCT.size)
                hall = (h0, h1)

    return {
        "frames": frames1 + frames2,
        "ack": ack,
        "test_response": test_response,
        "version": version,
        "hall": hall,
        "raw1": raw1,
        "raw2": raw2,
    }


def _binary_hit(binary_result: Optional[dict]) -> bool:
    if not binary_result:
        return False
    return bool(
        binary_result["ack"]
        or binary_result["test_response"] is not None
        or binary_result["version"] is not None
        or binary_result["hall"] is not None
    )


# ---------------------------------------------------------------------------
# jeden baud
# ---------------------------------------------------------------------------
def probe_baud(port: str, baud: int, seconds: float, serial_factory,
                ascii_only: bool = False, binary_only: bool = False,
                dump_path: Optional[str] = None) -> dict:
    ser = serial_factory(port, baud)
    try:
        flush_input(ser)
        unsolicited = probe_unsolicited(ser)
        append_dump(dump_path, baud, "niesprowokowane", unsolicited["raw"])

        ascii_result = None
        if not binary_only:
            ascii_result = probe_ascii(ser, seconds)
            append_dump(dump_path, baud, "ascii ?", ascii_result["raw"])
            append_dump(dump_path, baud, "ascii H", ascii_result["hall_raw"])

        binary_result = None
        if not ascii_only:
            binary_result = probe_binary(ser, seconds)
            append_dump(dump_path, baud, "binarny test+wersja", binary_result["raw1"])
            append_dump(dump_path, baud, "binarny hall", binary_result["raw2"])
    finally:
        try:
            ser.close()
        except Exception:  # noqa: BLE001
            pass

    hit = bool(ascii_result and ascii_result["detected"]) or _binary_hit(binary_result)
    return {
        "baud": baud,
        "unsolicited": unsolicited,
        "ascii": ascii_result,
        "binary": binary_result,
        "hit": hit,
    }


def verdict_line(result: dict) -> str:
    baud = result["baud"]
    ascii_result = result["ascii"]
    binary_result = result["binary"]
    ascii_str = "TAK" if (ascii_result and ascii_result["detected"]) else "NIE"
    if binary_result is None:
        detail = "ack=NIE test=NIE version=NIE hall=NIE"
        binary_str = "NIE"
    else:
        ack = binary_result["ack"]
        test = binary_result["test_response"] is not None
        version = binary_result["version"]
        hall = binary_result["hall"] is not None
        detail = "ack=%s test=%s version=%s hall=%s" % (
            "TAK" if ack else "NIE",
            "TAK" if test else "NIE",
            str(version) if version is not None else "NIE",
            "TAK" if hall else "NIE",
        )
        binary_str = "TAK" if _binary_hit(binary_result) else "NIE"
    return "%d: ASCII %s, binarny %s (%s), smieci: %d bajtow" % (
        baud, ascii_str, binary_str, detail, result["unsolicited"]["count"])


# ---------------------------------------------------------------------------
# wiele baudow + rekomendacja
# ---------------------------------------------------------------------------
def run_probe(port: str, bauds: list, seconds: float, serial_factory=None,
              ascii_only: bool = False, binary_only: bool = False,
              all_bauds: bool = False, dump_path: Optional[str] = None) -> tuple:
    factory = serial_factory or _default_serial_factory
    results = []
    for baud in bauds:
        result = probe_baud(port, baud, seconds, factory,
                             ascii_only=ascii_only, binary_only=binary_only, dump_path=dump_path)
        results.append(result)
        if result["hit"] and not all_bauds:
            break
    exit_code = 0 if any(r["hit"] for r in results) else 2
    return results, exit_code


def build_summary(results: list) -> list:
    lines = []
    binary_hit_result = next((r for r in results if _binary_hit(r["binary"])), None)
    ascii_hit_result = next((r for r in results if r["ascii"] and r["ascii"]["detected"]), None)
    if binary_hit_result is not None:
        baud = binary_hit_result["baud"]
        lines.append("Rekomendacja: cfg.base.driver = \"bipropellant\", cfg.base.baud = %d." % baud)
        lines.append("W pinecone_config.json, sekcja \"base\": zmien \"driver\": \"xiao\" na "
                      "\"driver\": \"bipropellant\" i \"baud\": %d (bylo 115200)." % baud)
    else:
        lines.append("Rekomendacja: zostaw cfg.base.driver = \"xiao\" - protokol binarny bipropellant nie odpowiedzial.")
        if ascii_hit_result is not None:
            lines.append("Plyta odpowiada w trybie ASCII na baudzie %d, ale to nie jest protokol, ktorego "
                          "uzywa BipropellantBase - bez odpowiedzi binarnej sterownik 'bipropellant' nie ruszy."
                          % ascii_hit_result["baud"])
    return lines


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_result(result: dict) -> None:
    print(verdict_line(result))
    ascii_result = result["ascii"]
    if ascii_result and ascii_result["detected"]:
        print("  ASCII menu (pierwsze linie):")
        for line in ascii_result["lines"]:
            print("    " + line)
        if ascii_result["hall_text"].strip():
            print("  ASCII H (odczyt hallotronow):")
            for line in ascii_result["hall_text"].splitlines()[:15]:
                print("    " + line)
    binary_result = result["binary"]
    if binary_result:
        for som, ci, data in binary_result["frames"]:
            print("  ramka: " + format_frame(som, ci, data))
        if binary_result["hall"] is not None:
            h0, h1 = binary_result["hall"]
            print("  hall lewe:  HallPosn_mm=%d HallSpeed_mm_per_s=%d" % (
                h0[BIP_HALL_MM_INDEX], h0[BIP_HALL_SPEED_INDEX]))
            print("  hall prawe: HallPosn_mm=%d HallSpeed_mm_per_s=%d" % (
                h1[BIP_HALL_MM_INDEX], h1[BIP_HALL_SPEED_INDEX]))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", required=True, help="port szeregowy, np. /dev/ttyAMA0")
    parser.add_argument("--baud", default="115200,9600,38400", help="lista baudow po przecinku, w kolejnosci prob")
    parser.add_argument("--seconds", type=float, default=2.0, help="czas zbierania odpowiedzi na kazdy test [s]")
    parser.add_argument("--binary-only", action="store_true", help="pomin test ASCII")
    parser.add_argument("--ascii-only", action="store_true", help="pomin test binarny")
    parser.add_argument("--all", action="store_true", help="testuj wszystkie baudy, nie przerywaj po pierwszym trafieniu")
    parser.add_argument("--dump", help="plik, do ktorego dopisac surowe bajty RX (timestamp + baud)")
    args = parser.parse_args(argv)

    if args.binary_only and args.ascii_only:
        parser.error("--binary-only i --ascii-only wykluczaja sie nawzajem")

    try:
        bauds = [int(b.strip()) for b in args.baud.split(",") if b.strip()]
    except ValueError:
        parser.error("--baud musi byc lista liczb po przecinku, np. 115200,9600")
        return 2
    if not bauds:
        parser.error("--baud: pusta lista")
        return 2

    print("Ten test nie rusza silnikow.")
    print("Sonda protokolu bipropellant/ASCII: port=%s baudy=%s" % (args.port, bauds))

    results, exit_code = run_probe(
        args.port, bauds, args.seconds,
        ascii_only=args.ascii_only, binary_only=args.binary_only,
        all_bauds=args.all, dump_path=args.dump,
    )

    for result in results:
        _print_result(result)

    print("")
    for line in build_summary(results):
        print(line)

    if exit_code == 2:
        print("")
        print("Brak odpowiedzi na zadnym baudzie. Podpowiedzi:")
        for hint in SILENCE_HINTS:
            print("  - " + hint)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
