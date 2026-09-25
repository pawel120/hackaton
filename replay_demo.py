"""Odtwarza chwyt na podstawie recznej demonstracji (demo.csv z record_demo.py).

NIEAKTUALNE od 2026-09-25: WAYPOINTS sa sprzed fix_shoulder_offset.py (zla
kalibracja barku/lokcia) i pojada zle. Uzywaj replay_csv.py demo2_fixed.csv.

Zapasowa sciezka obok approach_and_grasp.py (IK): bierze
kilka kluczowych punktow WPROST z ruchu, ktory czlowiek fizycznie wykonal
recznie (torque off), i odtwarza je bezposrednimi komendami (bez interpolacji -
patrz PROGRESS.md, interpolacja + duze skoki zapycha magistrale Feetech).

Dziala tylko dla TEJ SAMEJ pozycji szyszki (ta sama platforma, ten sam punkt
na podlodze) co podczas nagrywania - to odtworzenie trasy, nie ogolny chwyt.

Uzycie:
    python replay_demo.py --port /dev/robot-arm
    python replay_demo.py --port /dev/robot-arm --dry-run
"""

from __future__ import annotations

import argparse
import time

import arm_control as ac

# Punkty z demo.csv (nagranie reczne 2026-09-25), shoulder_lift/elbow_flex juz
# po korekcie zamienionych ID serw (patrz PROGRESS.md). Kolejnosc: home -> siegniecie
# w strone szyszki (elbow_flex blisko minimum = najdalszy wysieg) -> zamkniecie
# chwytaka na szyszce -> powrot do home z zaciśnietym chwytakiem.
WAYPOINTS = [
    ("start (home)", {
        "shoulder_pan": -0.13, "shoulder_lift": 96.75, "elbow_flex": 152.31,
        "wrist_flex": -101.41, "wrist_roll": 89.27, "gripper": 1.11,
    }),
    ("wysiegniecie nad szyszka", {
        "shoulder_pan": -8.22, "shoulder_lift": 34.95, "elbow_flex": -62.11,
        "wrist_flex": -13.05, "wrist_roll": 89.45, "gripper": 30.0,
    }),
    ("max wysiegniecie / zacisk", {
        "shoulder_pan": -6.20, "shoulder_lift": -5.49, "elbow_flex": -95.52,
        "wrist_flex": 12.79, "wrist_roll": 89.71, "gripper": 12.0,
    }),
    ("powrot do home z szyszka", {
        "shoulder_pan": -0.13, "shoulder_lift": 96.75, "elbow_flex": 152.31,
        "wrist_flex": -101.41, "wrist_roll": 89.27, "gripper": 15.0,
    }),
]


def send_and_wait(arm, target: dict, dry_run: bool, retries: int = 4, tol: float = 4.0) -> None:
    if dry_run:
        print(f"  [dry-run] {target}")
        return
    action = {f"{k}.pos": v for k, v in target.items()}
    for attempt in range(retries):
        arm.send_action(action)
        time.sleep(1.5)
        current = ac.read_joint_positions(arm)
        close_enough = all(abs(current.get(name, val) - val) < tol for name, val in target.items())
        print(f"  proba {attempt + 1}: {current}")
        if close_enough:
            print("  -> osiagniete")
            return
    print("  UWAGA: nie osiagnieto pelnej zbieznosci po", retries, "probach, jade dalej")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", required=True)
    parser.add_argument("--id", default="so101")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        for label, target in WAYPOINTS:
            print(f"KROK: {label}")
            send_and_wait(None, target, True)
        return

    arm = ac.make_arm(port=args.port, arm_id=args.id, max_relative_target=None)
    arm.connect(calibrate=False)
    try:
        for label, target in WAYPOINTS:
            print(f"\nKROK: {label}")
            send_and_wait(arm, target, False)
    finally:
        arm.disconnect()
    print("\nSekwencja wykonana.")


if __name__ == "__main__":
    main()
