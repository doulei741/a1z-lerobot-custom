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
`260522273365`，右腕 D405 序列号 `260522278763`。更换相机后再使用
`lerobot-find-cameras realsense` 探测并替换下文对应序列号。

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

### Leader 与 Follower 的一次性零位配对

STS3215 行程标定只建立 Leader 自身的角度坐标，不能自动得知对应 A1Z Follower 的
编码器零位。每套新的 Leader/Follower 组合在两臂摆成相同姿态后，需要计算一次独立的
`joint_offsets_rad`：

```text
offset = Follower 当前六轴角度 - Leader 经 signs/scales 转换后的六轴角度
```

配对结果可重复用于以后开机、遥控、录制和推理，无需每次计算。只有更换或重新标定
Leader、更换 Follower、拆装关节导致机械零位变化时才重新配对。不要通过修改
Leader calibration JSON 来补偿 A1Z 零位。

当前这套左右硬件在 2026-08-10 的配对结果是：

```text
left:  [0.185504249, -1.676119148, -1.985360469, 0.471459368, 0.061374215, 0.089759790]
right: [-0.097389546, -1.672050437, -1.971852804, 0.520146476, -0.038316864, -0.021480975]
```

这些数值只属于当前两条已标定 Leader 与当前两个 Follower 的配对，不应复制到另一套
硬件。

## 3. 纯遥控操作（不录制数据）

`a1z-teleoperate-dual` 只执行 Leader 到 Follower 的实时遥控，不创建数据集，也不写入
episode、视频或动作数据。默认使用 `--robot.cameras='{}'`，因此不连接相机。

### 无相机持续遥控

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
  --teleop.left_arm_config.joint_offsets_rad='[0.185504249,-1.676119148,-1.985360469,0.471459368,0.061374215,0.089759790]' \
  --teleop.right_arm_config.joint_offsets_rad='[-0.097389546,-1.672050437,-1.971852804,0.520146476,-0.038316864,-0.021480975]' \
  --fps=30
```

该命令没有 `--teleop_time_s`，因此会持续遥控且不会录制数据，直到按一次
`Ctrl+C`。一次只小幅移动一个关节，逐轴确认方向、零位和夹爪。方向错误才调整对应侧
的 `joint_signs`，比例误差才调整 `joint_scales`，零位误差调整
`joint_offsets_rad`，不要改动作转换代码。当前保留低速安全值
`max_joint_delta=0.01`；确认后可逐步提高到 `0.02`，不建议直接跳到大值。

若出现 `Gripper home timed out`，先检查对应 Follower 夹爪是否被物体、线材或机械限位
阻挡，再进行录制。退出时只按一次 `Ctrl+C` 并等待两条 A1Z 完成失能；连续按第二次会
中断断电清理，并可能出现 `SocketcanBus was not properly shut down`。

### 可选：纯遥控时追加三路相机和 Rerun

启用相机仍然是纯遥控，不会录制数据。以下是当前三台相机的完整命令：

```bash
a1z-teleoperate-dual \
  --robot.type=a1z \
  --robot.id=a1z_dual \
  --robot.left_can=can0 \
  --robot.right_can=can1 \
  --robot.cameras="{top_rgb: {type: intelrealsense, serial_number_or_name: '025222071608', width: 640, height: 480, fps: 30, color_mode: rgb, use_depth: false}, left_wrist_rgb: {type: intelrealsense, serial_number_or_name: '260522273365', width: 640, height: 480, fps: 30, color_mode: rgb, use_depth: false}, right_wrist_rgb: {type: intelrealsense, serial_number_or_name: '260522278763', width: 640, height: 480, fps: 30, color_mode: rgb, use_depth: false}}" \
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
  --teleop.left_arm_config.joint_offsets_rad='[0.185504249,-1.676119148,-1.985360469,0.471459368,0.061374215,0.089759790]' \
  --teleop.right_arm_config.joint_offsets_rad='[-0.097389546,-1.672050437,-1.971852804,0.520146476,-0.038316864,-0.021480975]' \
  --fps=30 \
  --display_data=true \
  --display_compressed_images=false
```

该命令同样没有时限。`display_data=true` 只把状态、动作和三路画面发送给 Rerun，
不会写入 LeRobot 数据集。训练数据采集必须使用后文的 `a1z-record-dual`，不能把纯
遥控误认为已经录制。

## 4. 三路 RGB 与 Rerun 一集验证

默认配置固定为 RGB 640×480@30，不启用深度。右腕序列号通过短参数传入：

```bash
a1z-record-dual \
  --config_path=a1z_lerobot/configs/record_a1z_dual_realsense.yaml \
  --robot.right_wrist_serial=260522278763 \
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
  --robot.right_wrist_serial=260522278763 \
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
  --robot.right_wrist_serial=260522278763 \
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
4. 让每组 Leader/Follower 处于相同姿态，读取双方六轴并计算该组合独立的 offset。
5. `max_joint_delta=0.01`、无相机、两秒静止验证；无起始跳变后再做五秒逐轴验证。
6. 探测三台相机序列号；将第二台 D405 通过 `--robot.right_wrist_serial` 传入。
7. 录制一个全新目录的十秒 episode，并检查 Rerun 与数据特征。
8. 才开始正式采集、训练和推理。

不要复用另一套实体 Leader 的校准 ID，也不要在未确认左右 CAN 对应关系时运行双臂。
