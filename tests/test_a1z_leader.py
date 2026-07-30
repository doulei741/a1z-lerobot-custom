import math

import pytest


def test_map_leader_positions_converts_all_six_joints_and_gripper():
    from a1z_lerobot.teleoperators.a1z_leader.a1z_leader import map_leader_positions

    raw = {
        "arm_0": 0.0,
        "arm_1": 90.0,
        "arm_2": -90.0,
        "arm_3": 180.0,
        "arm_4": -180.0,
        "arm_5": 45.0,
        "gripper": 25.0,
    }

    action = map_leader_positions(
        raw,
        signs=(1, -1, 1, 1, -1, 1),
        scales=(1, 1, 2, 0.5, 1, 1),
        offsets_rad=(0, 0.1, 0, 0, -0.2, 0.3),
    )

    assert list(action) == [
        "arm_0.pos",
        "arm_1.pos",
        "arm_2.pos",
        "arm_3.pos",
        "arm_4.pos",
        "arm_5.pos",
        "gripper.pos",
    ]
    assert action["arm_0.pos"] == pytest.approx(0.0)
    assert action["arm_1.pos"] == pytest.approx(-math.pi / 2 + 0.1)
    assert action["arm_2.pos"] == pytest.approx(-math.pi)
    assert action["arm_3.pos"] == pytest.approx(math.pi / 2)
    assert action["arm_4.pos"] == pytest.approx(math.pi - 0.2)
    assert action["arm_5.pos"] == pytest.approx(math.pi / 4 + 0.3)
    assert action["gripper.pos"] == pytest.approx(0.25)


def test_leader_default_mapping_reverses_first_and_sixth_joint():
    from a1z_lerobot.teleoperators.a1z_leader.config_a1z_leader import A1ZLeaderConfig

    config = A1ZLeaderConfig(port="/dev/ttyACM0")

    assert config.joint_signs == (-1.0, 1.0, 1.0, 1.0, 1.0, -1.0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("joint_signs", (1, 1, 1)),
        ("joint_scales", (1, 1, 1)),
        ("joint_offsets_rad", (0, 0, 0)),
    ],
)
def test_leader_config_rejects_mapping_vectors_that_are_not_six_elements(field, value):
    from a1z_lerobot.teleoperators.a1z_leader.config_a1z_leader import A1ZLeaderConfig

    kwargs = {"port": "/dev/ttyACM0", field: value}

    with pytest.raises(ValueError, match=f"{field} must contain 6 values"):
        A1ZLeaderConfig(**kwargs)


def test_map_leader_positions_rejects_missing_or_nonfinite_values():
    from a1z_lerobot.teleoperators.a1z_leader.a1z_leader import map_leader_positions

    valid = {f"arm_{index}": 0.0 for index in range(6)}
    valid["gripper"] = 50.0

    missing = valid.copy()
    missing.pop("arm_4")
    with pytest.raises(ValueError, match="leader position keys"):
        map_leader_positions(missing)

    nonfinite = valid.copy()
    nonfinite["arm_2"] = math.nan
    with pytest.raises(ValueError, match="finite"):
        map_leader_positions(nonfinite)


def test_a1z_leader_uses_motor_ids_one_through_seven_and_emits_mapped_action(monkeypatch, tmp_path):
    import a1z_lerobot.teleoperators.a1z_leader.a1z_leader as leader_module
    from a1z_lerobot.teleoperators.a1z_leader.config_a1z_leader import A1ZLeaderConfig

    class FakeBus:
        def __init__(self, *, port, motors, calibration):
            self.port = port
            self.motors = motors
            self.calibration = calibration
            self.is_connected = True

        @property
        def is_calibrated(self):
            return True

        def sync_read(self, register):
            assert register == "Present_Position"
            return {
                "arm_0": 0.0,
                "arm_1": 10.0,
                "arm_2": 20.0,
                "arm_3": 30.0,
                "arm_4": 40.0,
                "arm_5": 50.0,
                "gripper": 75.0,
            }

    monkeypatch.setattr(leader_module, "FeetechMotorsBus", FakeBus)
    config = A1ZLeaderConfig(
        port="/dev/ttyACM7",
        id="seven_axis",
        calibration_dir=tmp_path,
    )

    leader = leader_module.A1ZLeader(config)
    action = leader.get_action()

    assert [motor.id for motor in leader.bus.motors.values()] == [1, 2, 3, 4, 5, 6, 7]
    assert list(leader.action_features) == [
        "arm_0.pos",
        "arm_1.pos",
        "arm_2.pos",
        "arm_3.pos",
        "arm_4.pos",
        "arm_5.pos",
        "gripper.pos",
    ]
    assert action["arm_5.pos"] == pytest.approx(-math.radians(50))
    assert action["gripper.pos"] == pytest.approx(0.75)


def test_a1z_leader_calibration_records_arm_five_range(monkeypatch, tmp_path):
    import a1z_lerobot.teleoperators.a1z_leader.a1z_leader as leader_module
    from a1z_lerobot.teleoperators.a1z_leader.config_a1z_leader import A1ZLeaderConfig

    class FakeBus:
        def __init__(self, *, port, motors, calibration):
            self.motors = motors
            self.ranged_motors = None
            self.written_calibration = None

        def disable_torque(self):
            pass

        def write(self, register, motor, value):
            assert register == "Operating_Mode"

        def set_half_turn_homings(self):
            return {name: index for index, name in enumerate(self.motors)}

        def record_ranges_of_motion(self, motors):
            self.ranged_motors = list(motors)
            return (
                {name: 100 + index for index, name in enumerate(motors)},
                {name: 3000 + index for index, name in enumerate(motors)},
            )

        def write_calibration(self, calibration):
            self.written_calibration = calibration

    monkeypatch.setattr(leader_module, "FeetechMotorsBus", FakeBus)
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    leader = leader_module.A1ZLeader(
        A1ZLeaderConfig(id="calibration_test", port="/dev/ttyACM7", calibration_dir=tmp_path)
    )
    monkeypatch.setattr(leader, "_save_calibration", lambda: None)

    leader.calibrate()

    assert leader.bus.ranged_motors == [
        "arm_0",
        "arm_1",
        "arm_2",
        "arm_3",
        "arm_4",
        "arm_5",
        "gripper",
    ]
    assert leader.calibration["arm_5"].range_min == 105
    assert leader.calibration["arm_5"].range_max == 3005
