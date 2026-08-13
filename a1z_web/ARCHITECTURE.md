# A1Z Web V1 Architecture

The Web application is a control plane, not a motor controller. Browser requests are validated by FastAPI, checked against the hardware ownership table, and converted to fixed argv arrays. Long-running workers execute inside the configured `lerobot-a1z` Conda environment and call the existing A1Z/LeRobot Python APIs.

```text
React browser ── HTTP ──> FastAPI ── TaskManager ── exec argv ──> workflow worker
      ^                       │                                 │
      └──── WebSocket events ─┴──── disk JSONL logs <── A1Z_EVENT/stdout
                                                              │
                                      LeRobot loop → A1Z adapter → GALAXEA SDK
```

The backend owns configuration, state, logs, health, and process lifecycle. It never runs the 30 Hz LeRobot loop or 250 Hz SDK loop. Each worker exclusively owns its selected serial, SocketCAN, and RealSense resources until disconnect completes.

Recording has three deliberately separate states: process status, domain protocol phase, and frontend phase. Policy inspection and feature compatibility are completed before an inference worker is allowed to connect hardware. Mock mode follows the same HTTP and state contracts while prohibiting all hardware access.

The platform exposes only safe stop. A1Z currently has no verified Web-controllable pause/hold or generic reset-pose primitive, so neither is represented in the API or UI. Follower zeroing and gripper Flash maintenance remain terminal-only advanced maintenance operations.
