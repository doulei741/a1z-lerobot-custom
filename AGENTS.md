# A1Z LeRobot 项目规则

## 项目目的

本仓库将 GALAXEA A1Z 双臂机器人接入 Hugging Face LeRobot，用于：

- 使用七舵机 Leader 遥控单臂或双臂 A1Z；
- 以 LeRobot v3 格式直接录制单臂或双臂 RGB 数据；
- 将已有 A1Z 采集数据转换为 LeRobot v3 数据集；
- 使用 LeRobot 原生训练入口训练 ACT 等策略；
- 在单臂或双臂 A1Z 上执行训练好的策略。

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
- 当前双臂默认视觉键为 `top_rgb`、`left_wrist_rgb`、`right_wrist_rgb`；键名必须与
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

# 双臂纯遥控、录制和 ACT 推理入口
a1z-teleoperate-dual --help
a1z-record-dual --help
a1z-rollout-act-dual --help

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

完整、可复制执行的当前硬件命令以 `docs/a1z-dual-arm-commands.md` 为准。复杂诊断不要
写成 heredoc 或多行内联 Python；在 `a1z_lerobot/tools/` 中创建带 `--help`、参数校验
和可靠清理的脚本。

## 相机、录制与模型兼容性

- 当前双臂录制配置使用三路 RealSense RGB：顶部 D435、左右手腕 D405，均为
  640×480@30、`use_depth=false`。必须使用相机序列号，不使用不稳定的 `/dev/videoN`。
- LeRobot 的 RealSense 组件可打开深度流，但 A1Z `Robot.get_observation()` 当前只
  调用 `async_read()` 并输出彩色图；它不会将 `read_depth()` 的深度图写入观测、数据集
  或策略输入。
- 单相机或 RGB-D 模态只能与用相同特征键、形状和模态录制并训练的策略配套使用。
  现有三 RGB 视角的 checkpoint 不能直接用于单深度相机输入。
- 标准 `lerobot-record` 要求一个 `Teleoperator`。单臂使用 `a1z_leader`，双臂使用
  `bi_a1z_leader`；双臂已经支持原生遥控、录制和 ACT 推理，不要再按旧流程要求先采集
  外部 HDF5。
- `a1z` 是固定双臂 14D 适配；一只物理机械臂必须使用独立的 `a1z_single` 7D 适配，
  不得复用双臂配置。

## 实机安全

- 在连接实机、发送动作、启动 CAN、回零、夹爪操作或运行 rollout 前，先确认工作空间
  无障碍、人手远离机械臂、急停可用、CAN 接口和相机映射正确。
- `A1Z.send_action()` 已做 EMA 平滑、关节步进限幅和六轴绝对限位；不要无依据提高
  `ema_alpha`、`max_joint_delta` 或控制频率。
- 单臂和双臂默认退出均只停止并失能。双臂只有显式设置
  `open_grippers_on_disconnect=true` 才打开夹爪，只有显式设置
  `return_home_on_disconnect=true` 才回零；任何退出运动都必须先核实环境安全。
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
- 根级 `tests/` 包含单臂和双臂硬件无关测试。新增或修改纯 Python 逻辑时继续添加测试；
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

## 双臂 Leader、零位与动作约束

- 两条 Leader 都可以使用舵机 ID 1–7；它们位于不同串口，因此 ID 不冲突。每条
  Leader 必须使用不同串口和不同校准 ID，ID 1–6 对应六轴，ID 7 对应夹爪。
- Leader 行程标定只建立自身角度坐标，不会自动获得 A1Z Follower 的编码器零位。
  新 Leader/Follower 组合必须在相同安全姿态下独立配对：
  `offset = follower_angle - leader_angle * scale * sign`。
- `joint_signs`、`joint_scales`、`joint_offsets_rad` 在纯遥控和正式数据录制时都会生效。
  改 sign 后必须重新计算该轴 offset；禁止只改 sign 后直接上电测试。
- 当前已通过实机验收的左右 signs 均为 `[-1,-1,1,1,1,-1]`。当前配对 offsets 为：

```text
left:  [0.185504249, 1.676119148, -1.985360469, 0.471459368, 0.061374215, 0.089759790]
right: [-0.097389546, 1.672050437, -1.971852804, 0.520146476, -0.038316864, -0.021480975]
```

  这些数值只属于当前实体组合；更换 Leader、Follower、重新标定或拆装关节后必须重新
  配对，不得复制旧 offset。
- A1Z 六轴限制依次为：J1 `[-2.094,2.094]`、J2 `[0,3.142]`、J3
  `[-3.142,0]`、J4/J5 `[-1.484,1.484]`、J6 `[-2.007,2.007]` rad。
- 双臂动作必须按 `EMA -> 每步增量限制 -> 六轴绝对限位 -> 更新 _prev_action -> SDK`
  的顺序处理。绝对限位必须发生在 `_prev_action` 更新前，否则非法目标会在历史状态中
  积累，产生关节不动、反向后长时间延迟等假象。夹爪不使用六轴限位表。
- 保持单臂和双臂动作处理的安全语义一致，但不要通过修改单臂默认 signs/offsets 来修复
  双臂实体配对。

## J2/J3 故障复盘与诊断顺序

- 已遇到的症状是：Follower J2 不动，而移动 Leader 后 J3 变化更大。最终不是舵机
  ID 2/3 对调，而是 J2 sign 错误、J2 目标落在 A1Z 下限之外、双臂 `_prev_action`
  在 SDK 限位前积累非法值，以及操作过程中两个 Leader 编码器实际同时变化的组合结果。
- 先运行 `python -m a1z_lerobot.tools.diagnose_leader_joints --help`，再用该脚本单独连接
  Leader。脚本不连接 CAN、Follower、相机或录制器。默认零基索引 `1 2` 对应物理
  J2/J3；多值参数的标准写法是 `--joint-indices 1 2`。
- 如果只动 J2 时只有 `delta_J2` 变化，软件 ID 映射正确；如果 J2/J3 同时变化，说明
  两个 Leader 编码器确实都发生了变化，应固定相邻连杆、避免重力下沉后重测，不能仅凭
  Follower 视觉现象判定软件串轴。
- 诊断显示值只有在传入相同 signs/offsets 时才等于正式遥控目标。分析限位前必须把
  Leader 原始标定角度转换为实际双臂配置，不能直接拿诊断默认 offset 的数值与 A1Z
  限位比较。
- 方向判断必须结合 A1Z 的非对称范围：J2 只能为正，J3 只能为负。若匹配姿态位于限位
  边界，先确认 Leader 的可运动方向，再决定 sign，并同步重算 offset。

## 实机验收顺序

1. 确认两个 Leader 串口、两个 CAN 接口、左右对应关系和急停；首次测试不连接相机。
2. 使用 `max_joint_delta=0.01`、`ema_alpha=0.3`，先运行两秒且不移动 Leader，确认
   Follower 无启动跳变。
3. 再进行五秒逐轴小幅测试；一次只动一个关节并固定相邻连杆。验证方向、比例、零位和
   夹爪后，才允许无时限纯遥控。
4. 退出时只按一次 `Ctrl+C`，等待两条 A1Z 完成失能；连续中断可能跳过 CAN 清理并出现
   `SocketcanBus was not properly shut down`。
5. 无相机遥控通过后，才连接三路 RGB 并检查 Rerun；之后先录制一个短 episode，检查
   14D state/action、图像键和实际 `send_action()` 返回值，最后才正式采集或推理。

## 环境与版本管理经验

- 使用独立 Conda 环境 `lerobot-a1z`（Python 3.12），保留原有 `lerobot` 环境不动。
  从当前 worktree 运行时确保 `a1z_lerobot`、仓库内 `lerobot/src` 和
  `GALAXEA-A1Z` 来自同一工作版本。
- CAN 接口重启或重新插拔后可能消失；先从仓库/worktree 根目录运行
  `bash a1z_lerobot/scripts/setup.sh can0` 和 `can1`，再启动遥控或录制。
- 当前维护分支是 `feature/dual-arm-workflow`，目标仓库是用户自己的
  `doulei741/a1z-lerobot-custom`，不要向上游仓库推送二次开发。
- 若 SSH 因本机 OpenSSL 版本冲突失败，使用 GitHub CLI 凭据通过 HTTPS 推送：

```bash
git -c credential.helper='!gh auth git-credential' push \
  https://github.com/doulei741/a1z-lerobot-custom.git feature/dual-arm-workflow
```

- 提交和推送前运行硬件无关完整回归，并通过 `git diff --check`。不要清理或覆盖用户在
  `GALAXEA-A1Z` 子模块中的未提交状态。
