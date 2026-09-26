"""Kalkulator masztu kamery musi zgadzac sie z geometria symulatora i z prosta trygonometria."""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pinecone_bot.config import Config
from pinecone_bot.sim import SimDrive, SimWorld
from tools import camera_geometry as cg


def test_project_matches_simulator():
    cfg = Config()
    base = SimDrive(cfg, x=0.0, y=0.0, theta=0.0)
    world = SimWorld(cfg, base.odometry, cones=[])
    s = cfg.sim
    for dx, dy in ((0.3, 0.0), (0.6, 0.2), (1.2, -0.4)):
        a = world.project(dx, dy)
        b = cg.project(dx, dy, s.cam_height_m, s.cam_pitch_deg, s.cam_forward_m, s.fx, s.fy, cfg.image_w, cfg.image_h)
        assert a is not None and b is not None
        assert a[0] == b[0] and a[1] == b[1] and a[2] == b[2]


def test_ground_distance_inverts_projection():
    cfg = Config()
    s = cfg.sim
    for dx in (0.25, 0.4, 0.8, 1.5):
        px, py, _ = cg.project(dx, 0.0, s.cam_height_m, s.cam_pitch_deg, s.cam_forward_m, s.fx, s.fy, cfg.image_w, cfg.image_h)
        back = cg.ground_distance_at_row(py, s.cam_height_m, s.cam_pitch_deg, s.cam_forward_m, s.fy, cfg.image_h)
        assert abs(back - dx) < 1e-6


def test_straight_down_camera_is_symmetric():
    # kamera patrzy pionowo w dol: srodek kadru to punkt pod kamera, gora/dol symetrycznie
    h, fy, hgt = 0.5, 600.0, 480
    center = cg.ground_distance_at_row(hgt / 2, h, 90.0, 0.0, fy, hgt)
    top = cg.ground_distance_at_row(0, h, 90.0, 0.0, fy, hgt)
    bottom = cg.ground_distance_at_row(hgt, h, 90.0, 0.0, fy, hgt)
    assert abs(center) < 1e-9
    assert abs(top + bottom) < 1e-9 and top > 0
    assert abs(top - h * (hgt / 2) / fy) < 1e-9


def test_horizon_gives_none():
    # pochylenie 10 st, gorny rzad kadru patrzy nad horyzont (VFOV/2 ~ 21 st > 10 st)
    assert cg.ground_distance_at_row(0, 0.4, 10.0, 0.0, cg.D415_FY_480, 480) is None


def test_analyze_flags_dead_zone_and_frame():
    # nisko i plasko: punkt chwytu 0.17 m przed kamera jest za blisko dla glebi
    a = cg.analyze(0.10, 0.0 + 5.0, 0.0, cg.D415_FX_640, cg.D415_FY_480, 640, 480, [0.17], "640x480")
    assert not a["ok"]
    # wysoko, za osia, pochylona: chwyty 0.30-0.40 m w kadrze i poza martwa strefa
    b = cg.analyze(0.45, 38.0, -0.10, cg.D415_FX_640, cg.D415_FY_480, 640, 480, [0.30, 0.35, 0.40], "424x240")
    assert b["ok"], b
    rows = [g["row"] for g in b["grasps"]]
    assert rows[0] > rows[1] > rows[2]  # blizszy chwyt nizej w obrazie
    assert b["cm_per_px"] is not None and 0.05 < b["cm_per_px"] < 1.0


def test_cli_table_and_detail(capsys):
    assert cg.main(["--grasp-forward", "0.30,0.35,0.40"]) == 0
    out = capsys.readouterr().out
    assert "wys\\kat" in out and "OK" in out
    rc = cg.main(["--height", "0.45", "--pitch", "38", "--cam-forward", "-0.10", "--grasp-forward", "0.30,0.35,0.40"])
    out = capsys.readouterr().out
    assert rc == 0 and "MONTAZ OK" in out
