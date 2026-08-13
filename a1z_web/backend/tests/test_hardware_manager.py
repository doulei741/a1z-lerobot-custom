import pytest

from app.core.errors import ApiError
from app.services.hardware_manager import HardwareResourceManager


@pytest.mark.asyncio
async def test_resource_acquisition_is_atomic_and_reports_owner():
    manager = HardwareResourceManager()
    await manager.acquire("record-1", {"can0", "can1", "top_camera"})

    with pytest.raises(ApiError) as exc:
        await manager.acquire("infer-2", {"can1", "right_wrist_camera"})

    assert exc.value.code == "hardware_resource_busy"
    assert exc.value.details["resource"] == "can1"
    assert exc.value.details["owner_task_id"] == "record-1"
    assert await manager.owner_of("right_wrist_camera") is None

    await manager.release("record-1")
    await manager.acquire("infer-2", {"can1"})
    assert await manager.owner_of("can1") == "infer-2"
