from __future__ import annotations

from common import boolean, cameras_argv, proxy_process, request_json


def build_command(cfg: dict) -> list[str]:
    mode = cfg["mode"]
    command = [
        f"a1z-rollout-act-{mode}",
        "--strategy.type=base",
        f"--inference.type={cfg['inference_type']}",
        f"--policy.path={cfg['policy_path']}",
        f"--robot.type={'a1z' if mode == 'dual' else 'a1z_single'}",
        f"--robot.cameras={cameras_argv(cfg.get('cameras', {}))}",
        f"--robot.ema_alpha={cfg['ema_alpha']}",
        f"--robot.max_joint_delta={cfg['max_joint_delta']}",
        "--robot.gripper_start_hold=false",
        f"--robot.return_home_on_disconnect={boolean(cfg['return_home_on_disconnect'])}",
        f"--fps={cfg['fps']}",
        f"--duration={cfg['duration']}",
        f"--task={cfg['task']}",
        f"--display_data={boolean(cfg['display_data'])}",
        "--return_to_initial_position=false",
    ]
    if mode == "dual":
        command += [
            f"--robot.left_can={cfg['left_can']}",
            f"--robot.right_can={cfg['right_can']}",
            f"--robot.open_grippers_on_disconnect={boolean(cfg['open_grippers_on_disconnect'])}",
        ]
    else:
        command.append(f"--robot.can_channel={cfg['left_can']}")
    return command


if __name__ == "__main__":
    # This marker is printed only after build_rollout_context has loaded and
    # validated the policy and then connected the robot.
    raise SystemExit(proxy_process(build_command(request_json()), ("Rollout setup complete",)))
