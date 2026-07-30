# a1z_lerobot

把 GALAXEA A1Z 双臂机器人接入 [LeRobot](https://github.com/huggingface/lerobot) 框架，做策略的**训练**与**实机推理**。

## 能力范围

- 提供 A1Z 双臂的 lerobot `Robot` 适配（注册名 `a1z`），让原生 `lerobot rollout` 直接驱动实机。
- **训练**：复用 lerobot 原生 `lerobot_train`。
- **推理**：支持同步推理与 RTC 异步推理。

## 硬件要求

- GALAXEA A1Z 机械臂 ×2（左 `can0` + 右 `can1`，每臂 6 关节 + 1 夹爪）
- USB-CAN 适配器 ×2（HHS `a8fa:8598`，走 SocketCAN / gs_usb）
- 相机 ×3（头部 / 左腕 / 右腕，USB UVC）

## 安装

仓库内含 `lerobot` 与 `GALAXEA-A1Z` 两个子模块，连同本项目各以可编辑模式安装：

```bash
git clone --recursive https://github.com/userguide-galaxea/a1z-lerobot.git
pip install -e .
pip install -e lerobot
pip install -e GALAXEA-A1Z
```

## 项目结构

```
a1z_lerobot/
├── configs/
│   └── rollout_a1z.yaml          # 推理共享配置（CAN + 3 相机）；改相机只动这里
├── robots/a1z_follower/          # A1Z 的 lerobot Robot 适配（注册 --robot.type=a1z）
│   ├── a1z_follower.py           #   A1Z(Robot)：14 个 .pos 关节键 + 3 相机，send_action 内 EMA + 限幅
│   ├── config_a1z_follower.py    #   A1ZConfig（CAN 口 / 相机 / ema_alpha / max_joint_delta）
│   └── hardware/                 #   底层封装：单臂 a1z.py · 双臂 dual_arm.py · 常量 config.py
├── scripts/
│   ├── setup.sh                  # SocketCAN 启动（每次开机跑一次）
│   ├── rollout.py                # 推理入口（触发 a1z 注册 + 调 lerobot rollout）
│   ├── rollout_smolvla.sh        # smolvla 推理（含 RTC）
│   └── rollout_pi05.sh           # pi05 推理
└── tools/
    └── probe_cameras.py          # 扫描 /dev/video* 抓图 + 打印 by-id 稳定路径
```

## 使用流程

### 1. 启动 CAN 总线

```bash
bash a1z_lerobot/scripts/setup.sh can0
bash a1z_lerobot/scripts/setup.sh can1
```

### 2. 配置相机

插上相机后探测设备、抓图确认视角：

```bash
python -m a1z_lerobot.tools.probe_cameras
```

### 3. 训练

数据集（在采集项目里转好的 LeRobot 格式）放到本地，用 lerobot 原生训练：

```bash
python -m lerobot.scripts.lerobot_train \
    --dataset.repo_id=repo_id \
    --dataset.root=/path/to/dataset \
    --policy.type=smolvla \
    --policy.path=/path/to/smolvla_base \
    --output_dir=./outputs \
    --steps=30000 --save_freq=5000 --batch_size=32 --policy.device=cuda
```

### 4. 推理

改好 `.sh` 里的 `--policy.path`（指向上一步 checkpoint）和 `--task`，然后：

```bash
bash a1z_lerobot/scripts/rollout_<your policy>.sh
```

- 默认**同步推理**；加 `--inference.type=rtc` 走 **RTC 异步推理**。

## 单臂 A1Z：七轴示教、双 RealSense、ACT

单臂类型注册为 `a1z_single`，遥操作器注册为 `a1z_leader`。示教臂使用 7 个
STS3215：ID 1–6 对应 A1Z J1–J6，ID 7 对应夹爪。状态与动作顺序固定为：

```text
arm_0, arm_1, arm_2, arm_3, arm_4, arm_5, gripper
```

前六轴单位为弧度；夹爪使用归一化值 `0=闭合、1=张开`。单臂数据和双臂 14D
数据互不兼容，不要混用数据集或 checkpoint。

当前 LeRobot 子模块要求 Python 3.12 或更高。建议在独立环境安装：

```bash
pip install -e 'lerobot[hardware,feetech,intelrealsense,training]'
pip install -e GALAXEA-A1Z
pip install -e .
```

### 1. 查找硬件

```bash
lerobot-find-port
lerobot-find-cameras realsense
```

当前配置已绑定 D435 序列号 `025222071608`、D405 序列号 `260522273365` 和七轴
示教臂串口 `/dev/ttyACM0`。若更换设备，再通过命令行覆盖为实际序列号和串口。

每次开机只启动单条 A1Z CAN：

```bash
bash a1z_lerobot/scripts/setup.sh can0
```

### 2. 七轴示教器校准和低速遥控

先单独校准 Leader；此命令只访问 `/dev/ttyACM0` 上的 STS3215，不连接 A1Z、CAN 或相机：

```bash
a1z-calibrate-leader --port=/dev/ttyACM0 --id=a1z_leader
```

首次校准时，按提示手动摆动 `arm_0..arm_5` 与夹爪至安全机械行程。随后在空工作区、
急停可用条件下运行 10 秒低速验证：

```bash
python -m a1z_lerobot.scripts.teleoperate_single \
  --robot.type=a1z_single \
  --robot.id=a1z_single \
  --robot.can_channel=can0 \
  --robot.cameras='{}' \
  --robot.ema_alpha=0.3 \
  --robot.max_joint_delta=0.02 \
  --robot.relative_action_reference=true \
  --teleop.type=a1z_leader \
  --teleop.id=a1z_leader \
  --teleop.port=/dev/ttyACM0 \
  --fps=30 \
  --teleop_time_s=10
```

如果某轴方向或零位不一致，通过参数调整，不要修改转换代码：

```text
--teleop.joint_signs='[1,-1,1,1,1,1]'
--teleop.joint_scales='[1,1,1,1,1,1]'
--teleop.joint_offsets_rad='[0,0,0,0,0,0]'
```

### 3. 录制 LeRobot v3 数据

默认录制配置是 [record_a1z_single_realsense.yaml](a1z_lerobot/configs/record_a1z_single_realsense.yaml)：

- D435：`top_rgb`
- D405：`wrist_rgb`
- 两路均为 RGB 640×480@30，`use_depth=false`
- 单臂状态 7D、实际下发动作 7D
- 默认仅保存到本地，不上传 Hub

使用实际串口、相机序列号、数据路径和任务覆盖默认值：

```bash
python -m a1z_lerobot.scripts.record_single \
  --config_path=a1z_lerobot/configs/record_a1z_single_realsense.yaml \
  --teleop.port=/dev/ttyACM0 \
  --robot.cameras.top_rgb.serial_number_or_name=D435_SERIAL \
  --robot.cameras.wrist_rgb.serial_number_or_name=D405_SERIAL \
  --dataset.repo_id=local/a1z_pick \
  --dataset.root=datasets/a1z_pick \
  --dataset.single_task='Pick up the object and place it in the tray' \
  --dataset.num_episodes=50
```

相机数量完全由 `--robot.cameras` 字典决定。删除某个配置键即可录制单相机；增加新的
CameraConfig 键即可录制更多相机。训练和推理必须使用完全相同的视觉键。

录制循环保存 `Robot.send_action()` 返回的实际动作，因此 EMA、逐帧限幅和物理限位后
的 A1Z 指令就是训练标签。

单臂遥操作和录制使用相对参考：连接时保持 A1Z 的当前姿态，随后仅跟随 Leader 的关节
变化量。ACT 推理不启用该选项，仍将模型输出作为绝对 A1Z 动作。

### 4. RTX 4060 上训练 ACT

本机检测到 NVIDIA GeForce RTX 4060 Laptop GPU，显存约 7.62 GiB。单臂训练入口默认
补充 `policy.type=act`、`policy.device=cuda` 和 `batch_size=8`：

```bash
python -m a1z_lerobot.scripts.train_act_single \
  --dataset.repo_id=local/a1z_pick \
  --dataset.root=datasets/a1z_pick \
  --output_dir=outputs/act_a1z_single \
  --steps=100000 \
  --save_freq=10000
```

若训练时 CUDA 显存不足，先添加 `--batch_size=4`。数据仍保存 480p；不要为了调整
batch size 改变录制数据特征。

### 5. ACT 单臂推理

推理配置是 [a1z_single_realsense.yaml](a1z_lerobot/configs/a1z_single_realsense.yaml)。
默认不在退出时自动回初始位，也不在 Robot 断开时自动回零：

```bash
python -m a1z_lerobot.scripts.rollout_act_single \
  --config_path=a1z_lerobot/configs/a1z_single_realsense.yaml \
  --robot.cameras.top_rgb.serial_number_or_name=D435_SERIAL \
  --robot.cameras.wrist_rgb.serial_number_or_name=D405_SERIAL \
  --policy.path=outputs/act_a1z_single/checkpoints/last/pretrained_model \
  --strategy.type=base \
  --inference.type=sync \
  --task='Pick up the object and place it in the tray' \
  --duration=30
```

rollout 会在控制前核对 checkpoint 的状态、动作和视觉特征。ACT 使用同步推理；RTC
主要用于推理延迟更高的 VLA，不是此单臂 ACT 流程的默认选项。
