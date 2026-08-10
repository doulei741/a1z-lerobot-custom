import sys

import draccus
import pytest


RIGHT_D405_OVERRIDE = "--robot.right_wrist_serial=123456789012"


def test_record_yaml_decodes_complete_dual_arm_rgb_configuration():
    import draccus

    import a1z_lerobot.robots.a1z_follower  # noqa: F401
    import a1z_lerobot.teleoperators.bi_a1z_leader  # noqa: F401
    from lerobot.scripts.lerobot_record import RecordConfig

    config = draccus.parse(
        config_class=RecordConfig,
        args=[
            "--config_path=a1z_lerobot/configs/record_a1z_dual_realsense.yaml",
            RIGHT_D405_OVERRIDE,
        ],
    )

    assert config.robot.type == "a1z"
    assert (config.robot.left_can, config.robot.right_can) == ("can0", "can1")
    assert config.robot.gripper_start_hold is True
    assert config.robot.return_home_on_disconnect is False
    assert config.robot.open_grippers_on_disconnect is False
    assert config.robot.right_wrist_serial == "123456789012"
    assert config.teleop.type == "bi_a1z_leader"
    assert config.teleop.left_id == "a1z_left_leader"
    assert config.teleop.right_id == "a1z_right_leader"
    assert config.teleop.left_arm_config.port == "/dev/ttyACM0"
    assert config.teleop.right_arm_config.port == "/dev/ttyACM1"
    assert config.teleop.left_arm_config.joint_offsets_rad == pytest.approx(
        (0.185504249, -1.676119148, -1.985360469, 0.471459368, 0.061374215, 0.089759790)
    )
    assert config.teleop.right_arm_config.joint_offsets_rad == pytest.approx(
        (-0.097389546, -1.672050437, -1.971852804, 0.520146476, -0.038316864, -0.021480975)
    )
    assert list(config.robot.cameras) == ["top_rgb", "left_wrist_rgb", "right_wrist_rgb"]
    assert config.robot.cameras["right_wrist_rgb"].serial_number_or_name == "123456789012"
    for camera in config.robot.cameras.values():
        assert (camera.width, camera.height, camera.fps) == (640, 480, 30)
        assert camera.color_mode.value == "rgb"
        assert camera.use_depth is False


def test_dual_yaml_rejects_unconfigured_right_wrist_serial():
    import draccus

    import a1z_lerobot.robots.a1z_follower  # noqa: F401
    import a1z_lerobot.teleoperators.bi_a1z_leader  # noqa: F401
    from lerobot.scripts.lerobot_record import RecordConfig

    with pytest.raises(draccus.utils.ParsingError) as exc_info:
        draccus.parse(
            config_class=RecordConfig,
            args=["--config_path=a1z_lerobot/configs/record_a1z_dual_realsense.yaml"],
        )

    errors = []
    error = exc_info.value
    while error is not None:
        errors.append(str(error))
        error = error.__cause__
    assert any("right D405 serial" in message for message in errors)


def test_dual_wrappers_register_types_before_native_main(monkeypatch):
    from lerobot.robots.config import RobotConfig
    from lerobot.teleoperators.config import TeleoperatorConfig

    import a1z_lerobot.scripts.record_dual as record_wrapper
    import a1z_lerobot.scripts.rollout_act_dual as rollout_wrapper
    import a1z_lerobot.scripts.teleoperate_dual as teleoperate_wrapper

    assert RobotConfig.get_choice_class("a1z").__name__ == "A1ZConfig"
    assert TeleoperatorConfig.get_choice_class("bi_a1z_leader").__name__ == "BiA1ZLeaderConfig"

    calls = []
    monkeypatch.setattr(record_wrapper, "native_main", lambda: calls.append("record"))
    monkeypatch.setattr(rollout_wrapper, "native_main", lambda: calls.append("rollout"))
    monkeypatch.setattr(teleoperate_wrapper, "native_main", lambda: calls.append("teleoperate"))

    record_wrapper.main()
    rollout_wrapper.main()
    teleoperate_wrapper.main()

    assert calls == ["record", "rollout", "teleoperate"]


def test_dual_train_wrapper_applies_overrideable_act_defaults(monkeypatch):
    import a1z_lerobot.scripts.train_act_dual as train_wrapper

    assert train_wrapper.with_act_defaults(["train"]) == [
        "train",
        "--policy.type=act",
        "--policy.device=cuda",
        "--batch_size=8",
    ]
    calls = []
    monkeypatch.setattr(train_wrapper, "native_main", lambda: calls.append(sys.argv.copy()))
    monkeypatch.setattr(
        sys,
        "argv",
        ["train", "--policy.device=cpu", "--batch_size=4"],
    )

    train_wrapper.main()

    assert calls == [
        ["train", "--policy.device=cpu", "--batch_size=4", "--policy.type=act"]
    ]
