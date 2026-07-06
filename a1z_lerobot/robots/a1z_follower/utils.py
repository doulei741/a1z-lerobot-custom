"""Shared A1Z action post-processing: EMA smoothing + per-step joint clipping (pure, unit-testable)."""

import numpy as np

# Indices subject to clipping (joints only; grippers 6/13 of the A1Z 14D vector are not clipped)
JOINT_INDICES = list(range(6)) + list(range(7, 13))


def apply_ema(new: np.ndarray, prev: np.ndarray, alpha: float) -> np.ndarray:
    """Exponential moving average: out = alpha*new + (1-alpha)*prev. alpha=1 means no smoothing."""
    return (alpha * new + (1.0 - alpha) * prev).astype(np.float32)


def clip_joint_delta(
    action: np.ndarray, prev: np.ndarray, max_delta: float, joint_indices=JOINT_INDICES
) -> np.ndarray:
    """Clip per-step joint change (joint_indices only, grippers unclipped). No clipping when max_delta<=0."""
    if max_delta <= 0:
        return action.copy()
    clipped = action.copy()
    for idx in joint_indices:
        delta = clipped[idx] - prev[idx]
        clipped[idx] = prev[idx] + np.clip(delta, -max_delta, max_delta)
    return clipped
