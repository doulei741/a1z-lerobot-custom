# A1Z LeRobot Web

A1Z LeRobot Web 是现有 A1Z/LeRobot 实机工作流的本地低代码控制面。它不重写电机控制器，不让浏览器参与 30 Hz/250 Hz 循环，也不改变已经实机验证的 A1Z `send_action()` 安全链。第一版只提供四个工作流：Leader 校准与配对、遥控、数据录制、ACT 推理。

## Architecture

```text
React + TypeScript
  ├─ HTTP: 参数、启动、领域命令、停止、查询、补日志
  └─ WebSocket: 有序日志、阶段、health、fault
                 │
FastAPI ─ TaskManager ─ HardwareResourceManager
                 │ create_subprocess_exec(argv), process group
                 v
conda run -n lerobot-a1z --no-capture-output python workflow_worker.py
                 │
现有 LeRobot loop → A1Z adapter.send_action() → GALAXEA-A1Z SDK → SocketCAN
```

FastAPI 只做控制面。每个真实任务在独立进程组中运行；worker 调用现有入口或现有类。参数全部经过 Pydantic v2 校验并转换为 argv 数组，从不拼接用户 shell 字符串。任务元数据落 SQLite，日志落 JSONL，内存仅保留最近 3000 行。事件带单调 sequence，WebSocket 断线后用 `/api/tasks/{id}/logs?after=` 补齐。

`HardwareResourceManager` 对 `can0/can1`、左右 A1Z、左右 Leader 和三相机执行后端强制互斥。页面 disabled 不是唯一防线。浏览器刷新或切换路由不会终止子进程；当前 task id 存在全局 Zustand store，顶部一直显示任务并保留软件停止。

## Safety model

- 默认 `REAL HARDWARE MOTION DISABLED`。只有 `A1Z_WEB_MOCK=0` 且 `A1Z_WEB_ALLOW_HARDWARE=1` 才能启动真实硬件任务。
- 进入遥控、录制、推理和配对前必须完成现场安全确认。
- 软件停止不是工业物理急停；现场必须保持真实急停/断能装置可用。
- 停止顺序为 graceful `SIGINT` → 超时 `SIGTERM` → 最终 `SIGKILL`，优先让现有 `finally/disconnect()` 正常执行。
- A1Z 没有经过验证的 Pause/Hold，因此平台没有 Pause；也没有虚构 Reset Pose、碰撞检测、力矩检测。
- Follower `set_zero.py` 与 `gripper_set_zero.py` 会写 Flash，第一版 UI 不提供入口。
- CAN `Network is down`、SDK `Emergency stop`、RealSense critical timeout 或 worker fault 会变为任务 fault，Recording 停止接收帧、当前未保存 Episode 作废、禁止 Quick Next，并触发进程安全退出。
- 所有运动目标继续经过原有 A1Z Robot `send_action()` 的 key、finite、EMA、`max_joint_delta`、绝对限位和 `previous_action` 检查。Dataset label 使用它返回的 actual sent action。

## Installation

要求：已可用的 `lerobot-a1z` Conda 环境、Python 3.12+（Web backend 可独立）、Node.js 与 pnpm。

```bash
cd a1z_web/backend
python -m venv .venv
.venv/bin/pip install -e '.[dev]'

cd ../frontend
pnpm install
pnpm exec playwright install chromium

cd ..
cp .env.example .env
```

`.env` 不应硬编码某个用户目录。`A1Z_PROJECT_ROOT` 可显式配置；未配置时后端从同时包含 `a1z_lerobot/` 与 `GALAXEA-A1Z/` 的父目录自动探测。

## Development

安全的默认 Mock 启动：

```bash
cd a1z_web
export A1Z_WEB_MOCK=1
export A1Z_WEB_ALLOW_HARDWARE=0
./scripts/dev.sh
```

也可分别运行 `./scripts/dev-backend.sh` 与 `./scripts/dev-frontend.sh`。前端为 `http://127.0.0.1:5173`，Vite 将 `/api` 和 `/ws` 代理到后端。

生产构建：

```bash
cd a1z_web/frontend
pnpm build
```

硬件服务必须保持单实例，不能用多个 Uvicorn worker 争抢设备。`deploy/` 中提供 systemd 与 nginx 示例，但容器不是必需条件。

## Mock mode

`A1Z_WEB_MOCK=1` 时不会连接 SocketCAN、Leader 或 RealSense，也不会启动 A1Z 电机。它仍使用同一组 API、硬件锁和领域状态机，模拟校准阶段、Pairing 数据、遥控 ready、录制 Episode、ACT compatibility、日志、health 和 fault injection。UI 始终显示 `MOCK`，不会与真实状态混淆。

## Real hardware mode

完成 [人工 Smoke Test](docs/HARDWARE_SMOKE_TEST.md) 后，现场操作者才应设置：

```bash
cd a1z_web
unset LD_LIBRARY_PATH
./scripts/dev.sh
```

实机参数写入 `a1z_web/.env`（项目根目录可自动探测）：

```dotenv
A1Z_CONDA_ENV=lerobot-a1z
A1Z_WEB_MOCK=0
A1Z_WEB_ALLOW_HARDWARE=1
```

Web 启动后，点击顶部“设备准备中心”：

1. 重新识别 USB-CAN、Leader 与 RealSense；
2. 分别点击“初始化 can0 / can1”；
3. 按系统 Polkit 窗口完成管理员授权；
4. 后端固定配置 `gs_usb`、1 Mbps、`txqueuelen 1000`，并重新读取接口验证；
5. 两个 CAN Ready 后进入“机械臂校准”完成左右 Leader 校准和 Pairing。

浏览器不能提交 shell 文本，CAN 名只允许 `can0/can1`，Web 不接收或保存 sudo 密码。已有机器人任务占用硬件时，后端会拒绝重配 CAN。命令行 `setup.sh` 仅作为故障维护后备，不再是正常产品流程。Web 不替代物理安全检查，也不会自动运行硬件 smoke test。

### 在 Web 中切换 Mock / 真机

顶部状态栏提供当前模式按钮：`Mock 仿真` 或 `真机实操`。点击 `Mock 仿真` 后，完成工作区与物理急停确认，即可把当前后端会话切换为真机模式；不需要退出 Web，也不受启动终端中旧的 `A1Z_WEB_MOCK` 环境变量限制。切换模式本身不会连接或移动机械臂，后续仍需在具体页面通过设备 Preflight 和运动安全确认。

切换回 Mock 不需要运动确认。存在活动任务或硬件资源被占用时，前端禁用切换，后端也会返回 409。运行时切换仅对当前后端进程有效；后端重启后仍以 `.env`/启动环境为初始模式，这是为了避免一次真机授权在未来重启时被静默继承。

`A1Z_WEB_MOCK=1` 与 `A1Z_WEB_ALLOW_HARDWARE=0` 是开发界面的安全组合，只会模拟任务成功；即使 USB 设备已经插入，也绝不会驱动实机。Real 模式下，每个正式页面在启动动作前都会调用后端权威 Preflight：

- Calibration：检查所选 Leader 串口；
- Pairing：检查 Leader 串口、对应校准文件及所选 CAN；
- Teleoperation：检查 Single/Dual 所需的 Leader、校准文件、CAN 和页面启用的相机；
- Recording：额外检查录制 YAML、其中声明的相机及右腕序列号覆盖；
- Inference：检查 CAN 和模型运行配置所需的相机，模型兼容性仍通过单独的 Model First 检查完成。

阻断项会以弹窗列出准确资源、原因和图形化恢复步骤，CAN/Leader/相机问题统一引导至“设备准备中心”，后端启动端点还会再次执行同一检查，避免绕过前端或检查后设备发生变化。接口枚举只能证明设备节点存在：Leader 的 7 个电机握手、RealSense 实际取帧和 A1Z 电机状态仍由任务子进程验证；运行期故障会切换任务为 `faulted/failed` 并在全局弹窗提示查看日志。

## Four workflows

### Calibration

左右 Leader 使用不同 ID。worker 直接使用 `A1ZLeader`、`set_half_turn_homings()`、原始位置范围读取、`MotorCalibration`、`write_calibration()` 和 `_save_calibration()`。流程为中位确认 → half-turn homing → J1–J6/Gripper 全行程 → review → 保存。Pairing 是独立 Profile：在两臂相同安全姿态读取 Leader 6D 与 Follower 6D，按 `offset = follower - leader × scale × sign` 计算并保存，不污染 Leader MotorCalibration JSON。

### Teleoperation

支持 Single/Dual、CAN、Leader port/id、6 轴 sign/scale/offset、FPS、EMA、`max_joint_delta`、夹爪启动保持、退出 Home/张开、Rerun `display_data`，以及无相机/启用 RGB 相机、序列号、宽高与相机 FPS。默认映射来自当前现场验证配置；Single 与 Dual 映射不同。真实 worker 代理 `a1z-teleoperate-single/dual`，ready 依赖 A1Z CLI 的真实连接日志，不以“进程存在”冒充 ready。

### Recording

worker 复用 `RecordConfig`、`make_robot_from_config()`、`make_teleoperator_from_config()`、`record_loop()`、`LeRobotDataset.create/resume()`、`sanity_check_dataset_robot_compatibility()` 和 `VideoEncodingManager`。不再模拟方向键，而使用 stdin JSON 领域协议。

页面可调整录制 YAML、Dataset repo/root/task、Resume 与新增 Episode、Episode/Reset 时间、外层与 Dataset FPS、视频开关、三相机序列号/480p 尺寸、CAN、Leader port/id、Pairing profile、EMA、`max_joint_delta`、夹爪启动保持、退出行为、Rerun 和压缩图显示。所有值通过 Pydantic 验证并传入现有 `RecordConfig`，相机始终为 RGB、`use_depth=false`。

三层状态独立：

- Process：`starting/ready/running/stopping/completed/failed/faulted/stopped`
- Record protocol：`ready/recording/saving/resetting/finished/fault`
- Frontend：由服务端阶段派生 `waiting_ready/recording/saving/resetting/waiting_next/completed/fault`

正常流程：`ready → start_episode → recording → finish/quick_next → saving → saving_complete → resetting → reset_done → ready`。Quick Next 只是在合法阶段 arm 自动继续，绝不跳过保存和 Reset。每个命令含 `client_action_id` 并幂等；非法阶段返回 409。首帧未写入时 Finish/Quick Next 被拒绝，防止空 Episode。Resume 页面显示 Existing、Add 和 Total，启动前验证 state/action 维度、feature/camera keys、480p 与 FPS。

### Inference

推理页面没有 Leader 参数。可调整任务指令、Single/Dual CAN、策略同步方式、FPS/时长、EMA、`max_joint_delta`、相机序列号/宽高、Rerun 与退出行为。`inspect-policy` 仅读取 checkpoint 的 config/preprocessor，不连接硬件，比较 Single 7D 或 Dual 14D、相机 keys、图像 shape 和 processors，并产生短期 compatibility token。只有 token 与当前 path/mode 匹配才可启动。真实 rollout 仍保持当前 Model First, Hardware Last：模型、pre/postprocessor、CUDA/eval 和 `validate_policy_features()` 成功后才连接 CAN/相机。ACT 的 `gripper_start_hold` 被后端锁定为 false。默认 Safe Test 为 sync、30 FPS、10 秒、`max_joint_delta=0.01`。

## API and WebSocket

主要 API：

- `GET /api/system/health`, `/api/devices`, `/api/tasks`, `/api/schema/{workflow}`
- `POST /api/system/mode`（Mock/真机运行时切换，真机要求显式安全确认）
- `POST /api/devices/can/initialize`（只允许 can0/can1，固定 1 Mbps，Polkit 授权）
- `GET /api/tasks/{id}`, `/api/tasks/{id}/logs?after=N`; `POST /api/tasks/{id}/stop`
- `POST /api/calibration/start`, `/api/calibration/{id}/{middle|record-range|stop-range|save|cancel}`
- `POST /api/pairing/{read|calculate|save|verify}`
- `POST /api/teleop/start`
- `POST /api/record/compatibility`, `/api/record/start`, `/api/record/{id}/{start-episode|finish-episode|rerecord|reset-done|quick-next|stop}`
- `POST /api/inference/inspect-policy`, `/api/inference/compatibility`, `/api/inference/start`
- `/ws/events?last_seq=N`, `/ws/tasks/{id}?last_seq=N`

错误统一为 `{error: {code, message, details, recoverable}}`。参数 Schema 由后端 Pydantic 模型生成，并附单位、说明、危险级别、readonly/restart metadata。

## Testing

```bash
cd a1z_web/backend
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q -p pytest_asyncio.plugin
.venv/bin/ruff check app tests
.venv/bin/python -m compileall -q app

cd ../frontend
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm exec playwright test
```

自动测试覆盖参数校验、资源互斥、重复 stop、子进程崩溃/进程组停止、SQLite 恢复、日志 sequence、四页路由、全局停止、Policy gate、Record 非法阶段、幂等、防空帧、Quick Next、fault 传播和 Resume compatibility。所有 API/E2E 测试均为 Mock，不允许真实机械臂运动。

## Logs and health

全局 Drawer 支持 level 过滤、暂停滚动、复制、清空本地显示和下载。清空只影响浏览器，不删除后端日志。后端只读检查 sysfs SocketCAN、`/dev/ttyACM*` 和 RealSense 枚举；运行期间不会再开 CAN socket 或相机。任务 health 优先使用 child structured events。没有可靠 SDK 数据时 UI 显示 N/A，不伪造 245 Hz 或关节值。

## Known limitations

- 未实现 Pause/Hold、Reset Pose、碰撞/力矩检测，因为当前 A1Z 源码没有可验证的对应能力。
- Rerun 作为独立观察面；没有安全 Frame Relay，因此不 iframe 伪造相机画面。
- Pairing read 需要短暂启动 A1Z SDK 才能读取 Follower，故被视为可能运动的硬件 session，并要求确认。
- 全局设备发现能看到接口/枚举状态；电机级健康以运行 worker 的结构化事件为准。
- 自动化只证明 Mock、API、状态机、进程和 UI 契约；真实 CAN、Leader、三相机、录制文件和 ACT 动作仍须依照 smoke checklist 现场验证。

## Troubleshooting

- `hardware_motion_disabled`：确认不是 CI/Mock，并显式设置 `A1Z_WEB_ALLOW_HARDWARE=1`。
- `hardware_resource_busy`：已有任务拥有 CAN/Leader/Camera；从顶部查看 task id 并安全停止。
- `resume_schema_incompatible`：查看 details 中的 state/action/FPS/camera/resolution 差异，不要强行追加。
- `compatibility_token_invalid`：checkpoint path 或 mode 在检查后发生变化，重新 Inspect Policy。
- `Network is down`：停止任务，检查 USB-CAN 是否重枚举，重新建立 can0/can1；不要直接继续 Episode。
- `Timed out waiting for frame`：检查对应 RealSense USB 拓扑/带宽，任务进入 fault 后人工复核。
- OpenSSL/Conda 环境污染：Web backend 可使用独立 venv；机器人子进程固定通过 `conda run -n lerobot-a1z` 启动。
