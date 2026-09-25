"""Testy petli sterowania w symulacji (bez sprzetu)."""
from __future__ import annotations

import math

from pinecone_bot.brain import Brain, Controller, State
from pinecone_bot.config import Config
from pinecone_bot.detector import Detection, HsvConeDetector
from pinecone_bot.sim import SimArmSimple, SimCamera, SimClock, SimDrive, SimWorld, calibrate_grasps


def make_sim(seed: int, cones=None):
    cfg = Config()
    cfg.sim.seed = seed
    base = SimDrive(cfg)
    world = SimWorld(cfg, base.odometry, cones=cones)
    calibrate_grasps(cfg, world)
    clock = SimClock(base)
    return cfg, base, world, clock


def test_calibration_rows_are_ordered():
    cfg, base, world, clock = make_sim(1)
    rows = [g.target_row for g in cfg.grasps]
    # blizszy punkt chwytu lezy nizej w obrazie (wiekszy wiersz)
    assert rows[0] > rows[1] > rows[2]
    assert 0 < rows[2] and rows[0] < cfg.image_h


def test_detector_sees_simulated_cone_where_geometry_says():
    y0 = -Config().sim.field_m / 2 + 0.2          # robot startuje w rogu pola (patrz SimDrive)
    cfg, base, world, clock = make_sim(1, cones=[(0.6, y0)])  # 0.6 m przed robotem
    assert abs(base.y - y0) < 1e-9
    det = HsvConeDetector(cfg.detector)
    dets = det.detect(world.render())
    assert len(dets) == 1 and not dets[0].partial
    px, py, _ = world.project(*world.to_robot(0.6, y0))
    assert abs(dets[0].px - px) < 4 and abs(dets[0].py - py) < 4


def test_controller_signs():
    cfg, *_ = make_sim(1)
    ctrl = Controller(cfg)
    mid = cfg.grasps[1].target_row
    left = ctrl.compute(Detection(cfg.cx - 60, mid, 100, (0, 0, 1, 1)))
    assert left.w > 0, "szyszka po lewej -> obrot w lewo (w > 0)"
    right = ctrl.compute(Detection(cfg.cx + 60, mid, 100, (0, 0, 1, 1)))
    assert right.w < 0
    far = ctrl.compute(Detection(cfg.cx, mid - 60, 100, (0, 0, 1, 1)))
    assert far.v > 0, "szyszka wyzej w obrazie = dalej -> jazda do przodu"
    near = ctrl.compute(Detection(cfg.cx, cfg.grasps[0].target_row + 30, 100, (0, 0, 1, 1)))
    assert near.v < 0, "szyszka za blisko -> cofanie"
    ok = ctrl.compute(Detection(cfg.cx + 2, mid + 2, 100, (0, 0, 1, 1)))
    assert ok.in_tol


def test_single_cone_gets_collected():
    cfg, base, world, clock = make_sim(3, cones=[(0.9, 0.25)])
    brain = Brain(cfg, SimCamera(world), HsvConeDetector(cfg.detector), base,
                  SimArmSimple(world, clock), clock=clock, verbose=False)
    brain.run(max_seconds=400)
    assert world.collected == 1
    assert world.failed_grasps == 0
    assert brain.state == State.DONE


def test_five_cones_get_collected():
    # ziarno 1 celowo pominiete: jego ostatnia szyszka lezy za robotem poza zasiegiem kamery,
    # a przeczesywanie terenu (krok 6 planu) nie jest jeszcze zrobione
    cfg, base, world, clock = make_sim(2)
    brain = Brain(cfg, SimCamera(world), HsvConeDetector(cfg.detector), base,
                  SimArmSimple(world, clock), clock=clock, verbose=False)
    stats = brain.run(max_seconds=600)
    assert world.collected == len(world.cones), (world.collected, stats.transitions[-5:])
    assert world.failed_grasps <= 1


def test_sweep_over_seeds():
    """Kilka losowych ukladow: dwie szyszki obok siebie, szyszka na granicy zasiegu itd."""
    total = got = 0
    for seed in (3, 5, 10, 11):
        cfg, base, world, clock = make_sim(seed)
        brain = Brain(cfg, SimCamera(world), HsvConeDetector(cfg.detector), base,
                      SimArmSimple(world, clock), clock=clock, verbose=False)
        brain.run(max_seconds=600)
        total += len(world.cones)
        got += world.collected
        assert brain.state == State.DONE, f"seed {seed} utknal w {brain.state}"
    assert got == total, f"zebrane {got}/{total}"


def test_retry_after_failed_grasp():
    """Ramie, ktore pierwszy raz chybia: robot cofa, podjezdza i probuje jeszcze raz."""
    cfg, base, world, clock = make_sim(5, cones=[(0.8, -0.1)])

    class FlakyArm(SimArmSimple):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.fail_first = True

        def replay(self, name):
            if name.startswith("grasp") and self.fail_first:
                self.fail_first = False
                self.clock.sleep(self.motion_seconds)
                self.world.grasp_attempts += 1
                self.world.failed_grasps += 1
                return False
            return super().replay(name)

    arm = FlakyArm(world, clock)
    brain = Brain(cfg, SimCamera(world), HsvConeDetector(cfg.detector), base, arm, clock=clock, verbose=False)
    brain.run(max_seconds=400)
    names = [t[2] for t in brain.stats.transitions]
    assert "RETRY" in names
    assert world.collected == 1
    assert brain.stats.grasp_attempts == 2


def test_brain_skips_grasps_without_motion_file(capsys):
    """issue #15: chwyt bez pliku ruchu wypada z listy zamiast konczyc misje FileNotFoundError."""
    cfg, base, world, clock = make_sim(1, cones=[])

    class ArmWithFiles(SimArmSimple):
        def has_motion(self, name):
            return name in ("grasp_mid", "drop_box", "home")

    brain = Brain(cfg, SimCamera(world), HsvConeDetector(cfg.detector), base,
                  ArmWithFiles(world, clock), clock=clock, verbose=False)
    assert [g.name for g in cfg.grasps] == ["grasp_mid"]
    assert "grasp_near" in capsys.readouterr().out
    assert brain.controller.target_row_for(0.0) == cfg.grasps[0].target_row

    class ArmWithNothing(SimArmSimple):
        def has_motion(self, name):
            return False

    cfg2, base2, world2, clock2 = make_sim(1, cones=[])
    try:
        Brain(cfg2, SimCamera(world2), HsvConeDetector(cfg2.detector), base2,
              ArmWithNothing(world2, clock2), clock=clock2, verbose=False)
    except RuntimeError:
        pass
    else:
        raise AssertionError("brak jakiegokolwiek ruchu chwytu powinien byc bledem przy starcie")


def test_retry_count_resets_when_cone_is_lost():
    """issue #15: zgubiona szyszka nie zabiera prob nastepnej."""
    y0 = -Config().sim.field_m / 2 + 0.2
    cfg, base, world, clock = make_sim(5, cones=[(0.8, y0)])
    brain = Brain(cfg, SimCamera(world), HsvConeDetector(cfg.detector), base,
                  SimArmSimple(world, clock), clock=clock, verbose=False)
    brain.state = State.APPROACH
    brain._retry_count = 2
    brain._last_seen = clock.now() - 10.0      # dawno nie widziana
    world.cones[0].alive = False               # i faktycznie jej nie ma
    brain.step()
    assert brain.state == State.SEARCH
    assert brain._retry_count == 0


def test_no_cones_finishes_with_done():
    cfg, base, world, clock = make_sim(2, cones=[])
    brain = Brain(cfg, SimCamera(world), HsvConeDetector(cfg.detector), base,
                  SimArmSimple(world, clock), clock=clock, verbose=False)
    brain.run(max_seconds=400)
    assert brain.state == State.DONE
    assert abs(base.theta) > math.pi  # obrocil sie szukajac
