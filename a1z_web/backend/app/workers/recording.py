from __future__ import annotations

import json
import logging
import queue
import sys
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

import a1z_lerobot.robots.a1z_follower  # noqa: F401
import a1z_lerobot.robots.a1z_single  # noqa: F401
import a1z_lerobot.teleoperators.a1z_leader  # noqa: F401
import a1z_lerobot.teleoperators.bi_a1z_leader  # noqa: F401
import draccus
import yaml
from common import emit, request_json
from lerobot.common.control_utils import sanity_check_dataset_robot_compatibility
from lerobot.datasets import (
    LeRobotDataset,
    VideoEncodingManager,
    aggregate_pipeline_dataset_features,
    create_initial_features,
)
from lerobot.processor import make_default_processors
from lerobot.robots import make_robot_from_config
from lerobot.scripts.lerobot_record import RecordConfig, record_loop
from lerobot.teleoperators import make_teleoperator_from_config
from lerobot.utils.feature_utils import combine_feature_dicts


def merge_request(base: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(base)
    robot = data["robot"]
    robot.update({
        "ema_alpha": request["ema_alpha"],
        "max_joint_delta": request["max_joint_delta"],
        "gripper_start_hold": request["gripper_start_hold"],
        "return_home_on_disconnect": request["return_home_on_disconnect"],
    })
    if request["mode"] == "dual":
        robot.update({
            "left_can": request["left_can"],
            "right_can": request["right_can"],
            "open_grippers_on_disconnect": request["open_grippers_on_disconnect"],
        })
    else:
        robot["can_channel"] = request["left_can"]
    if request["mode"] == "dual" and request.get("right_wrist_serial"):
        robot["right_wrist_serial"] = request["right_wrist_serial"]
    selected = request.get("cameras") or {}
    if selected:
        robot["cameras"] = {
            name: {
                "type": "intelrealsense",
                "serial_number_or_name": camera["serial"],
                "width": camera["width"],
                "height": camera["height"],
                "fps": camera["fps"],
                "color_mode": "rgb",
                "use_depth": False,
            }
            for name, camera in selected.items()
            if camera.get("enabled") and camera.get("serial")
        }
    teleop = data["teleop"]
    if request["mode"] == "dual":
        teleop.update({"left_id": request["left_leader_id"], "right_id": request["right_leader_id"]})
        for side in ("left", "right"):
            arm = teleop[f"{side}_arm_config"]
            arm["port"] = request[f"{side}_leader_port"]
            mapping = request[f"{side}_mapping"]
            arm.update({"joint_signs": mapping["signs"], "joint_scales": mapping["scales"], "joint_offsets_rad": mapping["offsets_rad"]})
    else:
        mapping = request["left_mapping"]
        teleop.update({
            "id": request["left_leader_id"],
            "port": request["left_leader_port"],
            "joint_signs": mapping["signs"],
            "joint_scales": mapping["scales"],
            "joint_offsets_rad": mapping["offsets_rad"],
        })
    data["dataset"].update(request["dataset"])
    data.update({
        "resume": request["resume"],
        "display_data": request["display_data"],
        "display_compressed_images": request["display_compressed_images"],
        "play_sounds": request["play_sounds"],
    })
    return data


def buffer_frames(dataset: LeRobotDataset) -> int:
    buffer = dataset.episode_buffer
    if not buffer:
        return 0
    for value in buffer.values():
        try:
            return len(value)
        except TypeError:
            continue
    return 0


def main() -> int:
    request = request_json()
    root = Path.cwd()
    config_path = root / request["config_path"]
    config = draccus.decode(RecordConfig, merge_request(yaml.safe_load(config_path.read_text()), request))
    robot = make_robot_from_config(config.robot)
    teleop = make_teleoperator_from_config(config.teleop)
    teleop_processor, action_processor, observation_processor = make_default_processors()
    features = combine_feature_dicts(
        aggregate_pipeline_dataset_features(teleop_processor, create_initial_features(action=robot.action_features), use_videos=config.dataset.video),
        aggregate_pipeline_dataset_features(observation_processor, create_initial_features(observation=robot.observation_features), use_videos=config.dataset.video),
    )
    dataset: LeRobotDataset | None = None
    commands: queue.Queue[dict[str, Any]] = queue.Queue()
    events = {"exit_early": False, "rerecord_episode": False, "stop_recording": False}
    stop_reader = threading.Event()
    fault_announced = threading.Event()

    class ControlFaultHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.levelno < logging.ERROR or fault_announced.is_set():
                return
            if record.name.endswith("arm_robot") and record.getMessage().startswith(
                ("Control loop error", "Emergency stop")
            ):
                fault_announced.set()
                emit("fault", reason=f"{record.name}: {record.getMessage()}")

    control_fault_handler = ControlFaultHandler()
    logging.getLogger().addHandler(control_fault_handler)

    def reader() -> None:
        while not stop_reader.is_set():
            line = sys.stdin.readline()
            if not line:
                return
            payload = json.loads(line)
            commands.put(payload)
            if payload.get("command") in {"finish_episode", "quick_next", "rerecord", "stop"}:
                events["exit_early"] = True

    threading.Thread(target=reader, name="record-web-command-reader", daemon=True).start()
    try:
        if config.resume:
            dataset = LeRobotDataset.resume(config.dataset.repo_id, root=config.dataset.root)
            sanity_check_dataset_robot_compatibility(dataset, robot, config.dataset.fps, features)
        else:
            config.dataset.stamp_repo_id()
            dataset = LeRobotDataset.create(
                config.dataset.repo_id,
                config.dataset.fps,
                root=config.dataset.root,
                robot_type=robot.name,
                features=features,
                use_videos=config.dataset.video,
                image_writer_processes=config.dataset.num_image_writer_processes,
                image_writer_threads=config.dataset.num_image_writer_threads_per_camera * len(robot.cameras),
                batch_encoding_size=config.dataset.video_encoding_batch_size,
                camera_encoder=config.dataset.camera_encoder,
                encoder_threads=config.dataset.encoder_threads,
                streaming_encoding=config.dataset.streaming_encoding,
                encoder_queue_maxsize=config.dataset.encoder_queue_maxsize,
            )
        # Dataset contract is complete before either connect call.
        robot.connect()
        teleop.connect()
        emit("ready", phase="ready", existing_episodes=dataset.num_episodes)
        with VideoEncodingManager(dataset):
            while True:
                command = commands.get()
                name = command.get("command")
                if name == "stop":
                    break
                if name != "start_episode":
                    continue
                events["exit_early"] = False
                emit("phase", phase="recording")

                watcher_stop = threading.Event()
                def watcher(stop_event: threading.Event = watcher_stop) -> None:
                    announced = False
                    while not stop_event.wait(0.05):
                        count = buffer_frames(dataset)
                        if count and not announced:
                            emit("record_frame", frames=count)
                            announced = True
                thread = threading.Thread(target=watcher, daemon=True)
                thread.start()
                record_loop(
                    robot=robot,
                    events=events,
                    fps=config.dataset.fps,
                    teleop_action_processor=teleop_processor,
                    robot_action_processor=action_processor,
                    robot_observation_processor=observation_processor,
                    teleop=teleop,
                    dataset=dataset,
                    control_time_s=config.dataset.episode_time_s,
                    single_task=config.dataset.single_task,
                    display_data=config.display_data,
                    display_compressed_images=config.display_compressed_images,
                )
                watcher_stop.set()
                thread.join(timeout=0.2)
                frames = buffer_frames(dataset)
                trigger = commands.get_nowait() if not commands.empty() else {"command": "finish_episode"}
                if trigger.get("command") == "rerecord":
                    dataset.clear_episode_buffer()
                    emit("episode_discarded", reason="operator_rerecord")
                    commands.put({"command": "start_episode"})
                    continue
                if frames == 0:
                    dataset.clear_episode_buffer()
                    emit("fault", reason="Refused to save a zero-frame episode")
                    return 2
                emit("phase", phase="saving", frames=frames)
                dataset.save_episode()
                emit("saving_complete", total_episodes=dataset.num_episodes)
                emit("phase", phase="resetting")
                while True:
                    reset = commands.get()
                    if reset.get("command") == "stop":
                        return 0
                    if reset.get("command") == "reset_done":
                        emit("phase", phase="ready")
                        if trigger.get("command") == "quick_next":
                            commands.put({"command": "start_episode"})
                        break
    except KeyboardInterrupt:
        if dataset is not None and buffer_frames(dataset):
            dataset.clear_episode_buffer()
            emit("episode_discarded", reason="safe_stop")
        return 0
    except Exception as exc:
        if dataset is not None and buffer_frames(dataset):
            dataset.clear_episode_buffer()
        emit("fault", reason=f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        logging.getLogger().removeHandler(control_fault_handler)
        stop_reader.set()
        if dataset is not None:
            dataset.finalize()
        if robot.is_connected:
            robot.disconnect()
        if teleop.is_connected:
            teleop.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
