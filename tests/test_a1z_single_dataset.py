import numpy as np


MOTOR_NAMES = [*(f"arm_{index}.pos" for index in range(6)), "gripper.pos"]


def test_lerobot_dataset_roundtrip_preserves_single_arm_two_rgb_contract(tmp_path):
    from lerobot.datasets import LeRobotDataset
    from lerobot.utils.feature_utils import hw_to_dataset_features

    observation_features = {
        **dict.fromkeys(MOTOR_NAMES, float),
        "top_rgb": (480, 640, 3),
        "wrist_rgb": (480, 640, 3),
    }
    features = {
        **hw_to_dataset_features(observation_features, "observation", use_video=False),
        **hw_to_dataset_features(dict.fromkeys(MOTOR_NAMES, float), "action", use_video=False),
    }
    root = tmp_path / "single_arm_dataset"
    dataset = LeRobotDataset.create(
        repo_id="local/a1z_single_test",
        fps=30,
        features=features,
        root=root,
        robot_type="a1z_single",
        use_videos=False,
    )

    for frame_index in range(2):
        value = float(frame_index) / 10.0
        dataset.add_frame(
            {
                "observation.state": np.full(7, value, dtype=np.float32),
                "action": np.full(7, value + 0.01, dtype=np.float32),
                "observation.images.top_rgb": np.full(
                    (480, 640, 3), frame_index, dtype=np.uint8
                ),
                "observation.images.wrist_rgb": np.full(
                    (480, 640, 3), frame_index + 1, dtype=np.uint8
                ),
                "task": "move the test object",
            }
        )
    dataset.save_episode()
    dataset.finalize()

    loaded = LeRobotDataset(repo_id="local/a1z_single_test", root=root)

    assert loaded.fps == 30
    assert loaded.num_episodes == 1
    assert loaded.num_frames == 2
    assert loaded.meta.robot_type == "a1z_single"
    assert loaded.meta.features["observation.state"]["shape"] == (7,)
    assert loaded.meta.features["action"]["shape"] == (7,)
    assert loaded.meta.features["observation.images.top_rgb"]["shape"] == (480, 640, 3)
    assert loaded.meta.features["observation.images.wrist_rgb"]["shape"] == (480, 640, 3)
    assert loaded[0]["observation.state"].shape == (7,)
    assert loaded[0]["action"].shape == (7,)
