from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, Query, Request, WebSocket, WebSocketDisconnect, status

from app.core.errors import ApiError
from app.models.tasks import TaskStatus, TaskType
from app.schemas.workflows import (
    CalibrationStartRequest,
    DomainAction,
    InferenceRequest,
    PairingCalculateRequest,
    PairingReadRequest,
    PairingSaveRequest,
    PairingVerifyRequest,
    PolicyInspectRequest,
    RecordAction,
    RecordingRequest,
    StopRequest,
    TeleoperationRequest,
)
from app.services.calibration import CalibrationSession
from app.services.record_state import RecordSession

router = APIRouter()
ws_router = APIRouter()


def services(request: Request):
    return request.app.state.services


def motion_resources(payload: TeleoperationRequest | InferenceRequest | RecordingRequest) -> set[str]:
    resources = {payload.left_can, "a1z_left"}
    if payload.mode == "dual":
        resources.update({payload.right_can, "a1z_right"})
    if isinstance(payload, (TeleoperationRequest, RecordingRequest)):
        resources.add("leader_left")
        if payload.mode == "dual":
            resources.add("leader_right")
    for name, camera in payload.cameras.items():
        if camera.enabled:
            resources.add(name)
    if isinstance(payload, RecordingRequest) and not payload.cameras:
        resources.update({"top_camera", "left_wrist_camera"})
        if payload.mode == "dual":
            resources.add("right_wrist_camera")
    return resources


def require_safety(confirmed: bool) -> None:
    if not confirmed:
        raise ApiError(
            "motion_confirmation_required",
            "Confirm the work area and physical emergency-stop checklist before motion",
            status_code=409,
        )


@router.get("/system/health")
async def system_health(request: Request) -> dict[str, Any]:
    svc = services(request)
    owners = await svc.hardware.snapshot()
    if svc.settings.mock:
        resources = {"can0": "healthy", "can1": "healthy", "leaders": "healthy", "cameras": "healthy"}
    else:
        inventory = await svc.health.discover_devices()
        resources = {
            **{item["name"]: item["state"] for item in inventory["can"]},
            "leaders": "healthy" if inventory["leaders"] else "offline",
            "cameras": "healthy" if inventory["cameras"] else "offline",
        }
    states = set(resources.values())
    return {
        "mode": "mock" if svc.settings.mock else "real",
        "hardware_motion_enabled": svc.settings.allow_hardware,
        "status": "fault" if "fault" in states else "degraded" if "offline" in states else "healthy",
        "resources": resources,
        "owners": owners,
    }


@router.get("/devices")
async def devices(request: Request) -> dict[str, Any]:
    svc = services(request)
    if svc.settings.mock:
        return {
            "mock": True,
            "can": [{"name": "can0", "state": "healthy", "bitrate": 1000000}, {"name": "can1", "state": "healthy", "bitrate": 1000000}],
            "leaders": [{"port": "/dev/ttyACM0", "state": "healthy"}, {"port": "/dev/ttyACM1", "state": "healthy"}],
            "cameras": [
                {"name": "top_camera", "serial": "MOCK-TOP", "state": "healthy"},
                {"name": "left_wrist_camera", "serial": "MOCK-LEFT", "state": "healthy"},
                {"name": "right_wrist_camera", "serial": "MOCK-RIGHT", "state": "healthy"},
            ],
        }
    return await svc.health.discover_devices()


@router.get("/schema/{workflow}")
async def workflow_schema(workflow: str) -> dict[str, Any]:
    models = {
        "calibration": CalibrationStartRequest,
        "pairing": PairingReadRequest,
        "teleoperation": TeleoperationRequest,
        "recording": RecordingRequest,
        "inference": InferenceRequest,
    }
    model = models.get(workflow)
    if model is None:
        raise ApiError("schema_not_found", f"Unknown workflow schema: {workflow}", status_code=404)
    return {
        "workflow": workflow,
        "schema": model.model_json_schema(),
        "ui": {
            "fps": {"unit": "Hz", "description": "LeRobot outer-loop target", "danger_level": "normal", "requires_restart": True},
            "ema_alpha": {"unit": "ratio", "description": "Existing A1Z send_action EMA", "danger_level": "safety", "requires_restart": True},
            "max_joint_delta": {"unit": "rad/step", "description": "Existing A1Z per-step action limiter", "danger_level": "safety", "requires_restart": True},
            "gripper_start_hold": {"description": "Relative gripper hold at startup; locked false for ACT", "danger_level": "safety", "requires_restart": True},
        },
    }


@router.get("/tasks")
async def tasks(request: Request):
    return services(request).tasks.list()


@router.get("/tasks/{task_id}")
async def task(task_id: str, request: Request):
    runtime = services(request).tasks.get(task_id)
    payload = runtime.info.model_dump(mode="json")
    if runtime.record is not None:
        payload.update(record_payload(runtime.record))
    return payload


@router.get("/tasks/{task_id}/logs")
async def task_logs(task_id: str, request: Request, after: int = 0):
    items = services(request).tasks.logs_after(task_id, after)
    return {"items": [entry.model_dump(mode="json") for entry in items], "next_seq": items[-1].seq if items else after}


@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str, request: Request, payload: StopRequest | None = None):
    return await services(request).tasks.stop(task_id, (payload or StopRequest()).reason)


@router.post("/teleop/start", status_code=status.HTTP_201_CREATED)
async def start_teleop(payload: TeleoperationRequest, request: Request):
    require_safety(payload.safety_confirmed)
    svc = services(request)
    argv = svc.commands.teleoperation(payload)
    return await svc.tasks.start(TaskType.TELEOPERATION, motion_resources(payload), argv=argv, metadata={"config": payload.model_dump(mode="json")})


@router.post("/teleop/{task_id}/stop")
async def stop_teleop(task_id: str, request: Request):
    return await services(request).tasks.stop(task_id)


@router.get("/calibration/profiles")
async def calibration_profiles(request: Request):
    return {"items": services(request).profiles.list()}


@router.get("/calibration/status")
async def calibration_status(
    request: Request,
    leader_id: str = Query(pattern=r"^[A-Za-z0-9_-]+$", min_length=1, max_length=80),
):
    path = (
        Path.home()
        / ".cache"
        / "huggingface"
        / "lerobot"
        / "calibration"
        / "teleoperators"
        / "a1z_leader"
        / f"{leader_id}.json"
    )
    return {"leader_id": leader_id, "exists": path.exists(), "path": str(path)}


@router.post("/calibration/start", status_code=status.HTTP_201_CREATED)
async def calibration_start(payload: CalibrationStartRequest, request: Request):
    svc = services(request)
    argv = svc.commands.calibration(payload)
    info = await svc.tasks.start(
        TaskType.CALIBRATION,
        {f"leader_{payload.side}"},
        argv=argv,
        metadata={"side": payload.side, "port": payload.port, "leader_id": payload.leader_id},
    )
    svc.tasks.get(info.task_id).calibration = CalibrationSession()
    return info


async def calibration_command(task_id: str, command: str, action: DomainAction, request: Request):
    svc = services(request)
    runtime = svc.tasks.get(task_id)
    session = getattr(runtime, "calibration", None)
    if runtime.info.task_type is not TaskType.CALIBRATION or session is None:
        raise ApiError("wrong_task_type", "Task is not a calibration task", status_code=409)
    result = session.apply(command, action.client_action_id)
    if svc.settings.mock and command == "save":
        session.phase = "completed"
        session.calibration_status = "saved"
        result = session.payload()
    await svc.tasks.send_command(task_id, {"command": command, **action.model_dump()})
    await svc.events.publish("calibration", result, task_id)
    if svc.settings.mock and command == "save":
        await svc.tasks.complete_mock(task_id)
    return result


@router.post("/calibration/{task_id}/middle")
async def calibration_middle(task_id: str, action: DomainAction, request: Request):
    return await calibration_command(task_id, "middle", action, request)


@router.post("/calibration/{task_id}/record-range")
async def calibration_range(task_id: str, action: DomainAction, request: Request):
    return await calibration_command(task_id, "record_range", action, request)


@router.post("/calibration/{task_id}/stop-range")
async def calibration_stop_range(task_id: str, action: DomainAction, request: Request):
    return await calibration_command(task_id, "stop_range", action, request)


@router.post("/calibration/{task_id}/save")
async def calibration_save(task_id: str, action: DomainAction, request: Request):
    return await calibration_command(task_id, "save", action, request)


@router.post("/calibration/{task_id}/cancel")
async def calibration_cancel(task_id: str, action: DomainAction, request: Request):
    result = await calibration_command(task_id, "cancel", action, request)
    await services(request).tasks.stop(task_id, "calibration_cancelled")
    return result


@router.post("/pairing/calculate")
async def pairing_calculate(payload: PairingCalculateRequest, request: Request):
    offsets = services(request).profiles.calculate(payload.leader_rad, payload.follower_rad, payload.signs, payload.scales)
    return {**payload.model_dump(), "offsets_rad": offsets}


@router.post("/pairing/read", status_code=status.HTTP_201_CREATED)
async def pairing_read(payload: PairingReadRequest, request: Request):
    require_safety(payload.safety_confirmed)
    svc = services(request)
    info = await svc.tasks.start(
        TaskType.PAIRING,
        {f"leader_{payload.side}", payload.can_interface, f"a1z_{payload.side}"},
        argv=svc.commands.pairing(payload),
        metadata={"request": payload.model_dump(mode="json")},
    )
    if svc.settings.mock:
        result = {
            "side": payload.side,
            "leader_rad": [0.12, -0.31, 0.28, 0.04, -0.02, 0.08],
            "follower_rad": [-0.12, 0.31, 0.28, 0.04, -0.02, -0.08],
            "signs": payload.signs,
            "scales": payload.scales,
        }
        result["offsets_rad"] = svc.profiles.calculate(
            result["leader_rad"], result["follower_rad"], payload.signs, payload.scales
        )
        svc.tasks.get(info.task_id).info.metadata["pairing_result"] = result
        await svc.tasks.complete_mock(info.task_id)
    return info


@router.post("/pairing/verify")
async def pairing_verify(payload: PairingVerifyRequest):
    predicted = [
        payload.leader_rad[index] * payload.scales[index] * payload.signs[index]
        + payload.offsets_rad[index]
        for index in range(6)
    ]
    errors = [round(predicted[index] - payload.follower_rad[index], 9) for index in range(6)]
    return {
        "verified": max(abs(value) for value in errors) <= payload.tolerance_rad,
        "errors_rad": errors,
        "tolerance_rad": payload.tolerance_rad,
    }


@router.post("/pairing/save")
async def pairing_save(payload: PairingSaveRequest, request: Request):
    profile = payload.model_dump()
    profile["offsets_rad"] = services(request).profiles.calculate(payload.leader_rad, payload.follower_rad, payload.signs, payload.scales)
    return services(request).profiles.save(profile)


@router.post("/record/start", status_code=status.HTTP_201_CREATED)
async def start_record(payload: RecordingRequest, request: Request):
    require_safety(payload.safety_confirmed)
    svc = services(request)
    report = svc.datasets.inspect(payload)
    if not report["compatible"]:
        raise ApiError(
            "resume_schema_incompatible",
            "Dataset contract is incompatible with the selected A1Z workflow",
            details=report,
            status_code=409,
        )
    argv = svc.commands.recording(payload)
    info = await svc.tasks.start(TaskType.RECORDING, motion_resources(payload), argv=argv, metadata={"config": payload.model_dump(mode="json")})
    runtime = svc.tasks.get(info.task_id)
    existing = svc.dataset_existing_episodes(payload)
    runtime.record = RecordSession(existing_episodes=existing, add_episodes=payload.dataset.num_episodes)
    return info


@router.post("/record/compatibility")
async def record_compatibility(payload: RecordingRequest, request: Request):
    return services(request).datasets.inspect(payload)


def record_payload(session: RecordSession) -> dict[str, Any]:
    return {
        "record_phase": session.phase.value,
        "episode_index": session.episode_index,
        "existing_episodes": session.existing_episodes,
        "add_episodes": session.add_episodes,
        "total_after_session": session.existing_episodes + session.add_episodes,
        "saved_episodes": session.saved_episodes,
        "frames": session.frames,
        "quick_next_armed": session.quick_next_armed,
        "current_episode_invalid": session.current_episode_invalid,
        "last_trusted_episode": session.last_trusted_episode,
        "fault_reason": session.fault_reason,
    }


async def record_command(task_id: str, action: RecordAction, command: str, request: Request):
    svc = services(request)
    runtime = svc.tasks.get(task_id)
    if runtime.info.task_type is not TaskType.RECORDING or runtime.record is None:
        raise ApiError("wrong_task_type", "Task is not a recording task", status_code=409)
    if not runtime.record.is_duplicate(action.client_action_id) and action.episode_index != runtime.record.episode_index:
        raise ApiError(
            "stale_episode_action",
            "Action episode index does not match the active session",
            details={"expected": runtime.record.episode_index, "actual": action.episode_index},
            status_code=409,
        )
    if command == "reset_done" and runtime.record.quick_next_armed:
        unhealthy = {
            name: state.value
            for name, state in runtime.info.health.items()
            if state.value != "healthy"
        }
        if unhealthy or runtime.info.status is TaskStatus.FAULTED:
            raise ApiError(
                "quick_next_health_check_failed",
                "Quick Next requires every owned hardware resource to be healthy",
                details={"resources": unhealthy},
                status_code=409,
            )
    result = runtime.record.apply(command, action.client_action_id)
    await svc.tasks.send_command(task_id, {"command": command, **action.model_dump()})
    await svc.tasks.log(task_id, "INFO", "record_protocol", f"{command} -> {result.phase.value}")
    await svc.events.publish("record_phase", record_payload(runtime.record), task_id)
    if svc.settings.mock and result.phase.value == "saving":
        svc.schedule_mock_save(runtime)
    return record_payload(runtime.record)


@router.post("/record/{task_id}/start-episode")
async def start_episode(task_id: str, action: RecordAction, request: Request):
    return await record_command(task_id, action, "start_episode", request)


@router.post("/record/{task_id}/finish-episode")
async def finish_episode(task_id: str, action: RecordAction, request: Request):
    return await record_command(task_id, action, "finish_episode", request)


@router.post("/record/{task_id}/rerecord")
async def rerecord(task_id: str, action: RecordAction, request: Request):
    return await record_command(task_id, action, "rerecord", request)


@router.post("/record/{task_id}/reset-done")
async def reset_done(task_id: str, action: RecordAction, request: Request):
    return await record_command(task_id, action, "reset_done", request)


@router.post("/record/{task_id}/quick-next")
async def quick_next(task_id: str, action: RecordAction, request: Request):
    return await record_command(task_id, action, "quick_next", request)


@router.post("/record/{task_id}/stop")
async def stop_record(task_id: str, request: Request):
    runtime = services(request).tasks.get(task_id)
    if runtime.record is not None and runtime.record.phase.value not in {"fault", "finished"}:
        runtime.record.apply("stop", f"stop-{task_id}")
    return await services(request).tasks.stop(task_id)


@router.post("/inference/inspect-policy")
async def inspect_policy(payload: PolicyInspectRequest, request: Request):
    return services(request).policy.inspect(payload)


@router.post("/inference/compatibility")
async def compatibility(payload: PolicyInspectRequest, request: Request):
    return services(request).policy.inspect(payload)


@router.post("/inference/start", status_code=status.HTTP_201_CREATED)
async def start_inference(payload: InferenceRequest, request: Request):
    require_safety(payload.safety_confirmed)
    if not payload.compatibility_token:
        raise ApiError("compatibility_required", "Inspect and validate policy compatibility before starting", status_code=409)
    svc = services(request)
    svc.policy.validate_token(payload.compatibility_token, payload.policy_path, payload.mode)
    argv = svc.commands.inference(payload)
    return await svc.tasks.start(TaskType.INFERENCE, motion_resources(payload), argv=argv, metadata={"config": payload.model_dump(mode="json")})


@router.post("/inference/{task_id}/stop")
async def stop_inference(task_id: str, request: Request):
    return await services(request).tasks.stop(task_id)


@router.post("/mock/{task_id}/frame")
async def mock_frame(task_id: str, request: Request):
    svc = services(request)
    if not svc.settings.mock:
        raise ApiError("mock_only", "Fault/frame injection is available only in Mock mode", status_code=404)
    runtime = svc.tasks.get(task_id)
    runtime.record.note_frame()
    return record_payload(runtime.record)


@router.post("/mock/{task_id}/fault")
async def mock_fault(task_id: str, request: Request, reason: Annotated[str, Body(embed=True)] = "injected fault"):
    svc = services(request)
    if not svc.settings.mock:
        raise ApiError("mock_only", "Fault injection is available only in Mock mode", status_code=404)
    runtime = svc.tasks.get(task_id)
    runtime.info.status = TaskStatus.FAULTED
    runtime.info.phase = "fault"
    if runtime.record:
        runtime.record.fault(reason)
    await svc.events.publish("fault", {"reason": reason}, task_id)
    return runtime.info


@ws_router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket, last_seq: int = 0):
    await websocket.accept()
    svc = websocket.app.state.services
    queue = await svc.events.subscribe(last_seq)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        pass
    finally:
        await svc.events.unsubscribe(queue)


@ws_router.websocket("/ws/tasks/{task_id}")
async def websocket_task(task_id: str, websocket: WebSocket, last_seq: int = 0):
    await websocket.accept()
    svc = websocket.app.state.services
    svc.tasks.get(task_id)
    queue = await svc.events.subscribe(last_seq)
    try:
        while True:
            event = await queue.get()
            if event.task_id == task_id:
                await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        pass
    finally:
        await svc.events.unsubscribe(queue)
