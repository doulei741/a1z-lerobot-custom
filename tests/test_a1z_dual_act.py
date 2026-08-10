from types import SimpleNamespace

import pytest
import torch


CAMERA_FEATURES = {
    "top_rgb": (480, 640, 3),
    "left_wrist_rgb": (480, 640, 3),
    "right_wrist_rgb": (480, 640, 3),
}


def _policy_contract(state_shape=(14,), action_shape=(14,), camera_features=CAMERA_FEATURES):
    inputs = {"observation.state": SimpleNamespace(shape=state_shape)}
    inputs.update(
        {
            f"observation.images.{name}": SimpleNamespace(
                shape=(shape[2], shape[0], shape[1])
            )
            for name, shape in camera_features.items()
        }
    )
    return SimpleNamespace(
        input_features=inputs,
        output_features={"action": SimpleNamespace(shape=action_shape)},
    )


def test_policy_preflight_accepts_exact_dual_arm_three_camera_contract():
    from a1z_lerobot.robots.a1z_follower.a1z_follower import validate_policy_features

    validate_policy_features(_policy_contract(), CAMERA_FEATURES)


@pytest.mark.parametrize(
    ("policy", "camera_features", "message"),
    [
        (_policy_contract(state_shape=(7,)), CAMERA_FEATURES, "state"),
        (_policy_contract(action_shape=(7,)), CAMERA_FEATURES, "action"),
        (_policy_contract(), {"top_rgb": (480, 640, 3)}, "visual"),
    ],
)
def test_policy_preflight_rejects_dual_feature_mismatch(
    policy, camera_features, message
):
    from a1z_lerobot.robots.a1z_follower.a1z_follower import validate_policy_features

    with pytest.raises(ValueError, match=message):
        validate_policy_features(policy, camera_features)


def test_act_forward_backward_accepts_three_rgb_views_and_fourteen_dimensional_io():
    from lerobot.configs import FeatureType, PolicyFeature
    from lerobot.policies.act.configuration_act import ACTConfig
    from lerobot.policies.act.modeling_act import ACTPolicy
    from lerobot.utils.constants import ACTION, OBS_STATE

    visual_keys = [
        "observation.images.top_rgb",
        "observation.images.left_wrist_rgb",
        "observation.images.right_wrist_rgb",
    ]
    config = ACTConfig(
        input_features={
            OBS_STATE: PolicyFeature(type=FeatureType.STATE, shape=(14,)),
            **{
                key: PolicyFeature(type=FeatureType.VISUAL, shape=(3, 64, 64))
                for key in visual_keys
            },
        },
        output_features={
            ACTION: PolicyFeature(type=FeatureType.ACTION, shape=(14,)),
        },
        device="cpu",
        chunk_size=2,
        n_action_steps=1,
        dim_model=64,
        n_heads=4,
        dim_feedforward=128,
        n_encoder_layers=1,
        n_decoder_layers=1,
        n_vae_encoder_layers=1,
        latent_dim=8,
        pretrained_backbone_weights=None,
    )
    policy = ACTPolicy(config)
    batch = {
        OBS_STATE: torch.zeros(1, 14),
        **{key: torch.rand(1, 3, 64, 64) for key in visual_keys},
        ACTION: torch.zeros(1, 2, 14),
        "action_is_pad": torch.zeros(1, 2, dtype=torch.bool),
    }

    loss, loss_dict = policy(batch)
    loss.backward()

    assert torch.isfinite(loss)
    assert loss_dict["l1_loss"] >= 0.0
    assert any(parameter.grad is not None for parameter in policy.parameters())
