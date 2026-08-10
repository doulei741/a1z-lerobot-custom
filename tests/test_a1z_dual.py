from types import SimpleNamespace

import numpy as np
import pytest


MOTOR_KEYS = [
    "left_arm_0.pos",
    "left_arm_1.pos",
    "left_arm_2.pos",
    "left_arm_3.pos",
    "left_arm_4.pos",
    "left_arm_5.pos",
    "left_ee_0.pos",
    "right_arm_0.pos",
    "right_arm_1.pos",
    "right_arm_2.pos",
    "right_arm_3.pos",
    "right_arm_4.pos",
    "right_arm_5.pos",
    "right_ee_0.pos",
]


def make_action(left_gripper, right_gripper):
    values = np.zeros(14, dtype=np.float32)
    values[6] = left_gripper
    values[13] = right_gripper
    return dict(zip(MOTOR_KEYS, values, strict=True))


def test_dual_config_defaults_to_safe_exit_and_gripper_start_hold():
    from a1z_lerobot.robots.a1z_follower.config_a1z_follower import A1ZConfig

    config = A1ZConfig()

    assert config.gripper_start_hold is True
    assert config.return_home_on_disconnect is False
    assert config.open_grippers_on_disconnect is False


def test_dual_gripper_start_hold_tracks_left_and_right_deltas_independently(monkeypatch, tmp_path):
    import a1z_lerobot.robots.a1z_follower.a1z_follower as module
    from a1z_lerobot.robots.a1z_follower.config_a1z_follower import A1ZConfig

    follower_start = np.zeros(14, dtype=np.float32)
    follower_start[6] = 2.0
    follower_start[13] = -2.0

    class FakeDualArm:
        def __init__(self, left_can, right_can):
            self.commands = []

        def start(self):
            pass

        def get_state(self):
            return follower_start.copy()

        def send_command(self, command):
            self.commands.append(command.copy())

        def stop(self):
            pass

    monkeypatch.setattr(module, "A1ZDualArm", FakeDualArm)
    robot = module.A1Z(
        A1ZConfig(
            id="dual",
            calibration_dir=tmp_path,
            cameras={},
            ema_alpha=1.0,
            max_joint_delta=0.1,
            gripper_start_hold=True,
        )
    )
    robot.connect()

    first = robot.send_action(make_action(2.87, -2.87))
    second = robot.send_action(make_action(1.87, -1.87))

    assert first["left_ee_0.pos"] == pytest.approx(2.0)
    assert first["right_ee_0.pos"] == pytest.approx(-2.0)
    assert second["left_ee_0.pos"] == pytest.approx(1.0)
    assert second["right_ee_0.pos"] == pytest.approx(-1.0)


def test_dual_default_disconnect_stops_without_opening_or_homing(monkeypatch, tmp_path):
    import a1z_lerobot.robots.a1z_follower.a1z_follower as module
    from a1z_lerobot.robots.a1z_follower.config_a1z_follower import A1ZConfig

    class FakeDualArm:
        def __init__(self, left_can, right_can):
            self.events = []

        def start(self):
            self.events.append("start")

        def get_state(self):
            return np.zeros(14, dtype=np.float32)

        def command_gripper(self, position):
            self.events.append("open")

        def move_to_home(self):
            self.events.append("home")

        def disable_gripper(self):
            self.events.append("disable_gripper")

        def stop(self):
            self.events.append("stop")

    monkeypatch.setattr(module, "A1ZDualArm", FakeDualArm)
    robot = module.A1Z(A1ZConfig(id="dual", calibration_dir=tmp_path, cameras={}))
    robot.connect()
    arm = robot.arm
    robot.disconnect()

    assert arm.events == ["start", "stop"]
    assert robot.arm is None
    assert not robot.is_connected


def test_dual_disconnect_exit_movements_are_explicit_opt_ins(monkeypatch, tmp_path):
    import a1z_lerobot.robots.a1z_follower.a1z_follower as module
    from a1z_lerobot.robots.a1z_follower.config_a1z_follower import A1ZConfig

    class FakeDualArm:
        def __init__(self, left_can, right_can):
            self.events = []

        def start(self):
            pass

        def get_state(self):
            return np.zeros(14, dtype=np.float32)

        def command_gripper(self, position):
            self.events.append(("open", position))

        def move_to_home(self):
            self.events.append(("home",))

        def stop(self):
            self.events.append(("stop",))

    monkeypatch.setattr(module, "A1ZDualArm", FakeDualArm)
    robot = module.A1Z(
        A1ZConfig(
            id="dual",
            calibration_dir=tmp_path,
            cameras={},
            open_grippers_on_disconnect=True,
            return_home_on_disconnect=True,
        )
    )
    robot.connect()
    arm = robot.arm
    robot.disconnect()

    assert [event[0] for event in arm.events] == ["open", "home", "stop"]


def test_dual_connect_cleans_up_started_arm_and_connected_cameras(monkeypatch, tmp_path):
    import a1z_lerobot.robots.a1z_follower.a1z_follower as module
    from a1z_lerobot.robots.a1z_follower.config_a1z_follower import A1ZConfig

    events = []

    class FakeDualArm:
        def __init__(self, left_can, right_can):
            pass

        def start(self):
            events.append("arm:start")

        def stop(self):
            events.append("arm:stop")

    class Camera:
        def __init__(self, name, fails=False):
            self.name = name
            self.fails = fails
            self.is_connected = False

        def connect(self):
            events.append(f"camera:{self.name}:connect")
            if self.fails:
                raise RuntimeError("camera unavailable")
            self.is_connected = True

        def disconnect(self):
            events.append(f"camera:{self.name}:disconnect")
            self.is_connected = False

    cameras = {"top": Camera("top"), "wrist": Camera("wrist", fails=True)}
    monkeypatch.setattr(module, "A1ZDualArm", FakeDualArm)
    monkeypatch.setattr(module, "make_cameras_from_configs", lambda configs: cameras)
    robot = module.A1Z(
        A1ZConfig(
            id="dual",
            calibration_dir=tmp_path,
            cameras={
                "top": SimpleNamespace(height=480, width=640, fps=30),
                "wrist": SimpleNamespace(height=480, width=640, fps=30),
            },
        )
    )

    with pytest.raises(RuntimeError, match="camera unavailable"):
        robot.connect()

    assert events == [
        "arm:start",
        "camera:top:connect",
        "camera:wrist:connect",
        "camera:top:disconnect",
        "arm:stop",
    ]
    assert robot.arm is None


def test_dual_arm_start_stops_left_when_right_start_fails():
    from a1z_lerobot.robots.a1z_follower.hardware.dual_arm import A1ZDualArm

    events = []

    class Arm:
        def __init__(self, side, fails=False):
            self.side = side
            self.fails = fails

        def start(self):
            events.append(f"{self.side}:start")
            if self.fails:
                raise RuntimeError("right start failed")

        def stop(self):
            events.append(f"{self.side}:stop")

    dual = A1ZDualArm.from_arms(Arm("left"), Arm("right", fails=True))

    with pytest.raises(RuntimeError, match="right start failed"):
        dual.start()

    assert events == ["left:start", "right:start", "left:stop"]


def test_dual_robot_rejects_nonfinite_action_before_sending(monkeypatch, tmp_path):
    import a1z_lerobot.robots.a1z_follower.a1z_follower as module
    from a1z_lerobot.robots.a1z_follower.config_a1z_follower import A1ZConfig

    class FakeDualArm:
        def __init__(self, left_can, right_can):
            self.send_calls = 0

        def start(self):
            pass

        def get_state(self):
            return np.zeros(14, dtype=np.float32)

        def send_command(self, command):
            self.send_calls += 1

        def stop(self):
            pass

    monkeypatch.setattr(module, "A1ZDualArm", FakeDualArm)
    robot = module.A1Z(A1ZConfig(id="dual", calibration_dir=tmp_path, cameras={}))
    robot.connect()
    action = make_action(0.0, 0.0)
    action["right_arm_4.pos"] = float("nan")

    with pytest.raises(ValueError, match="finite"):
        robot.send_action(action)

    assert robot.arm.send_calls == 0


def test_dual_joint_limits_are_applied_before_command_history(monkeypatch, tmp_path):
    import a1z_lerobot.robots.a1z_follower.a1z_follower as module
    from a1z_lerobot.robots.a1z_follower.config_a1z_follower import A1ZConfig

    class FakeDualArm:
        def __init__(self, left_can, right_can):
            self.commands = []

        def start(self):
            pass

        def get_state(self):
            return np.zeros(14, dtype=np.float32)

        def send_command(self, command):
            self.commands.append(command.copy())

        def stop(self):
            pass

    monkeypatch.setattr(module, "A1ZDualArm", FakeDualArm)
    robot = module.A1Z(
        A1ZConfig(
            id="dual",
            calibration_dir=tmp_path,
            cameras={},
            ema_alpha=1.0,
            max_joint_delta=0.1,
            gripper_start_hold=False,
        )
    )
    robot.connect()

    invalid = make_action(0.0, 0.0)
    invalid.update(
        {
            "left_arm_1.pos": -1.0,
            "left_arm_2.pos": 1.0,
            "right_arm_1.pos": -1.0,
            "right_arm_2.pos": 1.0,
        }
    )
    first = robot.send_action(invalid)

    valid = make_action(0.0, 0.0)
    valid.update(
        {
            "left_arm_1.pos": 0.1,
            "left_arm_2.pos": -0.1,
            "right_arm_1.pos": 0.1,
            "right_arm_2.pos": -0.1,
        }
    )
    second = robot.send_action(valid)

    assert [first[key] for key in ("left_arm_1.pos", "left_arm_2.pos")] == pytest.approx(
        [0.0, 0.0]
    )
    assert [first[key] for key in ("right_arm_1.pos", "right_arm_2.pos")] == pytest.approx(
        [0.0, 0.0]
    )
    assert [second[key] for key in ("left_arm_1.pos", "left_arm_2.pos")] == pytest.approx(
        [0.1, -0.1]
    )
    assert [second[key] for key in ("right_arm_1.pos", "right_arm_2.pos")] == pytest.approx(
        [0.1, -0.1]
    )
    assert robot.arm.commands[-1] == pytest.approx(
        np.array([second[key] for key in MOTOR_KEYS], dtype=np.float32)
    )
