from __future__ import annotations

import asyncio

from app.core.errors import ApiError


class HardwareResourceManager:
    """Atomically arbitrates exclusive robot peripherals between tasks."""

    def __init__(self) -> None:
        self._owners: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, task_id: str, resources: set[str]) -> None:
        async with self._lock:
            for resource in sorted(resources):
                owner = self._owners.get(resource)
                if owner is not None and owner != task_id:
                    raise ApiError(
                        "hardware_resource_busy",
                        f"Hardware resource {resource} is owned by task {owner}",
                        status_code=409,
                        details={"resource": resource, "owner_task_id": owner},
                    )
            self._owners.update({resource: task_id for resource in resources})

    async def release(self, task_id: str) -> None:
        async with self._lock:
            owned = [resource for resource, owner in self._owners.items() if owner == task_id]
            for resource in owned:
                self._owners.pop(resource, None)

    async def owner_of(self, resource: str) -> str | None:
        async with self._lock:
            return self._owners.get(resource)

    async def snapshot(self) -> dict[str, str]:
        async with self._lock:
            return dict(self._owners)
