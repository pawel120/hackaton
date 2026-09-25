"""Testy pinecone_bot.arm bez sprzetu (pytest).

Uruchomienie z katalogu repo:
    .\\.venv\\Scripts\\python.exe -m pytest tests/test_arm.py -q
"""
from __future__ import annotations

import glob
import json
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from pinecone_bot import arm as arm_mod  # noqa: E402
from pinecone_bot.arm import (  # noqa: E402
    GRIPPER_OPEN,
    JOINT_NAMES,
    SimArm,
    SubprocessArm,
    WaypointArm,
    load_motion,
    make_arm,
    parse_motion,
)
from pinecone_bot.config import Config  # noqa: E402

MOTIONS_DIR = os.path.join(REPO_ROOT, "motions")

# arm_control importuje lerobot na poziomie modulu, wiec na laptopie bez lerobot
# nie da sie go zaimportowac. Wtedy asercje porownujace stale sa pomijane.
try:
    import arm_control  # noqa: E402
except ImportError:
    arm_control = None


# ---------------------------------------------------------------------------
# atrapy
# ---------------------------------------------------------------------------

class FakeClock:
    """Zegar posuwany przez sleep - testy sa deterministyczne i natychmiastowe."""

    def __init__(self):
        self.t = 0.0
        self.slept = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        assert s >= 0
        self.t += s
        self.slept += s


class FakeArm:
    """Idealnie sledzi komendy. gripper_reading (jesli ustawione) nadpisuje odczyt chwytaka."""

    def __init__(self, gripper_reading=None):
        self.pose = dict(arm_mod.HOME_POSE)
        self.actions: list = []
        self.gripper_reading = gripper_reading
        self.connected = False

    def connect(self, calibrate=False):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def send_action(self, action: dict):
        self.actions.append(dict(action))
        for key, val in action.items():
            assert key.endswith(".pos")
            self.pose[key[:-4]] = val
        return action

    def get_observation(self) -> dict:
        obs = {f"{j}.pos": v for j, v in self.pose.items()}
        if self.gripper_reading is not None:
            obs["gripper.pos"] = self.gripper_reading
        return obs


def make_cfg(driver="waypoints") -> Config:
    cfg = Config()
    cfg.arm.driver = driver
    cfg.arm.motions_dir = MOTIONS_DIR
    return cfg


def waypoint_arm(fake: FakeArm) -> tuple:
    clock = FakeClock()
    ctl = WaypointArm(make_cfg(), arm=fake, sleep=clock.sleep, clock=clock.now)
    return ctl, clock


def full_actions(fake: FakeArm) -> list:
    return [a for a in fake.actions if len(a) == len(JOINT_NAMES)]


# ---------------------------------------------------------------------------
# pliki ruchu
# ---------------------------------------------------------------------------

def test_joint_names_match_arm_control():
    if arm_control is None:
        pytest.skip("arm_control wymaga lerobot (import na poziomie modulu)")
    assert JOINT_NAMES == arm_control.JOINT_NAMES
    assert arm_mod.HOME_POSE == arm_control.HOME_POSE


def test_all_motion_files_load():
    paths = glob.glob(os.path.join(MOTIONS_DIR, "*.json"))
    assert paths, "brak plikow w motions/"
    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        motion = load_motion(MOTIONS_DIR, name)
        assert motion.name == name
        assert motion.waypoints
        for wp in motion.waypoints:
            assert set(wp.pose) == set(JOINT_NAMES)
        with open(path, "rb") as fh:
            fh.read().decode("ascii")  # regula zespolu: tylko ASCII


def test_grasp_mid_matches_replay_demo():
    motion = load_motion(MOTIONS_DIR, "grasp_mid")
    labels = [wp.label for wp in motion.waypoints]
    assert labels == [
        "start (home)",
        "wysiegniecie nad szyszka",
        "max wysiegniecie / zacisk",
        "powrot do home z szyszka",
    ]
    assert [wp.check_gripper for wp in motion.waypoints] == [False, False, True, False]
    assert motion.waypoints[2].pose["elbow_flex"] == pytest.approx(-95.52)
    assert motion.total_seconds == pytest.approx(6.0)


def test_home_motion_is_home_pose():
    motion = load_motion(MOTIONS_DIR, "home")
    assert len(motion.waypoints) == 1
    assert motion.waypoints[0].pose == pytest.approx(arm_mod.HOME_POSE)


def test_parse_rejects_unknown_joint():
    data = {"name": "x", "waypoints": [{"label": "a", "pose": dict(arm_mod.HOME_POSE, elbow=1.0)}]}
    with pytest.raises(ValueError, match="nieznane przeguby"):
        parse_motion(data)


def test_parse_rejects_missing_joint():
    pose = dict(arm_mod.HOME_POSE)
    del pose["wrist_roll"]
    with pytest.raises(ValueError, match="brakuje"):
        parse_motion({"name": "x", "waypoints": [{"label": "a", "pose": pose}]})


def test_load_missing_motion(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_motion(str(tmp_path), "nope")


def test_save_and_reload_roundtrip(tmp_path):
    motion = parse_motion(json.load(open(os.path.join(MOTIONS_DIR, "grasp_mid.json"))))
    path = arm_mod.save_motion(str(tmp_path), motion)
    assert os.path.exists(path)
    again = load_motion(str(tmp_path), "grasp_mid")
    assert [wp.label for wp in again.waypoints] == [wp.label for wp in motion.waypoints]
    assert [wp.check_gripper for wp in again.waypoints] == [wp.check_gripper for wp in motion.waypoints]
    assert again.waypoints[2].pose == pytest.approx(motion.waypoints[2].pose, abs=0.01)


# ---------------------------------------------------------------------------
# WaypointArm
# ---------------------------------------------------------------------------

def test_waypoint_replay_holds_returns_true():
    fake = FakeArm(gripper_reading=20.0)  # szyszka blokuje szczeki: odczyt 20 > prog 6
    ctl, clock = waypoint_arm(fake)
    motion = load_motion(MOTIONS_DIR, "grasp_mid")

    assert ctl.replay("grasp_mid") is True

    sent = full_actions(fake)
    # kazdy waypoint konczy sie dokladnie zadana poza
    for wp in motion.waypoints:
        target = {f"{j}.pos": v for j, v in wp.pose.items()}
        assert any(a == pytest.approx(target) for a in sent), wp.label
    # ostatnia komenda = ostatni waypoint (ruch dokonczony)
    last = motion.waypoints[-1].pose
    assert sent[-1] == pytest.approx({f"{j}.pos": v for j, v in last.items()})
    # interpolacja: ~30 komend/s przez 1.5 s na waypoint, 4 waypointy
    assert len(sent) == 4 * 45
    # zegar: czasy ruchu + settle po kazdym waypointcie
    assert clock.slept == pytest.approx(motion.total_seconds + 4 * ctl.settle_s, abs=0.05)


def test_waypoint_replay_empty_returns_false_and_opens():
    fake = FakeArm(gripper_reading=2.0)  # PROGRESS.md: ~2 po zamknieciu = pusto
    ctl, _ = waypoint_arm(fake)
    motion = load_motion(MOTIONS_DIR, "grasp_mid")

    assert ctl.replay("grasp_mid") is False

    close_pose = {f"{j}.pos": v for j, v in motion.waypoints[2].pose.items()}
    idx = next(i for i, a in enumerate(fake.actions) if a == pytest.approx(close_pose))
    after = fake.actions[idx + 1:]
    # po zacisku: tylko otwieranie chwytaka, zadnego 'powrot do home z szyszka'
    assert after, "chwytak powinien zostac otwarty"
    assert all(set(a) == {"gripper.pos"} for a in after)
    assert after[-1]["gripper.pos"] == pytest.approx(GRIPPER_OPEN)
    lift_pose = {f"{j}.pos": v for j, v in motion.waypoints[3].pose.items()}
    assert not any(a == pytest.approx(lift_pose) for a in fake.actions)


def test_waypoint_replay_without_check_returns_none():
    fake = FakeArm()
    ctl, _ = waypoint_arm(fake)
    assert ctl.replay("home") is None
    assert full_actions(fake)[-1] == pytest.approx({f"{j}.pos": v for j, v in arm_mod.HOME_POSE.items()})


def test_waypoint_interpolates_from_current_pose():
    fake = FakeArm()
    fake.pose["shoulder_pan"] = 40.0
    ctl, _ = waypoint_arm(fake)
    ctl.replay("home")
    sent = full_actions(fake)
    first = sent[0]["shoulder_pan.pos"]
    # pierwszy krok jest blisko pozycji startowej, nie skokiem do celu
    assert 35.0 < first < 40.0
    pans = [a["shoulder_pan.pos"] for a in sent]
    assert pans == sorted(pans, reverse=True)  # monotonicznie w strone celu


def test_waypoint_verify_warns_when_not_reached(caplog):
    class LazyArm(FakeArm):
        def get_observation(self):
            obs = super().get_observation()
            obs["elbow_flex.pos"] = obs["elbow_flex.pos"] + 10.0  # zawsze 10 st obok
            return obs

    fake = LazyArm()
    ctl, _ = waypoint_arm(fake)
    with caplog.at_level("WARNING", logger="pinecone_bot.arm"):
        ctl.replay("home")
    assert any("nie osiagniety" in r.message and "elbow_flex" in r.message for r in caplog.records)


def test_waypoint_home_uses_home_motion_or_pose(tmp_path):
    fake = FakeArm()
    ctl, _ = waypoint_arm(fake)
    ctl.home()
    assert full_actions(fake)[-1] == pytest.approx({f"{j}.pos": v for j, v in arm_mod.HOME_POSE.items()})

    fake2 = FakeArm()
    cfg = make_cfg()
    cfg.arm.motions_dir = str(tmp_path)  # brak home.json -> HOME_POSE
    clock = FakeClock()
    ctl2 = WaypointArm(cfg, arm=fake2, sleep=clock.sleep, clock=clock.now)
    ctl2.home()
    assert full_actions(fake2)[-1] == pytest.approx({f"{j}.pos": v for j, v in arm_mod.HOME_POSE.items()})


def test_waypoint_close_does_not_disconnect_injected_arm():
    fake = FakeArm()
    fake.connected = True
    ctl, _ = waypoint_arm(fake)
    ctl.close()
    assert fake.connected  # wstrzykniete ramie nalezy do wolajacego


# ---------------------------------------------------------------------------
# SimArm / SubprocessArm / make_arm
# ---------------------------------------------------------------------------

class World:
    def __init__(self, result):
        self.result = result
        self.calls: list = []

    def try_grasp(self, name):
        self.calls.append(name)
        return self.result


@pytest.mark.parametrize("result", [True, False])
def test_sim_arm_returns_world_result(result):
    world = World(result)
    clock = FakeClock()
    sim = SimArm(make_cfg("sim"), world=world, sleep=clock.sleep)
    assert sim.replay("grasp_mid") is result
    assert world.calls == ["grasp_mid"]
    assert clock.slept == pytest.approx(6.0)  # suma seconds z grasp_mid.json


def test_sim_arm_without_world_returns_none():
    clock = FakeClock()
    sim = SimArm(make_cfg("sim"), sleep=clock.sleep)
    assert sim.replay("grasp_mid") is None
    sim.home()
    assert clock.slept == pytest.approx(6.0 + 2.0)


def test_subprocess_arm_formats_command():
    calls = []

    class Proc:
        returncode = 0

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return Proc()

    cfg = make_cfg("subprocess")
    cfg.arm.port = "/dev/robot-arm"
    cfg.arm.subprocess_cmd = "python replay_demo.py --port {port} --motion {name}"
    sub = SubprocessArm(cfg, run=fake_run)
    assert sub.replay("grasp_mid") is None
    assert calls[0][0] == "python replay_demo.py --port /dev/robot-arm --motion grasp_mid"
    assert calls[0][1]["shell"] is True


def test_make_arm_dispatch():
    assert isinstance(make_arm(make_cfg("sim")), SimArm)
    assert isinstance(make_arm(make_cfg("subprocess")), SubprocessArm)
    assert isinstance(make_arm(make_cfg("waypoints"), arm=FakeArm(), sleep=lambda s: None), WaypointArm)
    cfg = make_cfg("nope")
    with pytest.raises(ValueError):
        make_arm(cfg)
