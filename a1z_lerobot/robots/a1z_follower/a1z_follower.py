#!/usr/bin/env python

# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
# Copyright 2026 Galaxea. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""lerobot Robot adapter for the GALAXEA A1Z dual-arm (wraps A1ZDualArm).

14D vector = A1Z_DUAL.motors [left j1..j6, left_ee, right j1..j6, right_ee];
joint keys carry a `.pos` suffix (rollout engine keeps only .pos joint keys).
"""

import logging
import os
import time
from functools import cached_property

import numpy as np

from lerobot.cameras import make_cameras_from_configs
from lerobot.robots.robot import Robot
from lerobot.types import RobotAction, RobotObservation
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected
from a1z.robots.gripper import GRIPPER_CLOSE_RAD, GRIPPER_OPEN_RAD

from .hardware.config import A1Z_DUAL
from .hardware.dual_arm import A1ZDualArm
from .config_a1z_follower import A1ZConfig
from .utils import apply_ema, clip_joint_delta

logger = logging.getLogger(__name__)


class A1Z(Robot):
    """lerobot Robot adapter for the A1Z dual-arm: 14 `.pos` joint keys + 3 cameras; send_action does EMA + per-step clipping."""

    config_class = A1ZConfig
    name = "a1z"

    def __init__(self, config: A1ZConfig):
        super().__init__(config)
        self.config = config
        self.motors = list(A1Z_DUAL.motors)
        self.cameras = make_cameras_from_configs(config.cameras)
        self.arm: A1ZDualArm | None = None
        self._connected = False
        self._prev_action: np.ndarray | None = None
        self._gripper_leader_reference: list[float | None] = [None, None]
        self._gripper_follower_reference: list[float | None] = [None, None]

    @property
    def _motors_ft(self) -> dict[str, type]:
        return {f"{motor}.pos": float for motor in self.motors}

    @property
    def _cameras_ft(self) -> dict[str, tuple]:
        return {
            name: (cfg.height, cfg.width, 3) for name, cfg in self.config.cameras.items()
        }

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        return {**self._motors_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> dict[str, type]:
        return self._motors_ft

    @property
    def is_connected(self) -> bool:
        return self._connected and all(cam.is_connected for cam in self.cameras.values())

    @property
    def is_calibrated(self) -> bool:
        return True

    def calibrate(self) -> None:
        # A1Z calibration is handled by the GALAXEA SDK; nothing to do here.
        pass

    def configure(self) -> None:
        # A1Z motor configuration is handled by the GALAXEA SDK; nothing to do here.
        pass

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        arm = A1ZDualArm(self.config.left_can, self.config.right_can)
        self.arm = arm
        connected_cameras = []
        try:
            arm.start()
            for camera in self.cameras.values():
                camera.connect()
                connected_cameras.append(camera)
            state = arm.get_state().astype(np.float32)
            if state.shape != (14,) or not np.isfinite(state).all():
                raise ValueError("dual A1Z state must contain fourteen finite values")
            self._prev_action = state
            self._gripper_leader_reference = [None, None]
            self._gripper_follower_reference = [float(state[6]), float(state[13])]
            self._connected = True
        except Exception:
            for camera in reversed(connected_cameras):
                try:
                    camera.disconnect()
                except Exception:
                    pass
            try:
                arm.stop()
            except Exception:
                pass
            self.arm = None
            self._prev_action = None
            self._gripper_follower_reference = [None, None]
            raise
        logger.info("%s connected.", self)

    @check_if_not_connected
    def disconnect(self) -> None:
        arm = self.arm
        first_error: Exception | None = None
        try:
            for camera in reversed(list(self.cameras.values())):
                if camera.is_connected:
                    try:
                        camera.disconnect()
                    except Exception as error:
                        first_error = first_error or error
            if arm is not None:
                if self.config.open_grippers_on_disconnect:
                    try:
                        arm.command_gripper(GRIPPER_OPEN_RAD)
                        time.sleep(1.5)
                    except Exception as error:
                        first_error = first_error or error
                if self.config.return_home_on_disconnect:
                    try:
                        arm.move_to_home()
                    except Exception as error:
                        first_error = first_error or error
                try:
                    arm.stop()
                except Exception as error:
                    first_error = first_error or error
        finally:
            self.arm = None
            self._connected = False
            self._prev_action = None
            self._gripper_leader_reference = [None, None]
            self._gripper_follower_reference = [None, None]
        if first_error is not None:
            raise first_error
        logger.info("%s disconnected.", self)

    @check_if_not_connected
    def get_observation(self) -> RobotObservation:
        state = self.arm.get_state()
        obs: RobotObservation = {
            f"{motor}.pos": float(state[i]) for i, motor in enumerate(self.motors)
        }
        for name, cam in self.cameras.items():
            obs[name] = cam.async_read()
        self._maybe_dump_policy_view(obs)
        return obs

    @check_if_not_connected
    def send_action(self, action: RobotAction) -> RobotAction:
        action_keys = [f"{motor}.pos" for motor in self.motors]
        if set(action) != set(action_keys):
            raise ValueError(f"action keys must be exactly {action_keys}")
        target = np.array(
            [float(action[key]) for key in action_keys], dtype=np.float32
        )
        if target.shape != (14,) or not np.isfinite(target).all():
            raise ValueError("dual A1Z action must contain fourteen finite values")
        if self._prev_action is None:
            self._prev_action = target
        if self.config.gripper_start_hold:
            lower = min(GRIPPER_CLOSE_RAD, GRIPPER_OPEN_RAD)
            upper = max(GRIPPER_CLOSE_RAD, GRIPPER_OPEN_RAD)
            for reference_index, action_index in enumerate((6, 13)):
                if self._gripper_leader_reference[reference_index] is None:
                    self._gripper_leader_reference[reference_index] = float(target[action_index])
                follower_reference = self._gripper_follower_reference[reference_index]
                target[action_index] = np.clip(
                    float(follower_reference)
                    + float(target[action_index])
                    - float(self._gripper_leader_reference[reference_index]),
                    lower,
                    upper,
                )
        smoothed = apply_ema(target, self._prev_action, self.config.ema_alpha)
        clipped = clip_joint_delta(smoothed, self._prev_action, self.config.max_joint_delta)
        self._maybe_log_action_debug(target, clipped)
        self._prev_action = clipped.copy()
        self.arm.send_command(clipped)
        return {key: float(clipped[i]) for i, key in enumerate(action_keys)}

    # --- A1Z_DEBUG ---

    def _maybe_dump_policy_view(self, obs: RobotObservation) -> None:
        """Dump the camera frames the policy actually sees to tmp/policy_view/ (first frame only)."""
        if not os.environ.get("A1Z_DEBUG") or getattr(self, "_frames_dumped", False):
            return
        self._frames_dumped = True
        try:
            import cv2

            out = "tmp/policy_view"
            os.makedirs(out, exist_ok=True)
            for name in self.cameras:
                img = obs[name]  # image the policy actually receives (RGB)
                cv2.imwrite(f"{out}/{name}.png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            logger.info(f"[A1Z_DEBUG] policy view saved to {out}/<camera_key>.png")
        except Exception as e:
            logger.warning(f"[A1Z_DEBUG] saving images failed: {e}")

    def _maybe_log_action_debug(self, target: np.ndarray, clipped: np.ndarray) -> None:
        """Every 10 ticks, log the difference between target/clipped and the current state."""
        if not os.environ.get("A1Z_DEBUG"):
            return
        state = self.arm.get_state()
        self._dbg = getattr(self, "_dbg", 0) + 1
        if self._dbg % 10 == 1:
            d_tgt = np.abs(target - state)
            d_cmd = np.abs(clipped - state)
            logger.info(
                f"[A1Z_DEBUG] tick={self._dbg} "
                f"max|target-state|={d_tgt.max():.4f} (argmax {int(d_tgt.argmax())}) "
                f"max|cmd-state|={d_cmd.max():.4f} | "
                f"state[:3]={np.round(state[:3], 3)} target[:3]={np.round(target[:3], 3)}"
            )
