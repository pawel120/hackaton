"""Nagrywa ruch ramienia jako liste WAYPOINTOW (motions/<name>.json).

Wymaga lerobot (uruchamiac na Pi). Przebieg:
  1. Ramie jedzie do home (z torque).
  2. Torque wylaczony - ramie mozna swobodnie ustawiac reka.
  3. Petla: ustaw ramie, Enter, podaj etykiete (hover/down/close/lift/...),
     czas dojazdu [s] i czy to krok sprawdzajacy chwytak. Biezaca pozycja
     (get_observation) trafia na liste.
  4. 'q' zapisuje plik i wlacza torque z powrotem.

Uzycie (na Pi):
    python tools/record_waypoints.py --name grasp_mid --port /dev/robot-arm
    python tools/record_waypoints.py --name drop_box --note "pojemnik po lewej"

WAZNE: waypointy sa w stopniach lerobot, czyli wzgledem kalibracji serw.
Po KAZDEJ zmianie kalibracji (lerobot calibrate, fix_shoulder_offset.py,
zmiana Homing_Offset) ruch trzeba nagrac od nowa - przeliczanie starych
nagran (jak demo2_fixed.csv) to zrodlo bledow.
"""
from __future__ import annotations

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from pinecone_bot.arm import JOINT_NAMES, Motion, Waypoint, WaypointArm, format_motion, motion_path, save_motion  # noqa: E402
from pinecone_bot.config import Config  # noqa: E402

CALIBRATION_REMINDER = (
    "PAMIETAJ: waypointy zaleza od kalibracji serw. Po kazdej zmianie kalibracji\n"
    "(lerobot calibrate, fix_shoulder_offset.py, Homing_Offset) nagraj ruch od nowa."
)


def ask(prompt: str, default: str = "") -> str:
    raw = input(f"{prompt} [{default}]: " if default else f"{prompt}: ").strip()
    return raw or default


def ask_float(prompt: str, default: float) -> float:
    while True:
        raw = ask(prompt, str(default))
        try:
            return float(raw)
        except ValueError:
            print("  podaj liczbe")


def ask_yes(prompt: str, default: bool = False) -> bool:
    raw = ask(prompt, "y" if default else "n").lower()
    return raw in ("y", "yes", "t", "tak")


def record_loop(arm_ctl, read_pose) -> list:
    """Petla interaktywna. arm_ctl = WaypointArm (do home), read_pose() -> dict."""
    waypoints: list = []
    print("\nUstaw ramie reka i nacisnij Enter, zeby dodac waypoint. 'q' + Enter konczy,")
    print("'d' + Enter usuwa ostatni, 'p' + Enter wypisuje biezaca pozycje.\n")
    while True:
        cmd = input(f"[{len(waypoints)} waypointow] Enter=dodaj, p=pozycja, d=usun ostatni, q=zapisz: ").strip().lower()
        if cmd == "q":
            return waypoints
        if cmd == "d":
            if waypoints:
                removed = waypoints.pop()
                print(f"  usunieto '{removed.label}'")
            continue
        pose = read_pose()
        if pose is None or any(j not in pose for j in JOINT_NAMES):
            print("  odczyt pozycji nieudany, sprobuj jeszcze raz")
            continue
        print("  pozycja: " + " ".join(f"{j}={pose[j]:.1f}" for j in JOINT_NAMES))
        if cmd == "p":
            continue
        label = ask("etykieta (hover/down/close/lift/...)", f"wp{len(waypoints)}")
        seconds = ask_float("czas dojazdu [s]", 1.5)
        check = ask_yes("krok sprawdzajacy chwytak (check_gripper)?", label.lower() in ("close", "zacisk", "grasp"))
        if check:
            # Nagrana wartosc chwytaka to szerokosc szyszki w dloni, nie komenda zacisku.
            # Cel ponizej empty_gripper_below sprawia, ze serwo sciska, a odczyt
            # ponizej progu oznacza pusty chwytak (PROGRESS.md: ~2 = pusto).
            pose["gripper"] = ask_float("cel gripper dla zacisku (0 = pelne zamkniecie)", 0.0)
        waypoints.append(Waypoint(label=label, pose=pose, seconds=seconds, check_gripper=check))
        print(f"  dodano '{label}' ({seconds:.1f} s{', check_gripper' if check else ''})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True, help="nazwa ruchu -> motions/<name>.json")
    parser.add_argument("--port", default=None, help="domyslnie cfg.arm.port")
    parser.add_argument("--id", default=None, help="domyslnie cfg.arm.arm_id")
    parser.add_argument("--motions-dir", default=None, help="domyslnie cfg.arm.motions_dir")
    parser.add_argument("--note", default="", help="opis: gdzie lezala szyszka, data, stan kalibracji")
    parser.add_argument("--no-home", action="store_true", help="nie jedz do home przed nagrywaniem")
    args = parser.parse_args()

    cfg = Config.load()
    if args.port:
        cfg.arm.port = args.port
    if args.id:
        cfg.arm.arm_id = args.id
    if args.motions_dir:
        cfg.arm.motions_dir = args.motions_dir

    path = motion_path(cfg.arm.motions_dir, args.name)
    if os.path.exists(path) and not ask_yes(f"{path} istnieje, nadpisac?", False):
        print("przerwano")
        return

    print(CALIBRATION_REMINDER)
    import arm_control as ac  # lerobot - tylko na Pi

    arm = ac.make_arm(port=cfg.arm.port, arm_id=cfg.arm.arm_id, max_relative_target=None)
    arm.connect(calibrate=False)
    ctl = WaypointArm(cfg, arm=arm)
    try:
        if not args.no_home:
            print("Jade do home...")
            ctl.home()
        print("HOME:", ac.read_joint_positions(arm))
        print("Wylaczam torque - mozesz recznie przesuwac ramie.")
        arm.bus.disable_torque()  # jak record_demo.py
        waypoints = record_loop(ctl, lambda: ctl._read_pose())
    finally:
        print("Wlaczam torque z powrotem...")
        try:
            arm.bus.enable_torque()
        finally:
            arm.disconnect()

    if not waypoints:
        print("brak waypointow, nic nie zapisano")
        return
    motion = Motion(name=args.name, waypoints=waypoints, note=args.note)
    out = save_motion(cfg.arm.motions_dir, motion)
    print(f"\nZapisano {out}")
    print(format_motion(motion))
    print("\nOdtworzenie: python tools/arm_play.py --motion", args.name)
    print(CALIBRATION_REMINDER)


if __name__ == "__main__":
    main()
