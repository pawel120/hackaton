"""Testy tools/calibrate_target.py w trybie headless - bez kamery i bez okna.

    python -m pytest tests/test_calibrate_target.py -q

Klatki syntetyczne jak w test_detector.py: zielona murawa, brazowa elipsa
w domyslnym zakresie HSV.
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pinecone_bot.camera import FileCamera  # noqa: E402
from pinecone_bot.config import Config, Grasp  # noqa: E402
from pinecone_bot.detector import HsvConeDetector  # noqa: E402
from tools import calibrate_target  # noqa: E402

W, H = 640, 480
GREEN = (40, 140, 40)
BROWN = (30, 60, 110)


def _frame(cx=None, cy=None, seed=0):
    rng = np.random.default_rng(seed)
    img = np.empty((H, W, 3), dtype=np.float32)
    img[:] = GREEN
    img += rng.normal(0.0, 6.0, size=img.shape).astype(np.float32)
    img = np.clip(img, 0, 255).astype(np.uint8)
    if cx is not None:
        cv2.ellipse(img, (int(cx), int(cy)), (18, 12), 0, 0, 360, BROWN, -1)
    return img


def _write_frames(tmp_path, frames):
    d = tmp_path / "frames"
    d.mkdir()
    for i, f in enumerate(frames):
        cv2.imwrite(str(d / f"f{i:03d}.png"), f)
    return str(d)


def test_collect_average_on_cone_frames(tmp_path):
    src = _write_frames(tmp_path, [_frame(300, 250, seed=i) for i in range(5)])
    cam = FileCamera(src)
    res = calibrate_target.collect_average(cam, HsvConeDetector(Config().detector), n_frames=15)
    assert res is not None
    avg_px, avg_py, std_px, std_py, n = res
    assert n == 15
    assert abs(avg_px - 300) <= 3.0 and abs(avg_py - 250) <= 3.0
    assert std_px < 2.0 and std_py < 2.0


def test_collect_average_returns_none_without_cone(tmp_path):
    src = _write_frames(tmp_path, [_frame(seed=i) for i in range(3)])
    cam = FileCamera(src)
    assert calibrate_target.collect_average(cam, HsvConeDetector(Config().detector), n_frames=5) is None


def test_gap_in_detections_resets_series(tmp_path):
    # 3 klatki z szyszka, 1 bez, 3 z szyszka: seria 4 nigdy nie powstaje w 7 odczytach
    frames = [_frame(300, 250, seed=i) for i in range(3)] + [_frame()] + [_frame(300, 250, seed=i) for i in range(3)]
    cam = FileCamera(_write_frames(tmp_path, frames), loop=False)
    assert calibrate_target.collect_average(cam, HsvConeDetector(Config().detector), n_frames=4, max_reads=7) is None


def test_apply_measurement_writes_grasp_and_cx():
    cfg = Config()
    cfg.grasps = [Grasp(name="grasp_mid", target_row=360.0, forward_m=0.33)]
    changes = calibrate_target.apply_measurement(cfg, 311.26, 402.74, "grasp_mid", set_cx=True)
    assert cfg.grasps[0].target_row == 402.7
    assert cfg.cx == 311.3
    assert len(changes) == 2


def test_apply_measurement_unknown_grasp():
    cfg = Config()
    with pytest.raises(SystemExit):
        calibrate_target.apply_measurement(cfg, 300.0, 400.0, "grasp_xxx", set_cx=False)


def test_apply_measurement_cx_only_keeps_grasps():
    cfg = Config()
    before = [g.target_row for g in cfg.grasps]
    calibrate_target.apply_measurement(cfg, 333.0, 444.0, None, set_cx=True)
    assert cfg.cx == 333.0
    assert [g.target_row for g in cfg.grasps] == before
