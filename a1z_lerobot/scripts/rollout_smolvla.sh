export HF_HUB_OFFLINE=1

python -m a1z_lerobot.scripts.rollout \
    --config_path=a1z_lerobot/configs/rollout_a1z.yaml \
    --policy.path=a1z_lerobot/lerobot/outputs/smolvla_crush_lemon_20260624_220944/checkpoints/030000/pretrained_model \
    --task="a1z crush lemon" \
    --fps=10 \
    --inference.type=rtc
