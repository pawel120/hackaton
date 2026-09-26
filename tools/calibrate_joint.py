"""Kalibracja JEDNEGO stawu ramienia SO-101 (domyslnie shoulder_lift), bez `lerobot calibrate`.

`lerobot calibrate` nadpisuje wszystkie stawy (w tym reczne poprawki barku, docs/HARDWARE.md
pulapki 1 i 3). To narzedzie rusza tylko wybrany staw: Homing_Offset + limity pozycji w EEPROM
serwa i jego wpis w so101.json. Reszta pliku zostaje bez zmian, przed zapisem robiona jest kopia.

Uzycie (na Pi, z katalogu repo; nic innego nie moze trzymac portu - zatrzymaj tools/arm_web.py):
    python tools/calibrate_joint.py                    # tylko odczyt: rejestry serwa vs plik
    python tools/calibrate_joint.py --record 20        # torque OFF na stawie, 20 s: przeprowadz staw
                                                       # recznie przez CALY zakres; wypisuje propozycje
    python tools/calibrate_joint.py --record 20 --write   # j.w. + zapis (pyta o potwierdzenie "TAK")

UWAGA: --record zdejmuje torque ze stawu - ramie opadnie w tym stawie. Trzymaj je.

Model Feetech STS3215 (tak liczy lerobot): Present = Actual - Homing_Offset (mod 4096).
Nowy offset ustawia srodek nagranego zakresu na 2047, wiec zakres jest daleko od zera enkodera
(przejscie przez zero = serwo jedzie "naokolo", pulapka 3). Homing_Offset ma zakres +-2047.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

RESOLUTION = 4096
CENTER = 2047
MAX_OFFSET = 2047
# id jak w lerobot so_follower.py (pole "id" w JSON jest ignorowane, pulapka 2)
MOTOR_IDS = {"shoulder_pan": 1, "shoulder_lift": 2, "elbow_flex": 3, "wrist_flex": 4, "wrist_roll": 5, "gripper": 6}
CALIB_PATH = os.path.expanduser("~/.cache/huggingface/lerobot/calibration/robots/so_follower/so101.json")
MIN_SPAN = 200  # ponizej tego staw prawie nie byl ruszany - to nie jest zakres


def unwrap(samples: list) -> list:
    """Surowe Present (0..4095) -> ciagla sekwencja (przejscie 4095->0 nie robi skoku)."""
    out: list = []
    for raw in samples:
        if not out:
            out.append(float(raw))
            continue
        delta = (raw - out[-1]) % RESOLUTION
        if delta > RESOLUTION / 2:
            delta -= RESOLUTION
        out.append(out[-1] + delta)
    return out


def wrap_offset(value: float) -> int:
    """Offset do zakresu -2047..2047 (modulo 4096)."""
    v = int(round(value)) % RESOLUTION
    if v > MAX_OFFSET:
        v -= RESOLUTION
    return v


def propose(present_samples: list, old_offset: int) -> dict:
    """Z surowych Present nagranych przy starym offsecie liczy nowy offset i limity.

    Actual = Present + old_offset. Nowy offset H taki, ze srodek zakresu Actual - H = 2047.
    """
    if not present_samples:
        raise ValueError("brak probek")
    cont = unwrap(present_samples)
    lo_a, hi_a = min(cont) + old_offset, max(cont) + old_offset
    span = hi_a - lo_a
    if span < MIN_SPAN:
        raise ValueError(f"zakres tylko {span:.0f} krokow - staw prawie sie nie ruszal")
    if span >= RESOLUTION - 1:
        raise ValueError("zakres >= pelny obrot - nagranie niewiarygodne")
    new_offset = wrap_offset((lo_a + hi_a) / 2 - CENTER)
    # wrap_offset zmienia offset o wielokrotnosc 4096 - przesun przedzial tak,
    # zeby jego srodek w nowych jednostkach Present wypadl na 2047
    lo_p = lo_a - new_offset
    lo_p -= round(((lo_p + span / 2) - CENTER) / RESOLUTION) * RESOLUTION
    return {
        "homing_offset": new_offset,
        "range_min": int(round(lo_p)),
        "range_max": int(round(lo_p + span)),
        "span": int(round(span)),
    }


def deg_half_range(cal: dict) -> float:
    return (cal["range_max"] - cal["range_min"]) / 2 * 360.0 / (RESOLUTION - 1)


def present_to_deg(present: float, cal: dict) -> float:
    """Tak jak lerobot (DEGREES): (raw - srodek zakresu) * 360 / 4095."""
    return (present - (cal["range_min"] + cal["range_max"]) / 2) * 360.0 / (RESOLUTION - 1)


def load_calib(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_joint(path: str, joint: str, new: dict) -> str:
    """Zapisuje wpis jednego stawu (reszta pliku bez zmian). Zwraca sciezke kopii zapasowej."""
    calib = load_calib(path)
    backup = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(path, backup)
    entry = dict(calib[joint])
    entry.update({k: new[k] for k in ("homing_offset", "range_min", "range_max")})
    calib[joint] = entry
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(calib, fh, indent=4)
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--joint", default="shoulder_lift", choices=list(MOTOR_IDS))
    parser.add_argument("--port", default=os.environ.get("ROBOT_ARM_PORT", "/dev/robot-arm"))
    parser.add_argument("--calib", default=CALIB_PATH)
    parser.add_argument("--record", type=float, default=0.0, metavar="S",
                        help="nagraj zakres przez S sekund (torque OFF na stawie)")
    parser.add_argument("--write", action="store_true", help="po nagraniu zapisz EEPROM + JSON (pyta)")
    args = parser.parse_args()
    if args.write and args.record <= 0:
        parser.error("--write wymaga --record")

    from lerobot.motors import Motor, MotorNormMode  # lazy: lerobot tylko na Pi
    from lerobot.motors.feetech import FeetechMotorsBus

    joint = args.joint
    file_cal = load_calib(args.calib)[joint]
    bus = FeetechMotorsBus(args.port, {joint: Motor(MOTOR_IDS[joint], "sts3215", MotorNormMode.DEGREES)})
    bus.connect()
    try:
        def reg(name: str) -> int:
            return int(bus.read(name, joint, normalize=False))

        offset = reg("Homing_Offset")
        present = reg("Present_Position")
        lim = (reg("Min_Position_Limit"), reg("Max_Position_Limit"))
        print(f"{joint} (id {MOTOR_IDS[joint]})")
        print(f"  serwo: Homing_Offset {offset}, limity {lim[0]}..{lim[1]}, Present {present}")
        print(f"  plik:  homing_offset {file_cal['homing_offset']}, zakres {file_cal['range_min']}..{file_cal['range_max']}"
              f" (+-{deg_half_range(file_cal):.1f} st)")
        print(f"  kat wg pliku: {present_to_deg(present, file_cal):.1f} st")
        if offset != file_cal["homing_offset"] or lim != (file_cal["range_min"], file_cal["range_max"]):
            print("  !! rejestry serwa NIE zgadzaja sie z plikiem - lerobot liczy katy z pliku")
        if args.record <= 0:
            return 0

        print(f"\nTORQUE OFF na {joint} - TRZYMAJ RAMIE. Przez {args.record:.0f} s przeprowadz staw"
              " powoli przez CALY zakres (oba konce).")
        bus.disable_torque([joint])
        samples = []
        t_end = time.monotonic() + args.record
        while time.monotonic() < t_end:
            try:
                samples.append(reg("Present_Position"))
            except Exception as exc:  # noqa: BLE001 - pojedynczy zgubiony pakiet nie przerywa nagrania
                print(f"  (pominieto odczyt: {exc})")
            time.sleep(0.05)
        new = propose(samples, offset)
        new_cal = {**file_cal, **new}
        print(f"\nnagrano {len(samples)} probek, zakres {new['span']} krokow (+-{deg_half_range(new_cal):.1f} st)")
        print(f"  PROPOZYCJA: Homing_Offset {new['homing_offset']}, limity {new['range_min']}..{new['range_max']}")
        now_present = samples[-1] + offset - new["homing_offset"]
        print(f"  staw teraz bylby na {present_to_deg(now_present, new_cal):.1f} st")
        if not args.write:
            print("  (bez --write nic nie zapisano)")
            return 0
        if input("Zapisac do EEPROM serwa i do pliku kalibracji? wpisz TAK: ").strip() != "TAK":
            print("  nie zapisano")
            return 0
        bus.write("Homing_Offset", joint, new["homing_offset"], normalize=False)
        bus.write("Min_Position_Limit", joint, new["range_min"], normalize=False)
        bus.write("Max_Position_Limit", joint, new["range_max"], normalize=False)
        back = (reg("Homing_Offset"), reg("Min_Position_Limit"), reg("Max_Position_Limit"))
        print(f"  serwo po zapisie: offset {back[0]}, limity {back[1]}..{back[2]}")
        if back != (new["homing_offset"], new["range_min"], new["range_max"]):
            print("  !! odczyt po zapisie inny niz zapisany - plik NIE zmieniony")
            return 1
        backup = save_joint(args.calib, joint, new)
        print(f"  plik zapisany: {args.calib} (kopia: {backup})")
        print("  Po zmianie kalibracji spisz na nowo HOME_POSE i sprawdz motions/ (pulapka 12).")
        return 0
    finally:
        bus.disconnect(disable_torque=True)


if __name__ == "__main__":
    sys.exit(main())
