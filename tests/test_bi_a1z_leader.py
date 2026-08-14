import pytest

LEFT_ACTION = {
    "arm_0.pos": 0.1,
    "arm_1.pos": 0.2,
    "arm_2.pos": 0.3,
    "arm_3.pos": 0.4,
    "arm_4.pos": 0.5,
    "arm_5.pos": 0.6,
    "gripper.pos": 0.0,
}

RIGHT_ACTION = {
    "arm_0.pos": 1.1,
    "arm_1.pos": 1.2,
    "arm_2.pos": 1.3,
    "arm_3.pos": 1.4,
    "arm_4.pos": 1.5,
    "arm_5.pos": 1.6,
    "gripper.pos": 1.0,
}


def test_compose_dual_action_matches_follower_order_and_gripper_units():
    from a1z.robots.gripper import GRIPPER_CLOSE_RAD, GRIPPER_OPEN_RAD
    from a1z_lerobot.robots.a1z_follower.hardware.config import A1Z_DUAL
    from a1z_lerobot.teleoperators.bi_a1z_leader import compose_dual_action

    action = compose_dual_action(LEFT_ACTION, RIGHT_ACTION)

    assert list(action) == [f"{motor}.pos" for motor in A1Z_DUAL.motors]
    assert action["left_arm_0.pos"] == pytest.approx(0.1)
    assert action["right_arm_5.pos"] == pytest.approx(1.6)
    assert action["left_ee_0.pos"] == pytest.approx(GRIPPER_CLOSE_RAD)
    assert action["right_ee_0.pos"] == pytest.approx(GRIPPER_OPEN_RAD)


@pytest.mark.parametrize(
    "broken",
    [
        {key: value for key, value in LEFT_ACTION.items() if key != "arm_5.pos"},
        {**LEFT_ACTION, "gripper.pos": float("nan")},
    ],
)
def test_compose_dual_action_rejects_invalid_single_leader_actions(broken):
    from a1z_lerobot.teleoperators.bi_a1z_leader import compose_dual_action

    with pytest.raises(ValueError):
        compose_dual_action(broken, RIGHT_ACTION)


def test_dual_leader_config_requires_independent_serial_buses():
    from a1z_lerobot.teleoperators.a1z_leader import A1ZLeaderConfigBase
    from a1z_lerobot.teleoperators.bi_a1z_leader import BiA1ZLeaderConfig

    with pytest.raises(ValueError, match="different serial ports"):
        BiA1ZLeaderConfig(
            id="dual",
            left_arm_config=A1ZLeaderConfigBase(port="/dev/ttyACM0"),
            right_arm_config=A1ZLeaderConfigBase(port="/dev/ttyACM0"),
        )


def test_dual_leader_preserves_independent_child_configuration(monkeypatch):
    import a1z_lerobot.teleoperators.bi_a1z_leader.bi_a1z_leader as module
    from a1z_lerobot.teleoperators.a1z_leader import A1ZLeaderConfigBase
    from a1z_lerobot.teleoperators.bi_a1z_leader import BiA1ZLeader, BiA1ZLeaderConfig

    created = []

    class FakeLeader:
        def __init__(self, config):
            self.config = config
            self.is_connected = False
            created.append(self)

        @property
        def action_features(self):
            return dict.fromkeys(LEFT_ACTION, float)

        @property
        def is_calibrated(self):
            return True

        def connect(self, calibrate=True):
            self.is_connected = True

        def disconnect(self):
            self.is_connected = False

        def calibrate(self):
            pass

        def configure(self):
            pass

        def setup_motors(self):
            pass

        def get_action(self):
            return LEFT_ACTION if self.config.id == "left_leader" else RIGHT_ACTION

    monkeypatch.setattr(module, "A1ZLeader", FakeLeader)
    config = BiA1ZLeaderConfig(
        id="dual",
        left_id="left_leader",
        right_id="right_leader",
        left_arm_config=A1ZLeaderConfigBase(
            port="/dev/ttyACM0",
            joint_signs=(-1, 1, 1, 1, 1, -1),
            auto_use_calibration=True,
        ),
        right_arm_config=A1ZLeaderConfigBase(
            port="/dev/ttyACM1",
            joint_signs=(1, -1, -1, 1, 1, 1),
        ),
    )

    leader = BiA1ZLeader(config)
    leader.connect()
    action = leader.get_action()
    leader.disconnect()

    assert [child.config.id for child in created] == ["left_leader", "right_leader"]
    assert [child.config.port for child in created] == ["/dev/ttyACM0", "/dev/ttyACM1"]
    assert created[0].config.joint_signs == (-1, 1, 1, 1, 1, -1)
    assert created[1].config.joint_signs == (1, -1, -1, 1, 1, 1)
    assert created[0].config.auto_use_calibration is True
    assert created[1].config.auto_use_calibration is False
    assert action["left_arm_0.pos"] == pytest.approx(0.1)
    assert action["right_arm_0.pos"] == pytest.approx(1.1)
    assert not leader.is_connected


def test_dual_leader_cleans_up_left_when_right_connection_fails(monkeypatch):
    import a1z_lerobot.teleoperators.bi_a1z_leader.bi_a1z_leader as module
    from a1z_lerobot.teleoperators.a1z_leader import A1ZLeaderConfigBase
    from a1z_lerobot.teleoperators.bi_a1z_leader import BiA1ZLeader, BiA1ZLeaderConfig

    events = []

    class FakeLeader:
        def __init__(self, config):
            self.config = config
            self.is_connected = False

        @property
        def action_features(self):
            return dict.fromkeys(LEFT_ACTION, float)

        def connect(self, calibrate=True):
            events.append(f"connect:{self.config.id}")
            if self.config.id == "right":
                raise RuntimeError("right unavailable")
            self.is_connected = True

        def disconnect(self):
            events.append(f"disconnect:{self.config.id}")
            self.is_connected = False

    monkeypatch.setattr(module, "A1ZLeader", FakeLeader)
    leader = BiA1ZLeader(
        BiA1ZLeaderConfig(
            id="dual",
            left_id="left",
            right_id="right",
            left_arm_config=A1ZLeaderConfigBase(port="/dev/ttyACM0"),
            right_arm_config=A1ZLeaderConfigBase(port="/dev/ttyACM1"),
        )
    )

    with pytest.raises(RuntimeError, match="right unavailable"):
        leader.connect()

    assert events == ["connect:left", "connect:right", "disconnect:left"]
