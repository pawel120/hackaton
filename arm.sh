#!/bin/bash
# Skrot na Pi: ./arm.sh status | home | move shoulder_pan=10 | open | close ...
cd ~/hackaton
export PATH="$HOME/.local/bin:$PATH"
export ROBOT_ARM_PORT=/dev/robot-arm
source .venv/bin/activate
exec python arm_control.py "$@"
