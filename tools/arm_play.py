"""Odtwarza nagrany ruch ramienia (motions/<name>.json).

Uzycie:
    python tools/arm_play.py --motion grasp_mid --dry-run          # bez sprzetu, wypisuje waypointy
    python tools/arm_play.py --motion grasp_mid --port /dev/robot-arm
    python tools/arm_play.py --motion drop_box --home-first
    python tools/arm_play.py --motion grasp_mid --driver subprocess  # przez cfg.arm.subprocess_cmd

Wynik replay(): True = chwytak cos trzyma, False = zamknal sie na niczym
(reszta ruchu pominieta, chwytak otwarty), None = brak informacji.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from pinecone_bot.arm import format_motion, load_motion, make_arm  # noqa: E402
from pinecone_bot.config import Config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--motion", required=True, help="nazwa ruchu (plik motions/<name>.json)")
    parser.add_argument("--port", default=None, help="domyslnie cfg.arm.port")
    parser.add_argument("--id", default=None, help="domyslnie cfg.arm.arm_id")
    parser.add_argument("--motions-dir", default=None, help="domyslnie cfg.arm.motions_dir")
    parser.add_argument("--driver", default="waypoints", choices=["waypoints", "subprocess", "sim"])
    parser.add_argument("--rate", type=float, default=30.0, help="komend/s podczas interpolacji")
    parser.add_argument("--home-first", action="store_true", help="najpierw home(), potem ruch")
    parser.add_argument("--home-after", action="store_true", help="po ruchu home()")
    parser.add_argument("--dry-run", action="store_true", help="tylko wypisz waypointy, bez sprzetu")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    cfg = Config.load()
    cfg.arm.driver = args.driver
    if args.port:
        cfg.arm.port = args.port
    if args.id:
        cfg.arm.arm_id = args.id
    if args.motions_dir:
        cfg.arm.motions_dir = args.motions_dir

    motion = load_motion(cfg.arm.motions_dir, args.motion)
    print(format_motion(motion))
    if args.dry_run:
        return 0

    kw = {"rate_hz": args.rate} if args.driver == "waypoints" else {}
    arm = make_arm(cfg, **kw)
    try:
        if args.home_first:
            print("home()...")
            arm.home()
        result = arm.replay(args.motion)
        print(f"replay('{args.motion}') -> {result}")
        if args.home_after:
            print("home()...")
            arm.home()
    finally:
        arm.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
