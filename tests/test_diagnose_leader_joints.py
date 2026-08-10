import pytest

from a1z_lerobot.tools.diagnose_leader_joints import (
    build_parser,
    observe_joint_deltas,
    run_diagnostic,
    validate_joint_indices,
)


def action(j2=0.0, j3=0.0):
    return {
        "arm_0.pos": 0.0,
        "arm_1.pos": j2,
        "arm_2.pos": j3,
        "arm_3.pos": 0.0,
        "arm_4.pos": 0.0,
        "arm_5.pos": 0.0,
        "gripper.pos": 0.5,
    }


class StepClock:
    def __init__(self, step):
        self.value = -step
        self.step = step

    def __call__(self):
        self.value += self.step
        return self.value


class SequenceLeader:
    def __init__(self, actions):
        self.actions = iter(actions)

    def get_action(self):
        return next(self.actions)


def test_validate_joint_indices_accepts_unique_zero_based_joints():
    assert validate_joint_indices([1, 2]) == (1, 2)


@pytest.mark.parametrize("indices", [[1, 1], [-1], [6], []])
def test_validate_joint_indices_rejects_invalid_values(indices):
    with pytest.raises(ValueError, match="unique values in 0..5"):
        validate_joint_indices(indices)


def test_observer_prints_only_threshold_crossings():
    output = []
    status = observe_joint_deltas(
        SequenceLeader([action(), action(j2=0.01), action(j2=0.03, j3=-0.04)]),
        joint_indices=(1, 2),
        duration_s=0.25,
        threshold_rad=0.02,
        monotonic=StepClock(0.1),
        sleep=lambda _: None,
        output=output.append,
    )

    assert status == "completed"
    assert len(output) == 2
    assert output[0].startswith("Baseline: J2=+0.000 rad | J3=+0.000 rad")
    assert "J2=+0.030 rad, delta_J2=+0.030 rad" in output[1]
    assert "J3=-0.040 rad, delta_J3=-0.040 rad" in output[1]
    assert "+0.010" not in output[1]


def test_run_diagnostic_connects_without_calibration_and_disconnects():
    events = []

    class FakeLeader(SequenceLeader):
        is_connected = False

        def connect(self, calibrate=True):
            self.is_connected = True
            events.append(("connect", calibrate))

        def disconnect(self):
            self.is_connected = False
            events.append("disconnect")

    def factory(config):
        assert config.port == "/dev/ttyUSB9"
        assert config.id == "bench_leader"
        return FakeLeader([action(), action()])

    status = run_diagnostic(
        "/dev/ttyUSB9",
        "bench_leader",
        duration_s=0.1,
        threshold_rad=0.02,
        joint_indices=(1, 2),
        leader_factory=factory,
        monotonic=StepClock(0.1),
        sleep=lambda _: None,
        output=lambda _: None,
    )

    assert status == "completed"
    assert events == [("connect", False), "disconnect"]


@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [(KeyboardInterrupt(), "interrupted"), (RuntimeError("read failed"), None)],
)
def test_run_diagnostic_always_disconnects(failure, expected_status):
    class FailingLeader:
        is_connected = False
        disconnect_calls = 0

        def connect(self, calibrate=True):
            self.is_connected = True

        def get_action(self):
            raise failure

        def disconnect(self):
            self.is_connected = False
            self.disconnect_calls += 1

    leader = FailingLeader()
    kwargs = {
        "duration_s": 0.1,
        "threshold_rad": 0.02,
        "joint_indices": (1, 2),
        "leader_factory": lambda config: leader,
        "monotonic": StepClock(0.1),
        "sleep": lambda _: None,
        "output": lambda _: None,
    }

    if expected_status is None:
        with pytest.raises(RuntimeError, match="read failed"):
            run_diagnostic("/dev/ttyUSB9", "bench_leader", **kwargs)
    else:
        assert run_diagnostic("/dev/ttyUSB9", "bench_leader", **kwargs) == expected_status
    assert leader.disconnect_calls == 1


def test_failed_handshake_closes_serial_port_without_writing_missing_motors():
    class FakeBus:
        def __init__(self):
            self.disconnect_calls = []

        def disconnect(self, disable_torque=True):
            self.disconnect_calls.append(disable_torque)

    class HandshakeFailureLeader:
        def __init__(self):
            self.is_connected = False
            self.bus = FakeBus()
            self.normal_disconnect_calls = 0

        def connect(self, calibrate=True):
            self.is_connected = True
            raise RuntimeError("missing motor IDs")

        def disconnect(self):
            self.normal_disconnect_calls += 1

    leader = HandshakeFailureLeader()

    with pytest.raises(RuntimeError, match="missing motor IDs"):
        run_diagnostic(
            "/dev/ttyUSB9",
            "bench_leader",
            leader_factory=lambda config: leader,
            monotonic=StepClock(0.1),
            sleep=lambda _: None,
            output=lambda _: None,
        )

    assert leader.normal_disconnect_calls == 0
    assert leader.bus.disconnect_calls == [False]


@pytest.mark.parametrize(
    ("duration_s", "threshold_rad", "joint_indices"),
    [(0.0, 0.02, (1, 2)), (1.0, 0.0, (1, 2)), (1.0, 0.02, (1, 6))],
)
def test_run_diagnostic_rejects_invalid_options_before_constructing_hardware(
    duration_s, threshold_rad, joint_indices
):
    factory_calls = []

    with pytest.raises(ValueError):
        run_diagnostic(
            "/dev/ttyUSB9",
            "bench_leader",
            duration_s=duration_s,
            threshold_rad=threshold_rad,
            joint_indices=joint_indices,
            leader_factory=lambda config: factory_calls.append(config),
            monotonic=StepClock(0.1),
            sleep=lambda _: None,
            output=lambda _: None,
        )

    assert factory_calls == []


def test_parser_has_safe_defaults_and_required_hardware_identity():
    parser = build_parser()

    args = parser.parse_args(["--port=/dev/ttyUSB9", "--id=bench_leader"])

    assert args.port == "/dev/ttyUSB9"
    assert args.leader_id == "bench_leader"
    assert args.duration_s == 30.0
    assert args.threshold_rad == 0.02
    assert args.joint_indices == [1, 2]
