"""Jednorazowa poprawka kalibracji barku/lokcia policzona z nagrania demo2.csv.

lerobot adresuje serwa po nazwie ze sztywnej listy (so_follower.py):
shoulder_lift = id2, elbow_flex = id3. Pole "id" w pliku kalibracji jest
IGNOROWANE - wczesniejsza "zamiana ID" w pliku zamienila tylko offsety/zakresy,
przez co oba przeguby byly liczone cudzym zakresem.

Kolumna shoulder_lift w demo2.csv = id2 (znormalizowany starym wpisem pliku:
zakres 1168..3423). Rozwinieta przez zero enkodera: Present -362..1621, wiec
id2 jezdzil "naokolo". Przesuniecie +1418 -> 1056..3039, srodek ~2047.
id2: offset -701 - 1418 = -2119 == 1977 (mod 4096, offset ma max +-2047).
id3 (elbow_flex) wraca do swoich rejestrow sprzed sesji: 1159, 1168..3423.

Robi tez demo2_fixed.csv - demo2.csv przeliczone do nowej kalibracji.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus

CALIB_PATH = Path.home() / ".cache/huggingface/lerobot/calibration/robots/so_follower/so101.json"
DEG_PER_TICK = 360 / 4095
SHIFT = 1418
OLD_SHOULDER_MID = (1168 + 3423) / 2
OLD_ELBOW_MID = (3 + 4094) / 2
SHOULDER = {"id": 2, "drive_mode": 0, "homing_offset": 1977, "range_min": 1006, "range_max": 3089}
ELBOW = {"id": 3, "drive_mode": 0, "homing_offset": 1159, "range_min": 1168, "range_max": 3423}


def mid(cal: dict) -> float:
    return (cal["range_min"] + cal["range_max"]) / 2


def shoulder_old_to_new(deg: float) -> float:
    present = OLD_SHOULDER_MID + deg / DEG_PER_TICK
    if present > 2500:  # po drugiej stronie zera enkodera
        present -= 4096
    return (present + SHIFT - mid(SHOULDER)) * DEG_PER_TICK


def elbow_old_to_new(deg: float) -> float:
    return deg + (OLD_ELBOW_MID - mid(ELBOW)) * DEG_PER_TICK


def main() -> None:
    motors = {
        "shoulder_lift": Motor(2, "sts3215", MotorNormMode.DEGREES),
        "elbow_flex": Motor(3, "sts3215", MotorNormMode.DEGREES),
    }
    bus = FeetechMotorsBus("/dev/robot-arm", motors)
    bus.connect()
    bus.disable_torque(list(motors))
    for name, cal in (("shoulder_lift", SHOULDER), ("elbow_flex", ELBOW)):
        bus.write("Homing_Offset", name, cal["homing_offset"])
        bus.write("Min_Position_Limit", name, cal["range_min"], normalize=False)
        bus.write("Max_Position_Limit", name, cal["range_max"], normalize=False)
        print(name, "id", motors[name].id,
              "offset", bus.read("Homing_Offset", name, normalize=False),
              "min", bus.read("Min_Position_Limit", name, normalize=False),
              "max", bus.read("Max_Position_Limit", name, normalize=False),
              "present", bus.read("Present_Position", name, normalize=False))
    bus.disconnect(disable_torque=True)

    calib = json.loads(CALIB_PATH.read_text())
    calib["shoulder_lift"] = SHOULDER
    calib["elbow_flex"] = ELBOW
    CALIB_PATH.write_text(json.dumps(calib, indent=4))
    print("Zapisano", CALIB_PATH)

    with open("demo2.csv") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["shoulder_lift"] = shoulder_old_to_new(float(r["shoulder_lift"]))
        r["elbow_flex"] = elbow_old_to_new(float(r["elbow_flex"]))
    with open("demo2_fixed.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for k in ("shoulder_lift", "elbow_flex"):
        print("demo2_fixed.csv", k, round(min(r[k] for r in rows), 1), "..", round(max(r[k] for r in rows), 1))


if __name__ == "__main__":
    main()
