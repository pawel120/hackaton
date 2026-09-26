"""Odtwarza nagranie z record_demo.py klatka po klatce, w tym samym tempie.

W odroznieniu od replay_demo.py (kilka recznie wybranych punktow) tu idzie
cala trajektoria z CSV (~10 klatek/s), wiec kazdy krok jest maly i serwo nie
wybiera "drogi naokolo". Najpierw powolny dojazd do pierwszej klatki.

Uzycie (na Pi, uruchamiac z katalogu glownego repo):
    python legacy/arm_recordings/replay_csv.py legacy/arm_recordings/demo2_fixed.csv --port /dev/robot-arm --start 4 --end 23
    python legacy/arm_recordings/replay_csv.py legacy/arm_recordings/demo2_fixed.csv --dry-run
"""

from __future__ import annotations

import argparse
import csv
import time

import os, sys; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import arm_control as ac


def load(path: str, start: float, end: float) -> list[dict]:
    with open(path) as f:
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]
    return [r for r in rows if start <= r["t"] <= end]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv")
    parser.add_argument("--port", default=None)
    parser.add_argument("--start", type=float, default=0.0, help="od ktorej sekundy nagrania")
    parser.add_argument("--end", type=float, default=1e9, help="do ktorej sekundy nagrania")
    parser.add_argument("--approach", type=float, default=3.0, help="czas dojazdu do 1. klatki [s]")
    parser.add_argument("--pause-at", type=float, default=None, help="zatrzymaj sie na klatce z tej sekundy nagrania")
    parser.add_argument("--pause", type=float, default=10.0, help="jak dlugo trzymac poze przy --pause-at [s]")
    parser.add_argument("--pan-offset", type=float, default=0.0,
                        help="dodaj do shoulder_pan w kazdej klatce [st] - obrot calego ruchu w bok")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    frames = load(args.csv, args.start, args.end)
    for fr in frames:
        fr["shoulder_pan"] += args.pan_offset
    print(f"{len(frames)} klatek, t={frames[0]['t']:.1f}..{frames[-1]['t']:.1f} s")
    first = {k: frames[0][k] for k in ac.JOINT_NAMES}
    print("Pierwsza klatka:", first)
    if args.dry_run:
        for fr in frames[::10]:
            print(f"  t={fr['t']:5.1f}", {k: round(fr[k], 1) for k in ac.JOINT_NAMES})
        return

    arm = ac.make_arm(port=args.port, max_relative_target=None)
    arm.connect(calibrate=False)
    try:
        current = ac.read_joint_positions(arm)
        print("Teraz:", current)
        steps = max(1, int(args.approach * 10))
        for i in range(1, steps + 1):
            a = i / steps
            arm.send_action({f"{k}.pos": current[k] + a * (first[k] - current[k]) for k in ac.JOINT_NAMES})
            time.sleep(args.approach / steps)
        time.sleep(1.0)
        print("Na 1. klatce:", ac.read_joint_positions(arm))

        t0 = time.monotonic()
        paused = args.pause_at is None
        for fr in frames:
            wait = (fr["t"] - frames[0]["t"]) - (time.monotonic() - t0)
            if wait > 0:
                time.sleep(wait)
            arm.send_action({f"{k}.pos": fr[k] for k in ac.JOINT_NAMES})
            if not paused and fr["t"] >= args.pause_at:
                paused = True
                time.sleep(0.8)
                print(f"PAUZA na t={fr['t']:.1f} przez {args.pause:.0f} s:", ac.read_joint_positions(arm), flush=True)
                time.sleep(args.pause)
                t0 += args.pause + 0.8
        time.sleep(1.5)
        print("Koniec:", ac.read_joint_positions(arm))
    finally:
        arm.disconnect()


if __name__ == "__main__":
    main()
