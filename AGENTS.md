# A1Z LeRobot 项目规则

## 项目目的

本仓库将 GALAXEA A1Z 双臂机器人接入 Hugging Face LeRobot，用于：

- 将已有 A1Z 采集数据转换为 LeRobot v3 数据集；
- 使用 LeRobot 原生训练入口训练策略；
- 通过同步或 RTC 异步推理在实机上执行策略。

仓库包含两个需要以 editable 模式安装的目录：`lerobot/` 与
`GALAXEA-A1Z/`。根项目包为 `a1z_lerobot/`，Python 要求为 3.12 或更高。

## 架构与数据约定

- `a1z_lerobot/robots/a1z_follower/` 是 A1Z 的 LeRobot `Robot` 适配层；
  配置注册名为 `a1z`。
- `hardware/a1z.py` 将 SDK 单臂封装为 7D 向量：6 个关节弧度 + 原始夹爪弧度。
- `hardware/dual_arm.py` 将左右臂组合为固定的 14D 向量：
  `[left_j1..j6, left_ee, right_j1..j6, right_ee]`。
- 电机状态和动作键均为 `<motor>.pos`。不要变更顺序、名称或夹爪单位，除非同步
  修改数据集、训练配置与推理策略。
- 当前默认视觉键为 `head_rgb`、`left_wrist_rgb`、`right_wrist_rgb`；键名必须与
  训练数据集和策略所期待的 `observation.images.*` 完全一致。
- SDK 层夹爪使用归一化值（0 闭合、1 张开）；A1Z/LeRobot 边界使用原始弧度。
  转换逻辑必须与 `hardware/a1z.py` 和 `tools/hdf5_to_lerobot.py` 一致。

## 关键入口

```bash
# 安装（仓库首次使用）
pip install -e .
pip install -e lerobot
pip install -e GALAXEA-A1Z

# 每次开机后启动两条 CAN 总线
bash a1z_lerobot/scripts/setup.sh can0
bash a1z_lerobot/scripts/setup.sh can1

# 扫描相机；优先将 /dev/v4l/by-id 路径写入相机配置
python -m a1z_lerobot.tools.probe_cameras

# 转换外部 HDF5 采集数据为 LeRobot v3 数据集
python -m a1z_lerobot.tools.hdf5_to_lerobot --src <directory> --repo-id <owner/dataset>

# 训练示例
python -m lerobot.scripts.lerobot_train \
  --dataset.repo_id=<owner/dataset> \
  --dataset.root=<dataset-root> \
  --policy.type=smolvla \
  --policy.path=<base-policy-or-checkpoint> \
  --output_dir=<output-dir> \
  --steps=30000 --save_freq=5000 --batch_size=32 --policy.device=cuda

# 推理入口（导入时注册 a1z Robot）
python -m a1z_lerobot.scripts.rollout \
  --config_path=a1z_lerobot/configs/rollout_a1z.yaml \
  --policy.path=<checkpoint> --task="<task>"
```

`a1z_lerobot/scripts/rollout_smolvla.sh` 是一个本地示例；其 checkpoint 路径不应
假定存在。运行前必须确认策略路径、任务和训练数据特征匹配。

## 相机、录制与模型兼容性

- 当前 `rollout_a1z.yaml` 配置三路 OpenCV RGB 相机。不要使用不稳定的
  `/dev/videoN` 作为长期配置；使用探测工具输出的 `by-id` 路径。
- LeRobot 的 RealSense 组件可打开深度流，但 A1Z `Robot.get_observation()` 当前只
  调用 `async_read()` 并输出彩色图；它不会将 `read_depth()` 的深度图写入观测、数据集
  或策略输入。
- 单相机或 RGB-D 模态只能与用相同特征键、形状和模态录制并训练的策略配套使用。
  现有三 RGB 视角的 checkpoint 不能直接用于单深度相机输入。
- 标准 `lerobot-record` 要求一个 `Teleoperator`。单臂现场示教使用
  `a1z_leader`；旧双臂没有对应的本仓库原生 Teleoperator，仍需外部采集后通过 HDF5
  转换器导入。
- `a1z` 是固定双臂 14D 适配；一只物理机械臂必须使用独立的 `a1z_single` 7D 适配，
  不得复用双臂配置。

## 实机安全

- 在连接实机、发送动作、启动 CAN、回零、夹爪操作或运行 rollout 前，先确认工作空间
  无障碍、人手远离机械臂、急停可用、CAN 接口和相机映射正确。
- `A1Z.send_action()` 已做 EMA 平滑和关节步进限幅；不要无依据提高 `ema_alpha`、
  `max_joint_delta` 或控制频率。
- 旧双臂 `A1Z.disconnect()` 会打开夹爪并尝试回零；单臂 `a1z_single` 默认只停止并
  失能，只有显式启用 `return_home_on_disconnect` 才回零。任何一种实机退出路径都应
  先核实环境安全。
- 使用 `A1Z_DEBUG=1` 时会在 `tmp/policy_view/` 写入策略实际看到的首帧，可用于验证
  相机视角和色彩通道。

## 修改原则与验证

- 保持分层边界：SDK 改动在 `GALAXEA-A1Z/`；A1Z 硬件适配在
  `a1z_lerobot/robots/a1z_follower/hardware/`；LeRobot 对接在 `a1z_follower.py`；
  rollout 入口只负责注册和转发。
- 先做不连接硬件的导入、配置解析、向量顺序和数据集特征检查；硬件验证必须由操作者
  在安全环境中执行。
- 改变任一观测/动作特征前，检查训练数据集元数据、策略配置、相机键、单位、帧率与
  rollout 配置是否一致。
- 根级 `tests/` 包含单臂硬件无关测试。新增或修改纯 Python 逻辑时继续添加测试；
  不要把实机动作当作唯一验证手段。
- 保留用户已有的未跟踪 `CLAUDE.md`；它是现有项目说明，不要在未经请求时替换、删除或
  重写它。

## 单臂 A1Z 扩展

- `a1z_lerobot/robots/a1z_single/` 注册 `a1z_single`：单个 CAN、六关节弧度加归一化
  夹爪，共 7D。
- `a1z_lerobot/teleoperators/a1z_leader/` 注册 `a1z_leader`：STS3215 ID 1–6 对应
  `arm_0..arm_5`，ID 7 对应 `gripper`。
- 单臂键顺序固定为 `arm_0.pos..arm_5.pos, gripper.pos`；夹爪在单臂 LeRobot 边界
  使用 `0=闭合、1=张开`，与旧双臂原始夹爪弧度契约不同。
- 默认单臂视觉为 `top_rgb`（D435）与 `wrist_rgb`（D405），RGB 640×480@30，
  `use_depth=false`；相机数量仍由配置字典决定。
- 单臂录制必须保存 `send_action()` 返回的实际限幅后动作。修改 LeRobot 录制循环时
  保留 `lerobot/tests/scripts/test_lerobot_record_sent_action.py` 回归测试。
- 单臂退出默认停止并失能，不自动回零。rollout 配置同时设置
  `return_to_initial_position=false`；任何显式回零仍视为实机运动。
- 当前 LeRobot 子模块要求 Python 3.12 或更高。硬件无关测试使用仓库内
  `lerobot/src` 与 `GALAXEA-A1Z`，不要误测系统中的旧版 LeRobot。
