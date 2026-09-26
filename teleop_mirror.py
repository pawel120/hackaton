"""
Teleoperacja: ramie "leader" (ruszane reka, silniki bezwladne) steruje na zywo
ramieniem "follower" (napedzane, podlaczone np. do Raspberry Pi).

Kazdy tick: czytaj pozycje z leadera -> wyslij jako target do followera.

Wymaga osobnej kalibracji obu ramion (inny ARM_ID kazde), patrz arm_control.py
(dla followera) i analogicznie lerobot SOLeader.calibrate() dla leadera.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from lerobot.robots.so_follower.so_follower import SO101Follower
from lerobot.robots.so_follower.config_so_follower import SO101FollowerConfig
from lerobot.teleoperators.so_leader.so_leader import SOLeader
from lerobot.teleoperators.so_leader.config_so_leader import SOLeaderTeleopConfig

LEADER_PORT = os.environ.get("ROBOT_ARM_LEADER_PORT", "COM9")
FOLLOWER_PORT = os.environ.get("ROBOT_ARM_PORT", "COM10")
LEADER_ID = os.environ.get("ROBOT_ARM_LEADER_ID", "so101_leader")
FOLLOWER_ID = os.environ.get("ROBOT_ARM_ID", "so101")

# Limit ruchu followera na jeden tick (stopnie/jednostki) - zabezpieczenie przed
# szarpnieciem gdy leader skoczy daleko (np. zgubiona ramka odczytu).
MAX_RELATIVE_TARGET = 25.0

LOOP_HZ = 30.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Teleoperacja: leader -> follower (mirror)")
    parser.add_argument("--leader-port", default=LEADER_PORT)
    parser.add_argument("--follower-port", default=FOLLOWER_PORT)
    parser.add_argument("--leader-id", default=LEADER_ID)
    parser.add_argument("--follower-id", default=FOLLOWER_ID)
    parser.add_argument("--hz", type=float, default=LOOP_HZ)
    args = parser.parse_args()

    leader = SOLeader(SOLeaderTeleopConfig(port=args.leader_port, id=args.leader_id))
    follower = SO101Follower(
        SO101FollowerConfig(
            port=args.follower_port,
            id=args.follower_id,
            max_relative_target=MAX_RELATIVE_TARGET,
        )
    )

    period = 1.0 / args.hz

    print(f"Leader   @ {args.leader_port} (id={args.leader_id})")
    print(f"Follower @ {args.follower_port} (id={args.follower_id})")

    leader.connect(calibrate=True)
    try:
        follower.connect(calibrate=True)
        try:
            print("Teleoperacja aktywna. Ctrl+C aby zakonczyc.")
            while True:
                t0 = time.perf_counter()
                try:
                    action = leader.get_action()
                    follower.send_action(action)
                except Exception as exc:
                    print(f"(pominieto blad odczytu/zapisu: {exc})")
                dt = time.perf_counter() - t0
                if dt < period:
                    time.sleep(period - dt)
        finally:
            follower.disconnect()
    except KeyboardInterrupt:
        pass
    finally:
        leader.disconnect()
        print("Rozlaczono oba ramiona.")


if __name__ == "__main__":
    sys.exit(main())
