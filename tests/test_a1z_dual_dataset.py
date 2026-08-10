import numpy as np


MOTOR_NAMES = [
    *(f"left_arm_{index}.pos" for index in range(6)),
    "left_ee_0.pos",
    *(f"right_arm_{index}.pos" for index in range(6)),
    "right_ee_0.pos",
]
CAMERA_NAMES = ["top_rgb", "left_wrist_rgb", "right_wrist_rgb"]


def test_lerobot_dataset_roundtrip_preserves_dual_arm_three_rgb_contract(tmp_path):
    from lerobot.datasets import LeRobotDataset
    from lerobot.utils.feature_utils import hw_to_dataset_features

    observation_features = {
        **dict.fromkeys(MOTOR_NAMES, float),
        **dict.fromkeys(CAMERA_NAMES, (480, 640, 3)),
    }
    features = {
        **hw_to_dataset_features(observation_features, "observation", use_video=False),
        **hw_to_dataset_features(
            dict.fromkeys(MOTOR_NAMES, float), "action", use_video=False
        ),
    }
    root = tmp_path / "dual_arm_dataset"
    dataset = LeRobotDataset.create(
        repo_id="local/a1z_dual_test",
        fps=30,
        features=features,
        root=root,
        robot_type="a1z",
        use_videos=False,
    )

    for frame_index in range(2):
        value = float(frame_index) / 10.0
        frame = {
            "observation.state": np.full(14, value, dtype=np.float32),
            "action": np.full(14, value + 0.01, dtype=np.float32),
            "task": "coordinate both test arms",
        }
        frame.update(
            {
                f"observation.images.{name}": np.full(
                    (480, 640, 3), frame_index + camera_index, dtype=np.uint8
                )
                for camera_index, name in enumerate(CAMERA_NAMES)
            }
        )
        dataset.add_frame(frame)
    dataset.save_episode()
    dataset.finalize()

    loaded = LeRobotDataset(repo_id="local/a1z_dual_test", root=root)

    assert loaded.fps == 30
    assert loaded.num_episodes == 1
    assert loaded.num_frames == 2
    assert loaded.meta.robot_type == "a1z"
    assert loaded.meta.features["observation.state"]["shape"] == (14,)
    assert loaded.meta.features["action"]["shape"] == (14,)
    for name in CAMERA_NAMES:
        assert loaded.meta.features[f"observation.images.{name}"]["shape"] == (
            480,
            640,
            3,
        )
    assert loaded[0]["observation.state"].shape == (14,)
    assert loaded[0]["action"].shape == (14,)
