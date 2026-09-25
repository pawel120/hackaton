"""Pojedynczy krok jazdy po surowym protokole Xiao (xiao_send_pwm.ino).

Omija ciezki system makarena/drive_to_target.py (niedostepny pakiet +
zablokowana jazda bez zmierzonej kalibracji). Wysyla "a<speed> b<steer>\\n"
co ~80 ms przez caly czas trwania kroku (watchdog na Xiao jest 500 ms), potem
zeruje predkosc.

speed/steer to SUROWE wartosci PWM (nie metry/stopnie):
    speed: -500..500 (dodatnie = do przodu)
    steer: -400..400 (dodatnie = w prawo, mix roznicowy)

Uzycie:
    python drive_step.py --port /dev/robot-drive --speed 120 --duration 0.15
    python drive_step.py --port /dev/robot-drive --speed 0 --steer 150 --duration 0.2
"""

from __future__ import annotations

import argparse
import time

import serial

BAUDRATE = 115200
TICK_S = 0.08  # < 500 ms watchdog na Xiao


def send_step(port: str, speed: int, steer: int, duration: float, settle: float = 0.3) -> None:
    speed = max(-500, min(500, int(speed)))
    steer = max(-400, min(400, int(steer)))

    with serial.Serial(port, BAUDRATE, timeout=0.2) as ser:
        time.sleep(0.3)  # Xiao resetuje sie przy otwarciu portu USB-CDC
        end = time.monotonic() + duration
        while time.monotonic() < end:
            ser.write(f"a{speed} b{steer}\n".encode())
            time.sleep(TICK_S)
        ser.write(b"a0 b0\n")
        time.sleep(settle)
        ser.write(b"a0 b0\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", required=True, help="np. /dev/robot-drive")
    parser.add_argument("--speed", type=int, default=0, help="PWM -500..500, dodatnie = przod")
    parser.add_argument("--steer", type=int, default=0, help="PWM -400..400, dodatnie = w prawo")
    parser.add_argument("--duration", type=float, required=True, help="czas trwania kroku [s]")
    parser.add_argument("--settle", type=float, default=0.3, help="pauza po zatrzymaniu [s]")
    args = parser.parse_args()

    print(f"Krok: speed={args.speed} steer={args.steer} przez {args.duration:.2f}s na {args.port}")
    send_step(args.port, args.speed, args.steer, args.duration, args.settle)
    print("Zatrzymano.")


if __name__ == "__main__":
    main()
