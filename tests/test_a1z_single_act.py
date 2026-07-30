import torch


def test_act_forward_backward_accepts_two_rgb_views_and_seven_dimensional_io():
    from lerobot.configs import FeatureType, PolicyFeature
    from lerobot.policies.act.configuration_act import ACTConfig
    from lerobot.policies.act.modeling_act import ACTPolicy
    from lerobot.utils.constants import ACTION, OBS_STATE

    config = ACTConfig(
        input_features={
            OBS_STATE: PolicyFeature(type=FeatureType.STATE, shape=(7,)),
            "observation.images.top_rgb": PolicyFeature(
                type=FeatureType.VISUAL, shape=(3, 64, 64)
            ),
            "observation.images.wrist_rgb": PolicyFeature(
                type=FeatureType.VISUAL, shape=(3, 64, 64)
            ),
        },
        output_features={
            ACTION: PolicyFeature(type=FeatureType.ACTION, shape=(7,)),
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
        OBS_STATE: torch.zeros(1, 7),
        "observation.images.top_rgb": torch.rand(1, 3, 64, 64),
        "observation.images.wrist_rgb": torch.rand(1, 3, 64, 64),
        ACTION: torch.zeros(1, 2, 7),
        "action_is_pad": torch.zeros(1, 2, dtype=torch.bool),
    }

    loss, loss_dict = policy(batch)
    loss.backward()

    assert torch.isfinite(loss)
    assert loss_dict["l1_loss"] >= 0.0
    assert any(parameter.grad is not None for parameter in policy.parameters())
