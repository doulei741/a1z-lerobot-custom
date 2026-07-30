import sys

import pytest


def test_calibrate_leader_command_constructs_requested_leader_and_disconnects(monkeypatch):
    import a1z_lerobot.scripts.calibrate_leader as command

    events = []

    class FakeLeader:
        def __init__(self, config):
            assert config.id == "bench_leader"
            assert config.port == "/dev/ttyUSB9"
            self.is_connected = False

        def connect(self, calibrate=True):
            self.is_connected = True
            events.append(("connect", calibrate))

        def calibrate(self):
            events.append("calibrate")

        def configure(self):
            events.append("configure")

        def disconnect(self):
            self.is_connected = False
            events.append("disconnect")

    monkeypatch.setattr(command, "A1ZLeader", FakeLeader)

    command.calibrate_leader("/dev/ttyUSB9", "bench_leader")

    assert events == [("connect", False), "calibrate", "configure", "disconnect"]


def test_calibrate_leader_command_disconnects_after_calibration_error(monkeypatch):
    import a1z_lerobot.scripts.calibrate_leader as command

    events = []

    class FailingLeader:
        def __init__(self, config):
            self.is_connected = False

        def connect(self, calibrate=True):
            self.is_connected = True
            events.append(("connect", calibrate))

        def calibrate(self):
            events.append("calibrate")
            raise RuntimeError("calibration interrupted")

        def configure(self):
            events.append("configure")

        def disconnect(self):
            self.is_connected = False
            events.append("disconnect")

    monkeypatch.setattr(command, "A1ZLeader", FailingLeader)

    with pytest.raises(RuntimeError, match="calibration interrupted"):
        command.calibrate_leader("/dev/ttyUSB9", "bench_leader")

    assert events == [("connect", False), "calibrate", "disconnect"]


def test_record_yaml_decodes_to_complete_single_arm_rgb_configuration():
    import draccus

    import a1z_lerobot.robots.a1z_single  # noqa: F401
    import a1z_lerobot.teleoperators.a1z_leader  # noqa: F401
    from lerobot.scripts.lerobot_record import RecordConfig

    config = draccus.parse(
        config_class=RecordConfig,
        args=["--config_path=a1z_lerobot/configs/record_a1z_single_realsense.yaml"],
    )

    assert config.robot.type == "a1z_single"
    assert config.robot.relative_action_reference is True
    assert config.teleop.type == "a1z_leader"
    assert config.dataset.single_task
    assert list(config.robot.cameras) == ["top_rgb", "wrist_rgb"]
    for camera in config.robot.cameras.values():
        assert (camera.width, camera.height, camera.fps) == (640, 480, 30)
        assert camera.use_depth is False


def test_default_realsense_cameras_are_rgb_480p_30fps_and_keep_serial_parameters():
    from a1z_lerobot.configs.a1z_single_realsense import default_realsense_cameras

    cameras = default_realsense_cameras("D435-SERIAL", "D405-SERIAL")

    assert list(cameras) == ["top_rgb", "wrist_rgb"]
    assert cameras["top_rgb"].serial_number_or_name == "D435-SERIAL"
    assert cameras["wrist_rgb"].serial_number_or_name == "D405-SERIAL"
    for camera in cameras.values():
        assert (camera.width, camera.height, camera.fps) == (640, 480, 30)
        assert camera.color_mode.value == "rgb"
        assert camera.use_depth is False


def test_act_train_defaults_only_fill_missing_cli_values():
    from a1z_lerobot.scripts.train_act_single import with_act_defaults

    assert with_act_defaults(["train"]) == [
        "train",
        "--policy.type=act",
        "--policy.device=cuda",
        "--batch_size=8",
    ]
    assert with_act_defaults(
        ["train", "--policy.type=act", "--policy.device=cpu", "--batch_size=4"]
    ) == ["train", "--policy.type=act", "--policy.device=cpu", "--batch_size=4"]


def test_single_arm_wrappers_register_robot_and_teleoperator_before_native_main(monkeypatch):
    from lerobot.robots.config import RobotConfig
    from lerobot.teleoperators.config import TeleoperatorConfig

    import a1z_lerobot.scripts.record_single as record_wrapper
    import a1z_lerobot.scripts.rollout_act_single as rollout_wrapper
    import a1z_lerobot.scripts.teleoperate_single as teleoperate_wrapper

    assert RobotConfig.get_choice_class("a1z_single").__name__ == "A1ZSingleConfig"
    assert TeleoperatorConfig.get_choice_class("a1z_leader").__name__ == "A1ZLeaderConfig"

    calls = []
    monkeypatch.setattr(record_wrapper, "native_main", lambda: calls.append("record"))
    monkeypatch.setattr(rollout_wrapper, "native_main", lambda: calls.append("rollout"))
    monkeypatch.setattr(teleoperate_wrapper, "native_main", lambda: calls.append("teleoperate"))

    record_wrapper.main()
    rollout_wrapper.main()
    teleoperate_wrapper.main()

    assert calls == ["record", "rollout", "teleoperate"]


def test_train_wrapper_applies_act_defaults_before_native_main(monkeypatch):
    import a1z_lerobot.scripts.train_act_single as train_wrapper

    calls = []
    monkeypatch.setattr(train_wrapper, "native_main", lambda: calls.append(sys.argv.copy()))
    monkeypatch.setattr(sys, "argv", ["train", "--batch_size=4"])

    train_wrapper.main()

    assert calls == [
        ["train", "--batch_size=4", "--policy.type=act", "--policy.device=cuda"]
    ]
