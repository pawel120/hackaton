"""Nagrywa pozycje przegubow, gdy CZLOWIEK recznie porusza ramieniem (torque off).

Uzycie (uruchamiac z katalogu glownego repo):
    python legacy/arm_recordings/record_demo.py --seconds 25 --out demo.csv

Kolejnosc:
  1. Ramie jedzie do HOME_POSE (z torque, normalnie).
  2. Torque wylaczony - ramie mozna swobodnie przesuwac reka.
  3. Przez --seconds sekund nagrywa pozycje wszystkich przegubow ~10x/s do CSV.
  4. Torque z powrotem wlaczony na koniec (ramie trzyma ostatnia pozycje).
"""

from __future__ import annotations

import argparse
import csv
import time

import os, sys; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import arm_control as ac


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seconds", type=float, default=25.0)
    parser.add_argument("--out", default="demo.csv")
    parser.add_argument("--rate", type=float, default=10.0, help="probek na sekunde")
    args = parser.parse_args()

    arm = ac.make_arm(max_relative_target=None)
    arm.connect(calibrate=False)
    try:
        print("Jade do HOME_POSE...")
        action = {f"{k}.pos": v for k, v in ac.HOME_POSE.items()}
        for _ in range(3):
            arm.send_action(action)
            time.sleep(1.5)
        print("HOME_POSE:", ac.read_joint_positions(arm))

        print("Wylaczam torque - mozesz teraz recznie przesuwac ramie.")
        arm.bus.disable_torque()

        rows = []
        t0 = time.monotonic()
        period = 1.0 / args.rate
        print(f"Nagrywam przez {args.seconds:.0f} s. START.")
        next_t = t0
        while True:
            now = time.monotonic()
            if now - t0 >= args.seconds:
                break
            if now >= next_t:
                pos = ac.read_joint_positions(arm)
                pos["t"] = now - t0
                rows.append(pos)
                next_t += period
            time.sleep(0.005)
        print("KONIEC nagrywania.")

        fieldnames = ["t"] + ac.JOINT_NAMES
        with open(args.out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        print(f"Zapisano {len(rows)} probek do {args.out}")

    finally:
        print("Wlaczam torque z powrotem...")
        arm.bus.enable_torque()
        arm.disconnect()


if __name__ == "__main__":
    main()
