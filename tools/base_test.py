"""
Reczny test podwozia na sprzecie (xiao albo bipropellant).

    python tools/base_test.py --driver xiao --port /dev/robot-drive forward --seconds 2 --v 0.15
    python tools/base_test.py --driver bipropellant --port /dev/ttyAMA0 --baud 115200 turn --seconds 2 --w 0.5
    python tools/base_test.py --driver bipropellant --port /dev/ttyAMA0 square --side 1.0

Fazy sa czasowe (open-loop). Jesli sterownik ma odometrie (bipropellant),
drukuje ja co 0.5 s - to pozwala sprawdzic znaki kol i skretu bez pomiarow.
Konfiguracja: pinecone_bot.config.Config.load() (--config nadpisuje sciezke),
--driver/--port/--baud nadpisuja cfg.base.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pinecone_bot.base import make_base  # noqa: E402
from pinecone_bot.config import Config  # noqa: E402

ODOM_PRINT_S = 0.5
WARNING = (
    "UWAGA: robot zaraz ruszy w open-loop. Trzymaj reke na wylaczniku awaryjnym\n"
    "       (kill switch) i miej wolne 2 m wokol robota. Ctrl+C zatrzymuje."
)


def run_phase(base, name: str, v: float, w: float, seconds: float) -> None:
    print("[%s] v=%.3f m/s w=%.3f rad/s przez %.2f s" % (name, v, w, seconds))
    base.set_speed(v, w)
    t0 = time.monotonic()
    next_print = t0
    while True:
        now = time.monotonic()
        if now - t0 >= seconds:
            break
        if now >= next_print:
            odom = base.odometry()
            if odom is not None:
                x, y, th = odom
                print("   t=%5.2f  x=%.3f  y=%.3f  theta=%.1f deg" % (now - t0, x, y, math.degrees(th)))
            next_print += ODOM_PRINT_S
        time.sleep(0.02)
    base.stop()


def cmd_forward(base, args) -> None:
    run_phase(base, "forward", args.v, 0.0, args.seconds)


def cmd_turn(base, args) -> None:
    run_phase(base, "turn", 0.0, args.w, args.seconds)


def cmd_square(base, args) -> None:
    side_s = args.side / args.v
    turn_s = (math.pi / 2) / args.w
    for i in range(4):
        run_phase(base, "bok %d" % (i + 1), args.v, 0.0, side_s)
        time.sleep(args.pause)
        run_phase(base, "skret %d (w lewo)" % (i + 1), 0.0, args.w, turn_s)
        time.sleep(args.pause)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--driver", choices=["xiao", "bipropellant", "sim"], required=True)
    parser.add_argument("--port", help="port szeregowy, np. /dev/robot-drive lub /dev/ttyAMA0")
    parser.add_argument("--baud", type=int, help="domyslnie cfg.base.baud (115200)")
    parser.add_argument("--config", help="sciezka do pinecone_config.json")
    parser.add_argument("--yes", action="store_true", help="nie pytaj o potwierdzenie")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("forward", help="jazda prosto przez S sekund")
    p.add_argument("--seconds", type=float, required=True)
    p.add_argument("--v", type=float, default=0.15, help="m/s (ujemne = cofanie)")
    p.set_defaults(fn=cmd_forward)

    p = sub.add_parser("turn", help="obrot w miejscu przez S sekund (w > 0 = w lewo)")
    p.add_argument("--seconds", type=float, required=True)
    p.add_argument("--w", type=float, default=0.4, help="rad/s, dodatnie = w lewo")
    p.set_defaults(fn=cmd_turn)

    p = sub.add_parser("square", help="kwadrat: 4 x (bok, obrot 90 st w lewo), fazy czasowe")
    p.add_argument("--side", type=float, default=1.0, help="dlugosc boku [m]")
    p.add_argument("--v", type=float, default=0.15)
    p.add_argument("--w", type=float, default=0.4)
    p.add_argument("--pause", type=float, default=0.5, help="pauza miedzy fazami [s]")
    p.set_defaults(fn=cmd_square)

    args = parser.parse_args()

    cfg = Config.load(args.config)
    cfg.base.driver = args.driver
    if args.port:
        cfg.base.port = args.port
    if args.baud:
        cfg.base.baud = args.baud
    if args.driver != "sim" and not args.port and not cfg.base.port:
        parser.error("--port jest wymagany dla sterownika %s" % args.driver)

    print(WARNING)
    print("driver=%s port=%s baud=%d wheel_base=%.2f m" % (cfg.base.driver, cfg.base.port, cfg.base.baud,
                                                          cfg.base.wheel_base_m))
    want_v = getattr(args, "v", 0.0)
    want_w = getattr(args, "w", 0.0)
    if not (cfg.control.v_min <= want_v <= cfg.control.v_max) or abs(want_w) > cfg.control.w_max:
        print("UWAGA: v=%.2f / w=%.2f poza limitami cfg.control (v %.2f..%.2f, |w| <= %.2f) - "
              "sterownik OBETNIE predkosc, czasy faz beda za krotkie." % (
                  want_v, want_w, cfg.control.v_min, cfg.control.v_max, cfg.control.w_max))
    if not args.yes:
        try:
            input("Enter = start, Ctrl+C = przerwij... ")
        except (KeyboardInterrupt, EOFError):
            print("\nPrzerwano przed startem.")
            return

    kw = {"clock": time.monotonic} if cfg.base.driver == "sim" else {}
    base = make_base(cfg, **kw)
    try:
        if cfg.base.driver == "bipropellant":
            print("limity mocy z firmware: %s (zrodlo: %s)" % (base.speed_limits, base.speed_limits_source))
        args.fn(base, args)
        odom = base.odometry()
        if odom is not None:
            x, y, th = odom
            print("koncowa odometria: x=%.3f y=%.3f theta=%.1f deg" % (x, y, math.degrees(th)))
    except KeyboardInterrupt:
        print("\nCtrl+C - zatrzymuje.")
    finally:
        base.stop()
        time.sleep(0.2)
        base.close()
        print("Zatrzymano, port zamkniety.")


if __name__ == "__main__":
    main()
