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
