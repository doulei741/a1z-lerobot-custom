from __future__ import annotations

from common import boolean, cameras_argv, mapping_args, proxy_process, request_json


def build_command(cfg: dict) -> list[str]:
    mode = cfg["mode"]
    command = [
        f"a1z-teleoperate-{mode}",
        f"--robot.type={'a1z' if mode == 'dual' else 'a1z_single'}",
        "--robot.id=a1z_web",
    ]
    if mode == "dual":
        command += [
            f"--robot.left_can={cfg['left_can']}",
            f"--robot.right_can={cfg['right_can']}",
            "--teleop.type=bi_a1z_leader",
            "--teleop.id=a1z_bi_leader",
            f"--teleop.left_id={cfg['left_leader_id']}",
            f"--teleop.right_id={cfg['right_leader_id']}",
            f"--teleop.left_arm_config.port={cfg['left_leader_port']}",
            f"--teleop.right_arm_config.port={cfg['right_leader_port']}",
        ]
        command += mapping_args("left_arm_config", cfg["left_mapping"])
        command += mapping_args("right_arm_config", cfg["right_mapping"])
    else:
        command += [
            f"--robot.can_channel={cfg['left_can']}",
            "--teleop.type=a1z_leader",
            f"--teleop.id={cfg['left_leader_id']}",
            f"--teleop.port={cfg['left_leader_port']}",
        ]
        command += mapping_args("", cfg["left_mapping"])
        command = [item.replace("--teleop..", "--teleop.") for item in command]
    command += [
        f"--robot.cameras={cameras_argv(cfg.get('cameras', {}))}",
        f"--robot.ema_alpha={cfg['ema_alpha']}",
        f"--robot.max_joint_delta={cfg['max_joint_delta']}",
        f"--robot.gripper_start_hold={boolean(cfg['gripper_start_hold'])}",
        f"--robot.return_home_on_disconnect={boolean(cfg['return_home_on_disconnect'])}",
        f"--fps={cfg['fps']}",
        f"--display_data={boolean(cfg['display_data'])}",
    ]
    if mode == "dual":
        command.append(f"--robot.open_grippers_on_disconnect={boolean(cfg['open_grippers_on_disconnect'])}")
    return command


if __name__ == "__main__":
    raise SystemExit(proxy_process(build_command(request_json()), ("A1Z connected.", "A1ZSingle connected.")))
