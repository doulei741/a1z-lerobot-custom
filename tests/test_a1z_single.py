import math
from types import SimpleNamespace

import numpy as np
import pytest


ACTION_KEYS = [*(f"arm_{index}.pos" for index in range(6)), "gripper.pos"]


def make_action(*values):
    return dict(zip(ACTION_KEYS, values, strict=True))


def test_a1z_arm_normalized_boundary_preserves_dual_arm_raw_interface():
    from a1z_lerobot.robots.a1z_follower.hardware import a1z as hardware_module

    class FakeSDKArm:
        gripper = SimpleNamespace(get_feedback_norm=lambda: 0.25)

        def get_joint_state(self):
            return {"pos": np.arange(6, dtype=np.float32)}

        def command_joint_pos(self, command):
            self.command = command

    arm = hardware_module.A1ZArm.__new__(hardware_module.A1ZArm)
    arm._arm = FakeSDKArm()

    normalized = arm.get_state_normalized()
    arm.send_command_normalized(np.array([1, 2, 3, 4, 5, 6, 0.75], dtype=np.float32))

    assert normalized.tolist() == [0, 1, 2, 3, 4, 5, 0.25]
    assert arm._arm.command.tolist() == [1, 2, 3, 4, 5, 6, 0.75]


def test_process_single_action_applies_ema_delta_and_gripper_limits():
    from a1z_lerobot.robots.a1z_single.a1z_single import process_single_action

    previous = np.zeros(7, dtype=np.float32)
    target = make_action(1, 1, -1, 1, 1, 1, 2)

    sent = process_single_action(
        target,
        previous=previous,
        ema_alpha=0.5,
        max_joint_delta=0.1,
    )

    assert sent[:6] == pytest.approx([0.1, 0.1, -0.1, 0.1, 0.1, 0.1])
    assert sent[6] == pytest.approx(1.0)


def test_process_single_action_applies_a1z_physical_joint_limits():
    from a1z_lerobot.robots.a1z_single.a1z_single import process_single_action

    target = make_action(-99, -99, 99, 99, 99, 99, -1)
    sent = process_single_action(
        target,
        previous=np.zeros(7, dtype=np.float32),
        ema_alpha=1.0,
        max_joint_delta=0.0,
    )

    assert sent.tolist() == pytest.approx([-2.094, 0.0, 0.0, 1.484, 1.484, 2.007, 0.0])


@pytest.mark.parametrize(
    "action",
    [
        {key: 0.0 for key in ACTION_KEYS[:-1]},
        {**{key: 0.0 for key in ACTION_KEYS}, "extra.pos": 0.0},
        make_action(0, 0, math.nan, 0, 0, 0, 0),
        make_action(0, 0, 0, 0, math.inf, 0, 0),
    ],
)
def test_process_single_action_rejects_invalid_actions_before_hardware(action):
    from a1z_lerobot.robots.a1z_single.a1z_single import process_single_action

    with pytest.raises(ValueError):
        process_single_action(
            action,
            previous=np.zeros(7, dtype=np.float32),
            ema_alpha=1.0,
            max_joint_delta=0.1,
        )


def test_single_robot_features_follow_parameterized_camera_dictionary(monkeypatch, tmp_path):
    import a1z_lerobot.robots.a1z_single.a1z_single as robot_module
    from a1z_lerobot.robots.a1z_single.config_a1z_single import A1ZSingleConfig

    camera_configs = {
        "top_rgb": SimpleNamespace(height=480, width=640, fps=30),
        "wrist_rgb": SimpleNamespace(height=480, width=640, fps=30),
    }
    cameras = {
        name: SimpleNamespace(is_connected=True, async_read=lambda: np.zeros((480, 640, 3), dtype=np.uint8))
        for name in camera_configs
    }
    monkeypatch.setattr(robot_module, "make_cameras_from_configs", lambda configs: cameras)

    robot = robot_module.A1ZSingle(
        A1ZSingleConfig(
            id="single",
            calibration_dir=tmp_path,
            cameras=camera_configs,
        )
    )

    assert list(robot.action_features) == ACTION_KEYS
    assert robot.observation_features["top_rgb"] == (480, 640, 3)
    assert robot.observation_features["wrist_rgb"] == (480, 640, 3)


def test_single_robot_returns_actual_sent_action_and_default_disconnect_does_not_home(
    monkeypatch, tmp_path
):
    import a1z_lerobot.robots.a1z_single.a1z_single as robot_module
    from a1z_lerobot.robots.a1z_single.config_a1z_single import A1ZSingleConfig

    class FakeArm:
        def __init__(self, can_channel):
            assert can_channel == "can7"
            self.command = None
            self.home_calls = 0
            self.stop_calls = 0

        def start(self):
            pass

        def get_state_normalized(self):
            return np.zeros(7, dtype=np.float32)

        def send_command_normalized(self, command):
            self.command = command.copy()

        def move_to_home(self):
            self.home_calls += 1

        def stop(self):
            self.stop_calls += 1

    monkeypatch.setattr(robot_module, "A1ZArm", FakeArm)
    robot = robot_module.A1ZSingle(
        A1ZSingleConfig(
            id="single",
            calibration_dir=tmp_path,
            can_channel="can7",
            cameras={},
            ema_alpha=1.0,
            max_joint_delta=0.1,
        )
    )
    robot.connect()

    sent = robot.send_action(make_action(1, 1, -1, 1, 1, 1, 0.75))
    arm = robot.arm
    robot.disconnect()

    assert list(sent) == ACTION_KEYS
    expected = [0.1, 0.1, -0.1, 0.1, 0.1, 0.1, 0.75]
    assert list(sent.values()) == pytest.approx(expected)
    assert arm.command.tolist() == pytest.approx(expected)
    assert arm.home_calls == 0
    assert arm.stop_calls == 1


def test_single_robot_stops_arm_even_if_camera_disconnect_fails(monkeypatch, tmp_path):
    import a1z_lerobot.robots.a1z_single.a1z_single as robot_module
    from a1z_lerobot.robots.a1z_single.config_a1z_single import A1ZSingleConfig

    class FailingCamera:
        is_connected = True

        def connect(self):
            pass

        def disconnect(self):
            raise RuntimeError("camera disconnect failed")

    class FakeArm:
        def __init__(self, can_channel):
            self.stop_calls = 0

        def start(self):
            pass

        def get_state_normalized(self):
            return np.zeros(7, dtype=np.float32)

        def stop(self):
            self.stop_calls += 1

    camera_config = {"top_rgb": SimpleNamespace(height=480, width=640, fps=30)}
    monkeypatch.setattr(robot_module, "make_cameras_from_configs", lambda configs: {"top_rgb": FailingCamera()})
    monkeypatch.setattr(robot_module, "A1ZArm", FakeArm)
    robot = robot_module.A1ZSingle(
        A1ZSingleConfig(
            id="single",
            calibration_dir=tmp_path,
            cameras=camera_config,
        )
    )
    robot.connect()
    arm = robot.arm

    with pytest.raises(RuntimeError, match="camera disconnect failed"):
        robot.disconnect()

    assert arm.stop_calls == 1
    assert robot.arm is None
    assert robot._connected is False


def test_policy_preflight_accepts_exact_seven_dimensional_two_camera_contract():
    from a1z_lerobot.robots.a1z_single.a1z_single import validate_policy_features

    policy = SimpleNamespace(
        input_features={
            "observation.state": SimpleNamespace(shape=(7,)),
            "observation.images.top_rgb": SimpleNamespace(shape=(3, 480, 640)),
            "observation.images.wrist_rgb": SimpleNamespace(shape=(3, 480, 640)),
        },
        output_features={"action": SimpleNamespace(shape=(7,))},
    )

    validate_policy_features(
        policy,
        camera_features={
            "top_rgb": (480, 640, 3),
            "wrist_rgb": (480, 640, 3),
        },
    )


@pytest.mark.parametrize(
    ("state_shape", "action_shape", "camera_features", "message"),
    [
        ((14,), (7,), {"top_rgb": (480, 640, 3)}, "state"),
        ((7,), (14,), {"top_rgb": (480, 640, 3)}, "action"),
        ((7,), (7,), {"wrong_rgb": (480, 640, 3)}, "visual"),
    ],
)
def test_policy_preflight_rejects_feature_mismatch_before_hardware(
    state_shape, action_shape, camera_features, message
):
    from a1z_lerobot.robots.a1z_single.a1z_single import validate_policy_features

    policy = SimpleNamespace(
        input_features={
            "observation.state": SimpleNamespace(shape=state_shape),
            "observation.images.top_rgb": SimpleNamespace(shape=(3, 480, 640)),
        },
        output_features={"action": SimpleNamespace(shape=action_shape)},
    )

    with pytest.raises(ValueError, match=message):
        validate_policy_features(policy, camera_features=camera_features)
