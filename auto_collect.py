"""Krokowe podjezdzanie do szyszki (skan -> maly krok kolami -> skan...) i chwyt.

Nie uzywa drive_to_target.py (wymaga pakietu makarena, ktorego nie ma na tym
repo, i blokuje jazde bez zmierzonej kalibracji). Zamiast tego steruje kolami
bezposrednio przez drive_step.py (surowy protokol Xiao), male kroki, rescan po
kazdym - klasyczna petla wizyjna zamiast jazdy na oslep na duzym dystansie.

Kamera D415 nie widzi obiektow blizej ~0.31 m (martwa strefa), wiec petla
wizyjna dziala tylko do pewnego dystansu (VISIBLE_FLOOR_M z zapasem). Po niej
jeden krotki, "slepy" krok do finalnego standoffu - jego dlugosc liczona z
PRAWDZIWEJ predkosci zmierzonej wlasnie w tej sesji z poprzednich krokow
(dystans/czas), nie z domyslnych/zgadnietych stalych.

Kolejnosc: skan -> [korekta kierunku jesli trzeba] -> [krok naprzod -> skan] * N
           -> jeden krok slepy do standoffu -> approach_and_grasp.py (chwyt)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent
CEL_JSON = REPO_DIR / "cel.json"

VISIBLE_FLOOR_M = 0.35    # ponizej tego kamera zaczyna gubic szyszki (dead zone ~0.31 m)
FINAL_STANDOFF_M = 0.15   # ma zostac przed szyszka po dojezdzie, w zasiegu chwytaka
ANGLE_DEADBAND_DEG = 6.0  # ponizej tego kata nie korygujemy kierunku

FORWARD_SPEED_PWM = 150
FORWARD_STEP_S = 0.05     # zmierzone 2026-09-25 na dywanie: PWM 150 ~1 m/s, czyli ~5 cm na krok
STEER_PWM = 150
STEER_STEP_S = 0.12

DEFAULT_RATE_MPS = 1.0    # zmierzone: 0.470 -> 0.322 m w 0.15 s przy PWM 150
MAX_ITERS = 15
SETTLE_S = 0.6


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd))
    result = subprocess.run(cmd, cwd=REPO_DIR)
    if result.returncode != 0:
        raise SystemExit(f"Komenda nie powiodla sie (kod {result.returncode}): {' '.join(cmd)}")
    return result


def scan() -> dict | None:
    run([sys.executable, "scan_cones.py", "--json", str(CEL_JSON)])
    data = json.loads(CEL_JSON.read_text())
    targets = data.get("targets") or []
    return targets[0] if targets else None


def drive_step(port: str, speed: int, steer: int, duration: float, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] krok: speed={speed} steer={steer} czas={duration:.2f}s (BEZ RUCHU)")
        return
    run([
        sys.executable, "drive_step.py",
        "--port", port,
        "--speed", str(speed),
        "--steer", str(steer),
        "--duration", f"{duration:.3f}",
    ])
    time.sleep(SETTLE_S)


def grasp(standoff: float, port: str, dry_run: bool) -> None:
    cmd = [sys.executable, "approach_and_grasp.py", "--standoff", f"{standoff:.3f}", "--port", port]
    if dry_run:
        cmd.append("--dry-run")
    run(cmd)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--drive-port", required=True, help="port Xiao, np. /dev/robot-drive")
    parser.add_argument("--arm-port", required=True, help="port ramienia, np. /dev/robot-arm")
    parser.add_argument("--final-standoff", type=float, default=FINAL_STANDOFF_M)
    parser.add_argument("--visible-floor", type=float, default=VISIBLE_FLOOR_M)
    parser.add_argument("--forward-speed", type=int, default=FORWARD_SPEED_PWM)
    parser.add_argument("--forward-step", type=float, default=FORWARD_STEP_S, help="czas trwania jednego kroku naprzod [s]")
    parser.add_argument("--max-iters", type=int, default=MAX_ITERS)
    parser.add_argument("--dry-run", action="store_true", help="pokaz caly przebieg bez zadnego fizycznego ruchu")
    args = parser.parse_args()

    rate_samples: list[float] = []  # m/s zmierzone z (forward_before - forward_after) / czas kroku

    print("=== Skan startowy ===")
    target = scan()
    if target is None:
        raise SystemExit("Nie widac szyszki w kadrze. Ustaw ja przed kamera i sprobuj ponownie.")
    forward = float(target["forward_m"])
    bearing = float(target.get("bearing_deg", 0.0))
    print(f"Szyszka: do przodu {forward:.3f} m, kat {bearing:+.1f} st")

    for i in range(1, args.max_iters + 1):
        if forward <= args.visible_floor:
            print(f"\n=== Na granicy widocznosci ({forward:.3f} m <= {args.visible_floor} m) - koniec petli wizyjnej ===")
            break

        if abs(bearing) > ANGLE_DEADBAND_DEG:
            steer = STEER_PWM if bearing > 0 else -STEER_PWM
            print(f"\n--- Krok {i}: korekta kierunku {bearing:+.1f} st (steer {steer}) ---")
            drive_step(args.drive_port, 0, steer, STEER_STEP_S, args.dry_run)
        else:
            print(f"\n--- Krok {i}: naprzod ({forward:.3f} m do celu) ---")
            drive_step(args.drive_port, args.forward_speed, 0, args.forward_step, args.dry_run)

            if not args.dry_run:
                new_target = scan()
                if new_target is None:
                    print("Szyszka zniknela z kadru po kroku - zatrzymuje sie, sprawdz recznie.")
                    raise SystemExit(1)
                new_forward = float(new_target["forward_m"])
                delta = forward - new_forward
                if delta > 0.005:  # ponad 5 mm ruchu - wiarygodny pomiar
                    rate = delta / args.forward_step
                    rate_samples.append(rate)
                    print(f"Zmierzone: {delta*100:.1f} cm w {args.forward_step:.2f} s -> {rate:.3f} m/s")
                else:
                    print(f"Ruch niewykryty wyraznie (delta {delta*100:.1f} cm) - platforma mogla stac w miejscu (tarcie statyczne).")
                forward = new_forward
                bearing = float(new_target.get("bearing_deg", 0.0))
                print(f"Po kroku: do przodu {forward:.3f} m, kat {bearing:+.1f} st")
                continue

        # dry-run albo sam krok korekcyjny (bez rescanu) - rescan i tak, zeby petla mialiswiezy stan
        target = scan()
        if target is None:
            if args.dry_run:
                print("[dry-run] (symulacja - zaklada ze szyszka nadal widoczna)")
                continue
            raise SystemExit("Szyszka zniknela z kadru - zatrzymuje sie, sprawdz recznie.")
        forward = float(target["forward_m"])
        bearing = float(target.get("bearing_deg", 0.0))
    else:
        raise SystemExit(f"Nie udalo sie podjechac blisko w {args.max_iters} krokach.")

    avg_rate = (sum(rate_samples) / len(rate_samples)) if rate_samples else DEFAULT_RATE_MPS
    remaining = max(0.0, forward - args.final_standoff)
    blind_duration = remaining / avg_rate if avg_rate > 0 else 0.0
    blind_duration = min(blind_duration, 3.0)  # zabezpieczenie - nigdy dluzszy pojedynczy krok niz 3 s

    print(f"\n=== Krok koncowy (slepy): {remaining*100:.1f} cm przy {avg_rate:.3f} m/s -> {blind_duration:.2f} s ===")
    if rate_samples:
        print(f"(oparte na {len(rate_samples)} pomiarach z tej sesji, srednia {avg_rate:.3f} m/s)")
    else:
        print(f"(BRAK pomiarow - uzyto domyslnego zgadnietego {DEFAULT_RATE_MPS} m/s, sprawdz na oko)")

    drive_step(args.drive_port, args.forward_speed, 0, blind_duration, args.dry_run)

    print("\n=== Chwyt ===")
    grasp(args.final_standoff, args.arm_port, args.dry_run)


if __name__ == "__main__":
    main()
