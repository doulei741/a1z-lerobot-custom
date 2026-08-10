# A1Z 双臂 LeRobot 操作手册

本文对应 `feature/dual-arm-workflow`。双臂由两个七舵机 Leader、两个 A1Z
Follower 和三台 RGB RealSense 组成。两条 Leader 的舵机 ID 都是 1–7 没有冲突，
因为它们位于两个独立串口总线上；ID 1–6 对应 A1Z J1–J6，ID 7 是夹爪。

## 0. 环境与目录

```bash
conda activate lerobot-a1z
cd /home/anno/learning/A1Z_Lerobot/a1z-lerobot/.worktrees/dual-arm-workflow
pip install -e .
```

上面是当前电脑已建立的隔离工作树。以后从 GitHub 全新克隆时，改为检出
`feature/dual-arm-workflow` 分支后在该仓库根目录执行。

每次运行都从仓库根目录执行。安装后应存在：

```bash
a1z-teleoperate-dual --help
a1z-record-dual --help
a1z-train-act-dual --help
a1z-rollout-act-dual --help
```

## 1. 找到两个 Leader、两个 CAN 和三台相机

先只连接一条 Leader，执行并按提示拔插；记录端口。第二条重复一次：

```bash
lerobot-find-port
```

然后连接三台相机：

```bash
lerobot-find-cameras realsense
```

已知设备：D435 顶部序列号 `025222071608`，左腕 D405 序列号
`260522273365`。把探测到的另一台 D405 序列号记为：

```bash
RIGHT_D405_SERIAL=在这里填右腕D405序列号
```

双 USB-CAN 插好后启动总线。每次重启系统都要重新执行：

```bash
bash a1z_lerobot/scripts/setup.sh can0
bash a1z_lerobot/scripts/setup.sh can1
ip -details link show can0
ip -details link show can1
```

必须看到两个接口均为 `UP` 且 bitrate 为 `1000000`。如果接口名称顺序交换，先根据
USB 物理连接确认左右，再调整命令中的 `left_can`/`right_can`，不要带着未知映射上电。

## 2. 分别校准两条 Leader

两条 Leader 使用不同的校准 ID，因此各自保存校准文件：

```bash
a1z-calibrate-leader --port=/dev/ttyACM0 --id=a1z_left_leader
a1z-calibrate-leader --port=/dev/ttyACM1 --id=a1z_right_leader
```

校准文件位于：

```text
~/.cache/huggingface/lerobot/calibration/teleoperators/a1z_leader/
```

更换 Leader 后使用新的 ID，例如 `a1z_left_leader_02`，不要覆盖已经验收的校准文件。
同一条 Leader 的 ID 1–7 不需要更改；左右 Leader 的端口必须不同。

## 3. 五秒无相机低速遥控验收

先清空机械臂周围空间并准备急停。两条 Leader 和 Follower 摆到对应的安全姿态，运行：

```bash
a1z-teleoperate-dual \
  --robot.type=a1z \
  --robot.id=a1z_dual \
  --robot.left_can=can0 \
  --robot.right_can=can1 \
  --robot.cameras='{}' \
  --robot.ema_alpha=0.3 \
  --robot.max_joint_delta=0.01 \
  --robot.gripper_start_hold=true \
  --robot.return_home_on_disconnect=false \
  --robot.open_grippers_on_disconnect=false \
  --teleop.type=bi_a1z_leader \
  --teleop.id=a1z_bi_leader \
  --teleop.left_id=a1z_left_leader \
  --teleop.right_id=a1z_right_leader \
  --teleop.left_arm_config.port=/dev/ttyACM0 \
  --teleop.right_arm_config.port=/dev/ttyACM1 \
  --teleop.left_arm_config.joint_signs='[-1,1,1,1,1,-1]' \
  --teleop.right_arm_config.joint_signs='[-1,1,1,1,1,-1]' \
  --teleop.left_arm_config.joint_scales='[1,1,1,1,1,1]' \
  --teleop.right_arm_config.joint_scales='[1,1,1,1,1,1]' \
  --teleop.left_arm_config.joint_offsets_rad='[-0.040418965,1.567886653,-1.698370257,-0.144229406,-0.011507665,-0.016411362]' \
  --teleop.right_arm_config.joint_offsets_rad='[-0.040418965,1.567886653,-1.698370257,-0.144229406,-0.011507665,-0.016411362]' \
  --fps=30 \
  --teleop_time_s=5
```

一次只小幅移动一个关节，逐轴确认方向、零位和夹爪。新的一对 Leader/Follower 若机械
装配零位不同，只调整对应侧的 `joint_signs`、`joint_scales` 和
`joint_offsets_rad`，不要改动作转换代码。确认后可把 `max_joint_delta` 提高到
`0.02`，最终根据现场响应逐步提高，但不建议直接跳到大值。

## 4. 三路 RGB 与 Rerun 一集验证

默认配置固定为 RGB 640×480@30，不启用深度。右腕序列号通过短参数传入：

```bash
a1z-record-dual \
  --config_path=a1z_lerobot/configs/record_a1z_dual_realsense.yaml \
  --robot.right_wrist_serial="$RIGHT_D405_SERIAL" \
  --dataset.repo_id=local/a1z_dual_smoke \
  --dataset.root=datasets/a1z_dual_smoke \
  --dataset.single_task='Dual-arm smoke test' \
  --dataset.num_episodes=1 \
  --dataset.episode_time_s=10 \
  --dataset.reset_time_s=5 \
  --display_data=true \
  --display_compressed_images=false
```

`datasets/a1z_dual_smoke` 必须是尚不存在的新目录；如果要继续已有且特征完全相同的
数据集，显式添加 `--resume=true`。Rerun 窗口应同时显示 `top_rgb`、
`left_wrist_rgb`、`right_wrist_rgb`，三者均是彩色 640×480 图像。

录制快捷键：

- `→`：提前结束当前录制或复位阶段。
- `←`：丢弃当前未保存 episode，并重新录制这一集。
- `Esc`：停止整个录制任务，已保存 episode 会保留并 finalize。

## 5. 正式录制

烟雾测试通过后换一个新的数据集目录：

```bash
a1z-record-dual \
  --config_path=a1z_lerobot/configs/record_a1z_dual_realsense.yaml \
  --robot.right_wrist_serial="$RIGHT_D405_SERIAL" \
  --dataset.repo_id=local/a1z_dual_task_01 \
  --dataset.root=datasets/a1z_dual_task_01 \
  --dataset.single_task='Describe exactly one task in English' \
  --dataset.num_episodes=50 \
  --dataset.episode_time_s=60 \
  --dataset.reset_time_s=30 \
  --display_data=true
```

固定数据契约为 14D `observation.state`、14D `action` 和三路 RGB。训练和推理的
相机键、分辨率以及状态/动作维度必须完全一致。录制标签是经过 EMA、逐帧关节限幅和
夹爪起始保持后实际发给 Follower 的动作。

## 6. RTX 4060 训练 ACT

默认使用 CUDA 和 batch size 8：

```bash
a1z-train-act-dual \
  --dataset.repo_id=local/a1z_dual_task_01 \
  --dataset.root=datasets/a1z_dual_task_01 \
  --output_dir=outputs/act_a1z_dual_task_01 \
  --steps=100000 \
  --save_freq=10000
```

RTX 4060 显存不足时添加 `--batch_size=4`，仍保持原始 480p 数据与三路视觉键不变。

## 7. 十秒 ACT 推理验收

先用十秒、同步推理和空工作区验证：

```bash
a1z-rollout-act-dual \
  --config_path=a1z_lerobot/configs/a1z_dual_realsense.yaml \
  --robot.right_wrist_serial="$RIGHT_D405_SERIAL" \
  --policy.path=outputs/act_a1z_dual_task_01/checkpoints/last/pretrained_model \
  --strategy.type=base \
  --inference.type=sync \
  --task='Describe exactly one task in English' \
  --duration=10
```

rollout 会在连接并发送策略动作前验证 checkpoint：状态 `(14,)`、动作 `(14,)` 和
三路视觉键/尺寸必须与机器人一致。推理配置令 `gripper_start_hold=false`，因为模型输出
是物理绝对夹爪位置；退出默认不回零、不主动张开夹爪。

## 8. 安全参数含义

- `gripper_start_hold=true`：遥控开始时每侧夹爪保持 Follower 实际开度，Leader
  第一次动作之后按增量跟随，避免起始跳变；录制默认开启。
- `gripper_start_hold=false`：策略的绝对夹爪输出直接生效；推理默认使用。
- `return_home_on_disconnect=false`：退出时不自动回 Home。
- `open_grippers_on_disconnect=false`：退出时不自动张开夹爪。

后两项保持 `false` 是双臂默认安全退出行为。只有在无碰撞路径经过实机验证后才应显式
开启。任一手臂、相机或 Leader 连接失败时，适配器会清理已经连接的另一侧资源。

## 9. 换另一套双臂快速上手

1. 记录两个新 Leader 的稳定串口；两个串口不能相同。
2. 使用新的唯一校准 ID 分别执行 `a1z-calibrate-leader`。
3. 确认两个 CAN 接口及左右对应关系。
4. 探测三台相机序列号；将第二台 D405 通过 `--robot.right_wrist_serial` 传入。
5. `max_joint_delta=0.01`、无相机、五秒逐轴验证；左右映射独立调整。
6. 录制一个全新目录的十秒 episode，并检查 Rerun 与数据特征。
7. 才开始正式采集、训练和推理。

不要复用另一套实体 Leader 的校准 ID，也不要在未确认左右 CAN 对应关系时运行双臂。
