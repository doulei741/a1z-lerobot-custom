#!/usr/bin/env python
"""Convert a1z_data_collection HDF5 episodes to a LeRobot v3.0 dataset.

Merged schema: observation.state(14)+action(14)+3 videos. Gripper norm->rad.
Run in the a1z_lerobot conda env. Usage:
    python -m a1z_lerobot.tools.hdf5_to_lerobot --src <dir> --repo-id NAME
"""
import argparse, glob, os, re, sys

import cv2
import h5py
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from a1z_lerobot.robots.a1z_follower.hardware.config import A1Z_DUAL
from a1z.robots.gripper import GRIPPER_OPEN_RAD, GRIPPER_CLOSE_RAD

GRIPPER_IDX = [6, 13]
CAM_KEYS = ["head_rgb", "left_wrist_rgb", "right_wrist_rgb"]
CAM_SRC_TO_DST = {"cam_high": "head_rgb", "cam_left_wrist": "left_wrist_rgb", "cam_right_wrist": "right_wrist_rgb"}


def norm_to_rad(vec):
    """Gripper cols [6,13] from SDK norm[0,1] (0 closed/1 open) to raw rad. Arm cols unchanged."""
    out = np.asarray(vec, dtype=np.float32).copy()
    n = np.clip(out[..., GRIPPER_IDX], 0.0, 1.0)
    out[..., GRIPPER_IDX] = GRIPPER_CLOSE_RAD + n * (GRIPPER_OPEN_RAD - GRIPPER_CLOSE_RAD)
    return out


def nearest_indices(base_ts, cam_ts):
    """For each base timestamp, index of nearest cam frame (clamped to range)."""
    base = np.asarray(base_ts, float); cam = np.asarray(cam_ts, float)
    if len(cam) == 1:
        return np.zeros(len(base), int)
    idx = np.clip(np.searchsorted(cam, base), 1, len(cam) - 1)
    pick_left = (base - cam[idx - 1]) <= (cam[idx] - base)
    return np.clip(idx - pick_left.astype(int), 0, len(cam) - 1)


def build_features(fps, motors, height, width):
    f = {
        "observation.state": {"dtype": "float32", "shape": (len(motors),), "names": list(motors)},
        "action": {"dtype": "float32", "shape": (len(motors),), "names": list(motors)},
    }
    for c in CAM_KEYS:
        f[f"observation.images.{c}"] = {"dtype": "video", "shape": (height, width, 3),
                                        "names": ["height", "width", "channels"]}
    return f


def convert_episode(ds, h5path, task):
    with h5py.File(h5path, "r") as f:
        state = norm_to_rad(f["arm/state"][:])
        action = norm_to_rad(f["arm/action"][:])
        base = f["arm/follower_timestamps"][:]
        n = len(state)
        ep_task = task or f.attrs.get("task", "")
        cams = {}
        for src, dst in CAM_SRC_TO_DST.items():
            frames = f[f"cameras/{src}/frames"][:]
            nidx = nearest_indices(base, f[f"cameras/{src}/timestamps"][:])
            cams[dst] = (frames, nidx)
        for i in range(n):
            frame = {"observation.state": state[i], "action": action[i], "task": ep_task}
            for dst, (frames, nidx) in cams.items():
                img = cv2.imdecode(np.frombuffer(frames[nidx[i]], np.uint8), cv2.IMREAD_COLOR)
                frame[f"observation.images.{dst}"] = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            ds.add_frame(frame)
    ds.save_episode()


def convert_dir(src, repo_id, root, task, fps, height, width):
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    eps = sorted(
        glob.glob(os.path.join(src, "episode_*.hdf5")),
        key=lambda p: int(re.findall(r"\d+", os.path.basename(p))[0]),
    )
    if not eps:
        raise FileNotFoundError(f"No episode_*.hdf5 under {src}")
    ds = LeRobotDataset.create(
        repo_id=repo_id, fps=fps, root=root, robot_type="a1z",
        features=build_features(fps, A1Z_DUAL.motors, height, width),
        use_videos=True, image_writer_processes=2, image_writer_threads=4,
    )
    for p in eps:
        print("converting", p)
        convert_episode(ds, p, task)
    ds.finalize()
    print("done:", root)


def main():
    ap = argparse.ArgumentParser(description="Convert two_master_slave HDF5 to a LeRobot v3.0 dataset.")
    ap.add_argument("--src", default="a1z_data_collection/data/two_master_slave")
    ap.add_argument("--repo-id", required=True)
    ap.add_argument("--root", default=None)
    ap.add_argument("--task", default=None)
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    root = a.root or f"dataset/{a.repo_id}"
    convert_dir(a.src, a.repo_id, root, a.task, a.fps, 720, 1280)


if __name__ == "__main__":
    main()
