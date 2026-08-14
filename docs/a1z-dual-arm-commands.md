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

当前这套左右硬件在 2026-08-11 修正二轴方向后的配对结果是：

```text
signs: [-1, -1, 1, 1, 1, -1]
left:  [0.185504249, 1.676119148, -1.985360469, 0.471459368, 0.061374215, 0.089759790]
right: [-0.097389546, 1.672050437, -1.971852804, 0.520146476, -0.038316864, -0.021480975]
```

这些数值只属于当前两条已标定 Leader 与当前两个 Follower 的配对，不应复制到另一套
硬件。

### Follower 六轴与夹爪校准

这里要区分三类参数，不能混在一起调整：

- `a1z-calibrate-leader` 只标定 Leader 的 ST3215 行程；生成的
  `homing_offset`、`range_min`、`range_max` 不控制 A1Z Follower。
- A1Z Follower J1–J6 的零点保存在对应从臂电机中，只在机械零位确实错误、关节拆装或
  更换电机后使用 SDK 的 `set_zero.py` 重写。
- A1Z Follower 夹爪是 CAN ID 7，使用 `gripper_set_zero.py` 把机械行程中点写为夹爪
  Flash 零点；正常出厂设备和每次开机都不需要重复执行。

校准会让从臂运动并改写电机保存的零点。一次只连接和处理一条 Follower，清空工作空间、
准备急停，并把 J1–J6 准确摆到 SDK 定义的机械零位。左从臂 `can0` 的完整命令：

```bash
conda activate lerobot-a1z
cd /home/anno/learning/A1Z_Lerobot/a1z-lerobot/.worktrees/dual-arm-workflow
bash a1z_lerobot/scripts/setup.sh can0
ip -details link show can0
sudo python GALAXEA-A1Z/tools/set_zero.py --all --channel can0
```

右从臂 `can1` 的完整命令：

```bash
conda activate lerobot-a1z
cd /home/anno/learning/A1Z_Lerobot/a1z-lerobot/.worktrees/dual-arm-workflow
bash a1z_lerobot/scripts/setup.sh can1
ip -details link show can1
python GALAXEA-A1Z/tools/set_zero.py --all --channel can1
```

不要在日常配对时运行 `set_zero.py --all`，也不要使用 `-y` 跳过脚本自身的现场确认。
如果只有一个关节确实需要重设，使用零基索引 `0..5`，例如仅处理物理 J2：

```bash
sudo python GALAXEA-A1Z/tools/set_zero.py --joints 1 --channel can0
```

Follower 夹爪出现全行程整体偏移，并且确认不是 Leader 行程、映射或夹持力矩问题后，
才执行中心零点校准。下面以当前出现问题的右 Follower（`can1`、电机 ID 7）为例。

#### 执行修复前先检查机械结构

断开右 Follower 电源，逐项检查：

- 电机输出轴固定螺丝是否松动；
- 联轴器是否打滑；
- 齿轮或同步结构是否错齿；
- 两个夹指是否对称；
- 夹爪连杆是否弯曲、摩擦或卡住；
- 电机或夹爪最近是否拆装过。

如果固定螺丝松动，先恢复正确的机械结构并拧紧，再重新标定。机械连接没有固定时，写入
新的电机零位只能暂时补偿，继续使用后仍会再次漂移。

#### 重新标定右 Follower 夹爪零位

确认机械结构正常、夹爪全行程可以自由运动后，关闭遥控、录制、推理及其他占用
`can1` 的程序，清空夹爪周围物体并确保手指远离夹爪。执行：

```bash
conda activate lerobot-a1z
cd /home/anno/learning/A1Z_Lerobot/a1z-lerobot/.worktrees/dual-arm-workflow

python GALAXEA-A1Z/tools/gripper_set_zero.py \
  --can can1 \
  --half-travel 2.87
```

不要添加 `-y`。先核对程序显示的是 `can1`、电机 ID `0x07` 和半行程
`2.87 rad`，然后按提示手动输入 `y`。工具会实际执行：

1. 向正方向运动，通过堵转检测寻找右夹爪真实的闭合机械限位；
2. 在闭合限位建立临时 RAM 零点；
3. 向张开方向运动 `2.87 rad`，到达机械行程中点；
4. 把该中点写入电机 Flash 作为持久零位；
5. 使目标行程重新对应为：完全张开 `-2.87 rad`、中间位置 `0.00 rad`、完全闭合
   `+2.87 rad`。

该操作会移动夹爪，并持久化修改 `can1` 上 ID 7 电机的 Flash 零位。执行过程中不能触碰
夹爪，也不能让物体阻挡自动寻找机械限位的过程。

#### 标定完成后断电重启并验收

工具结束时应看到类似输出：

```text
Verification: position after flash write = 0.0000 rad
```

验证值应接近 `0.0 rad`。随后关闭右 Follower 电源，等待几秒再重新上电。如果
`can1` 消失，重新初始化并检查接口：

```bash
bash a1z_lerobot/scripts/setup.sh can1
ip -details link show can1
```

不要启动双臂遥控，先对右夹爪运行隔离的空载全行程测试：

```bash
python GALAXEA-A1Z/examples/gripper_hybrid_test.py \
  --can can1 \
  --torque 2.0 \
  --tests free
```

修复后的预期结果：

- 启动归位可以到达全开位置，不再出现 `Gripper home timed out`；
- `关闭(0.0)` 的反馈接近 `0.000`；
- `半开(0.5)` 的反馈接近 `0.500`；
- `全开(1.0)` 的反馈接近 `1.000`；
- 三个目标的反馈误差均不超过 `0.1`，并显示到达目标。

测试中的归一化定义固定为 `0.0=闭合`、`1.0=全开`。如果仍在接近某个端点时力矩明显
升高且反馈无法到达目标，继续检查机械止挡、安装偏心、错齿和异物；不能靠扩大 Leader
JSON 的 `range_min/range_max` 修复 Follower 机械问题。左 Follower 需要执行相同流程时，
把上述命令中的 `can1` 全部替换为 `can0`。

任何 Follower 六轴零点重写、Follower 更换或 Leader 重新标定都会改变两臂坐标关系。
完成后必须重新执行上一节的同姿态配对，重新计算对应侧六个
`joint_offsets_rad`，再按 `max_joint_delta=0.01` 从静止和逐轴小幅遥控开始验收；旧
offset 不得直接复用。只重新校准夹爪中心零点时，六轴 offset 不变，但必须重新验证
夹爪的开闭端点和正式录制动作。

### Leader 二、三轴独立诊断

诊断脚本只连接 Leader 串口，不连接 CAN、Follower、相机或录制器。运行左 Leader：

```bash
python -m a1z_lerobot.tools.diagnose_leader_joints \
  --port=/dev/ttyACM0 \
  --id=a1z_left_leader \
  --duration-s=30 \
  --threshold-rad=0.02 \
  --joint-indices 1 2
```

运行右 Leader：

```bash
python -m a1z_lerobot.tools.diagnose_leader_joints \
  --port=/dev/ttyACM1 \
  --id=a1z_right_leader \
  --duration-s=30 \
  --threshold-rad=0.02 \
  --joint-indices 1 2
```

每次先只移动物理二轴，再回到基准姿态，然后只移动物理三轴。输出中的 `J2/J3` 是当前
映射角度，`delta_J2/delta_J3` 是相对启动基准的变化：

- 物理二轴只改变 `delta_J2`，但方向与 A1Z 相反：调整二轴 `joint_signs` 并重新计算
  该轴 offset。
- 物理二轴只改变 `delta_J3`：检查 STS3215 ID 2/3 与物理关节的安装对应。
- 物理二轴同时改变两项：Leader 结构或手动动作存在二、三轴耦合，需要先测量解耦关系。
- Leader 输出正确而 Follower 仍响应错误：再检查实际发送给 A1Z SDK 的 14D target。

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
  --robot.gripper_start_hold=false \
  --robot.return_home_on_disconnect=false \
  --robot.open_grippers_on_disconnect=false \
  --teleop.type=bi_a1z_leader \
  --teleop.id=a1z_bi_leader \
  --teleop.left_id=a1z_left_leader \
  --teleop.right_id=a1z_right_leader \
  --teleop.left_arm_config.port=/dev/ttyACM0 \
  --teleop.right_arm_config.port=/dev/ttyACM1 \
  --teleop.left_arm_config.joint_signs='[-1,-1,1,1,1,-1]' \
  --teleop.right_arm_config.joint_signs='[-1,-1,1,1,1,-1]' \
  --teleop.left_arm_config.joint_scales='[1,1,1,1,1,1]' \
  --teleop.right_arm_config.joint_scales='[1,1,1,1,1,1]' \
  --teleop.left_arm_config.joint_offsets_rad='[0.185504249,1.676119148,-1.985360469,0.471459368,0.061374215,0.089759790]' \
  --teleop.right_arm_config.joint_offsets_rad='[-0.097389546,1.672050437,-1.971852804,0.520146476,-0.038316864,-0.021480975]' \
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

当一切都调整好了就可以用下述代码了：
```bash
a1z-teleoperate-dual \
  --robot.type=a1z \
  --robot.id=a1z_dual \
  --robot.left_can=can0 \
  --robot.right_can=can1 \
  --robot.cameras='{}' \
  --robot.ema_alpha=1 \
  --robot.max_joint_delta=0.05 \
  --robot.gripper_start_hold=false \
  --robot.return_home_on_disconnect=false \
  --robot.open_grippers_on_disconnect=false \
  --teleop.type=bi_a1z_leader \
  --teleop.id=a1z_bi_leader \
  --teleop.left_id=a1z_left_leader \
  --teleop.right_id=a1z_right_leader \
  --teleop.left_arm_config.port=/dev/ttyACM0 \
  --teleop.right_arm_config.port=/dev/ttyACM1 \
  --teleop.left_arm_config.joint_signs='[-1,-1,1,1,1,-1]' \
  --teleop.right_arm_config.joint_signs='[-1,-1,1,1,1,-1]' \
  --teleop.left_arm_config.joint_scales='[1,1,1,1,1,1]' \
  --teleop.right_arm_config.joint_scales='[1,1,1,1,1,1]' \
  --teleop.left_arm_config.joint_offsets_rad='[0.185504249,1.676119148,-1.985360469,0.471459368,0.061374215,0.089759790]' \
  --teleop.right_arm_config.joint_offsets_rad='[-0.097389546,1.672050437,-1.971852804,0.520146476,-0.038316864,-0.021480975]' \
  --fps=30
```

### 可选：纯遥控时追加三路相机和 Rerun

启用相机仍然是纯遥控，不会录制数据。以下是当前三台相机的完整命令：

```bash
a1z-teleoperate-dual \
  --robot.type=a1z \
  --robot.id=a1z_dual \
  --robot.left_can=can0 \
  --robot.right_can=can1 \
  --robot.cameras="{top_rgb: {type: intelrealsense, serial_number_or_name: '025222071608', width: 640, height: 480, fps: 30, color_mode: rgb, use_depth: false}, left_wrist_rgb: {type: intelrealsense, serial_number_or_name: '260522273365', width: 640, height: 480, fps: 30, color_mode: rgb, use_depth: false}, right_wrist_rgb: {type: intelrealsense, serial_number_or_name: '260522278763', width: 640, height: 480, fps: 30, color_mode: rgb, use_depth: false}}" \
  --robot.ema_alpha=1 \
  --robot.max_joint_delta=0.05 \
  --robot.gripper_start_hold=false \
  --robot.return_home_on_disconnect=false \
  --robot.open_grippers_on_disconnect=false \
  --teleop.type=bi_a1z_leader \
  --teleop.id=a1z_bi_leader \
  --teleop.left_id=a1z_left_leader \
  --teleop.right_id=a1z_right_leader \
  --teleop.left_arm_config.port=/dev/ttyACM0 \
  --teleop.right_arm_config.port=/dev/ttyACM1 \
  --teleop.left_arm_config.joint_signs='[-1,-1,1,1,1,-1]' \
  --teleop.right_arm_config.joint_signs='[-1,-1,1,1,1,-1]' \
  --teleop.left_arm_config.joint_scales='[1,1,1,1,1,1]' \
  --teleop.right_arm_config.joint_scales='[1,1,1,1,1,1]' \
  --teleop.left_arm_config.joint_offsets_rad='[0.185504249,1.676119148,-1.985360469,0.471459368,0.061374215,0.089759790]' \
  --teleop.right_arm_config.joint_offsets_rad='[-0.097389546,1.672050437,-1.971852804,0.520146476,-0.038316864,-0.021480975]' \
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

方向键必须单击，不要连续按住或快速连按。终端显示 `^[[C` 是右方向键的 ANSI 序列，
随后出现 `Right arrow key pressed. Exiting loop...` 表示监听生效；`^[[A` 对应上方向
键，不会触发提前结束。当前录制器的按键状态在录制和 reset 阶段共享：录制阶段按一次
`→` 后，等待出现 `Reset the environment`；如需跳过 reset，再单击一次 `→`，然后停止
按键并等待下一条 `Recording episode N`。连续右键可能把事件带入下一集，使下一集在
写入首帧前退出并触发 `You must add one or several frames` 的空 episode 错误。

希望每集按一次右键后直接保存并进入下一集时，将命令设置为：

```bash
--dataset.reset_time_s=0
```

## 5. 正式录制

烟雾测试通过后换一个新的数据集目录：

```bash
a1z-record-dual \
  --config_path=a1z_lerobot/configs/record_a1z_dual_realsense.yaml \
  --robot.right_wrist_serial=260522278763 \
  --dataset.repo_id=local/a1z_dual_task_8.12 \
  --dataset.root=datasets/a1z_dual_task_8.12 \
  --dataset.single_task='Pick up the pen with your left hand and pass it to your right hand. The right hand receives the pen, then places the pen into the black pen holder. The left hand picks up another pen; the right hand takes the pen and puts it beside the orange book.' \
  --dataset.num_episodes=50 \
  --dataset.episode_time_s=120 \
  --dataset.reset_time_s=10 \
  --display_data=true \
  --display_compressed_images=false
```

固定数据契约为 14D `observation.state`、14D `action` 和三路 RGB。训练和推理的
相机键、分辨率以及状态/动作维度必须完全一致。录制标签是经过 EMA、逐帧关节限幅和
夹爪起始保持后实际发给 Follower 的动作。

### 中断后继续录制（resume）

`Ctrl+C` 或 `Esc` 停止后，已经保存并 finalize 的 episode 可以继续追加。resume 时
`--dataset.num_episodes` 表示“本次新增多少集”，不是最终总集数。例如当前数据集已经
保存 25 集，目标总数为 40 集时，本次必须填写 `15`；如果填写 `40`，最终会得到 65 集。

当前 `local/a1z_dual_task_8.11` 从 25 集继续录到 40 集的完整命令：

```bash
a1z-record-dual \
  --config_path=a1z_lerobot/configs/record_a1z_dual_realsense.yaml \
  --resume=true \
  --robot.right_wrist_serial=260522278763 \
  --dataset.repo_id=local/a1z_dual_task_8.11 \
  --dataset.root=datasets/a1z_dual_task_8.11 \
  --dataset.single_task='Pick up the pen with your left hand, pick up the pen holder with your right hand. Put the pen from your left hand into the pen holder held in your right hand, then place the pen holder at the designated position.' \
  --dataset.num_episodes=15 \
  --dataset.episode_time_s=60 \
  --dataset.reset_time_s=10 \
  --display_data=true \
  --display_compressed_images=false
```

该命令会从 episode 索引 25（第 26 集）开始追加，到索引 39 为止。`repo_id`、`root`、
任务文本、FPS、三路相机键/尺寸以及 14D state/action 必须与已有数据集保持一致；程序会
在连接硬件后、正式追加前执行兼容性检查。停止整个录制任务优先使用 `Esc`，它会保留已
保存 episode 并 finalize 当前数据集；正在录制但尚未保存的 episode 不计入总数。

## 6. RTX 4060 训练 ACT

### 6.1 新建一次 ACT 训练

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

### 6.2 从云端 checkpoint 在本机继续训练

当前云端训练使用的原始命令以 300000 为总步数，每 50000 步保存一次。下载到本机的
最新完整 checkpoint 是 `150000`，包含以下继续训练所需内容：

```text
checkpoints/150000/pretrained_model
checkpoints/150000/training_state/optimizer_state.safetensors
checkpoints/150000/training_state/rng_state.safetensors
checkpoints/150000/training_state/training_step.json
```

这里必须使用 `lerobot-a1z` Conda 环境，不能使用旧的 `lerobot` 环境。当前电脑上的
`lerobot` 环境是 Python 3.10、Torch 2.1.1，并指向另一个旧 LeRobot 仓库；
`lerobot-a1z` 是 Python 3.12、CUDA 可用，并加载当前项目中的 LeRobot 代码，与下载的
checkpoint、LeRobot v3 数据集及断点恢复格式一致。

本机数据集路径为：

```text
/home/anno/learning/A1Z_Lerobot/a1z-lerobot/.worktrees/dual-arm-workflow/datasets/a1z_dual_task_8.11
```

该数据集已经验证可被当前 LeRobot 加载，包含 40 个 episode、71527 帧、14D state、
14D action 和三路 640×480 RGB。先确认环境和训练入口来自当前项目：

```bash
conda activate lerobot-a1z
cd /home/anno/learning/A1Z_Lerobot/a1z-lerobot/.worktrees/dual-arm-workflow
which lerobot-train
python -c "import sys, lerobot; print(sys.version); print(lerobot.__file__)"
```

`python` 应显示 3.12，`lerobot.__file__` 应位于：

```text
/home/anno/learning/A1Z_Lerobot/a1z-lerobot/lerobot/src/lerobot/
```

从 150000 步真正恢复模型权重、优化器状态、随机状态和数据采样位置，并训练到总计
300000 步的完整命令是：

```bash
lerobot-train \
  --config_path=/home/anno/learning/A1Z_Lerobot/a1z-lerobot/outputs/a1z_dual_task_8.11/checkpoints/150000/pretrained_model/train_config.json \
  --resume=true \
  --dataset.repo_id=a1z_pick_40 \
  --dataset.root=/home/anno/learning/A1Z_Lerobot/a1z-lerobot/.worktrees/dual-arm-workflow/datasets/a1z_dual_task_8.11 \
  --dataset.video_backend=torchcodec \
  --output_dir=/home/anno/learning/A1Z_Lerobot/a1z-lerobot/outputs/a1z_dual_task_8.11 \
  --job_name=a1z_pick_40 \
  --policy.device=cuda \
  --wandb.enable=false \
  --policy.push_to_hub=false \
  --steps=300000 \
  --batch_size=4 \
  --num_workers=4 \
  --save_freq=50000 \
  --log_freq=100 \
  --save_checkpoint=true
```

`--steps=300000` 表示训练结束时的总步数，不是从 150000 再训练 300000 步。程序读取
`training_step.json` 中的 `150000` 后，只执行剩余约 150000 次更新，正常情况下继续生成
`200000`、`250000`、`300000` checkpoint，并把 `checkpoints/last` 更新为最新一步。

不要把上述命令改成只有
`--policy.path=.../150000/pretrained_model` 的普通训练：那种方式只加载策略权重，不恢复
优化器、随机状态和数据采样位置，不属于原训练任务的真正断点续训。模型结构、图像增强、
ACT chunk、VAE 和优化器超参数已经从 checkpoint 内的 `train_config.json` 恢复，无需在
命令行重复整套参数。

开始后日志应明确包含类似信息：

```text
cfg.steps=300000
Resuming data order at epoch ...
Training .../150000
```

另开一个终端监控 RTX 4060：

```bash
watch -n 1 nvidia-smi
```

为了尽可能保持云端训练的数据顺序，首先保持原来的 `batch_size=4`。如果本机显存确实
出现 CUDA OOM，可以停止后重新运行同一条命令并改为 `--batch_size=2`；程序可以继续，
但会警告 batch size 与 checkpoint 不同，之后的数据顺序不再是严格逐样本一致。不要通过
删除已有 checkpoint 或清空输出目录来处理 OOM。

## 7. 已训练模型下载检查与十秒 ACT 推理验收

当前从云端下载并验收的模型目录是：

```text
/home/anno/learning/A1Z_Lerobot/a1z-lerobot/outputs/a1z_dual_task_8.11
```

其中包含 `050000`、`100000`、`150000` 三个 checkpoint，`last` 指向
`150000`。最新推理模型的完整路径是：

```text
/home/anno/learning/A1Z_Lerobot/a1z-lerobot/outputs/a1z_dual_task_8.11/checkpoints/150000/pretrained_model
```

本地检查确认该 checkpoint 的 `model.safetensors` 大小为 `247031288` 字节，并可正常
解析 314 个张量。模型契约是 14D `observation.state`、14D `action`，以及以下三路
640×480 RGB 输入：

```text
observation.images.top_rgb
observation.images.left_wrist_rgb
observation.images.right_wrist_rgb
```

虽然 `train_config.json` 中的训练目标是 300000 步，但当前实际下载到的最新 checkpoint
是 150000 步，因此现阶段推理明确使用 `150000/pretrained_model`。

### 7.1 推理前准备

ACT 推理不需要连接两条 Leader，只需要两个 A1Z Follower、两个 USB-CAN 和三台
RealSense。先激活正确环境并进入双臂工作树：

```bash
conda activate lerobot-a1z
cd /home/anno/learning/A1Z_Lerobot/a1z-lerobot/.worktrees/dual-arm-workflow
```

每次开机或重新插拔 USB-CAN 后初始化并检查两条 CAN 总线：

```bash
bash a1z_lerobot/scripts/setup.sh can0
bash a1z_lerobot/scripts/setup.sh can1
ip -details link show can0
ip -details link show can1
```

两个接口都必须显示 `UP`、bitrate `1000000`，CAN 状态正常。然后确认三台相机：

```bash
lerobot-find-cameras realsense
```

当前硬件应对应：

```text
顶部 D435：025222071608
左腕 D405：260522273365
右腕 D405：260522278763
```

推理前把双臂和任务物体恢复到录制数据每集开始时的初始状态，清空机械臂工作空间，
人手远离机械臂并准备急停。策略输出的是绝对动作，因此程序启动后 Follower 自主运动是
正常现象；如果初始状态与训练数据差异过大，应立即停止并重新摆放。

### 7.2 第一次十秒低速推理

第一次验证使用同步推理、十秒时限和 `max_joint_delta=0.01` 的保守逐帧限幅，并打开
Rerun 查看三路相机与状态：

```bash
a1z-rollout-act-dual \
  --config_path=a1z_lerobot/configs/a1z_dual_realsense.yaml \
  --robot.right_wrist_serial=260522278763 \
  --robot.ema_alpha=0.3 \
  --robot.max_joint_delta=0.01 \
  --robot.gripper_start_hold=false \
  --robot.return_home_on_disconnect=false \
  --robot.open_grippers_on_disconnect=false \
  --policy.path=/home/anno/learning/A1Z_Lerobot/a1z-lerobot/outputs/a1z_dual_task_8.11/checkpoints/300000/pretrained_model \
  --strategy.type=base \
  --inference.type=sync \
  --task='Pick up the pen with your left hand, pick up the pen holder with your right hand. Put the pen from your left hand into the pen holder held in your right hand, then place the pen holder at the designated position.' \
  --fps=30 \
  --duration=60 \
  --display_data=true
```

rollout 按“加载 checkpoint → 创建机器人配置并核对策略特征 → 连接硬件 → 发送动作”的
顺序执行。策略特征必须与机器人配置的 14D state、14D action 和三路视觉键/尺寸完全
一致，否则在发送策略动作前停止。

`gripper_start_hold=false` 是推理所需设置：ACT 输出的双臂绝对夹爪位置应立即生效，
不能使用遥控录制模式的夹爪起始保持。退出默认不回零、不主动张开夹爪。需要提前停止时
只按一次 `Ctrl+C`，然后等待两条 A1Z 完成停止和失能；不要连续按 `Ctrl+C`，否则可能
中断 CAN 清理。

### 7.3 通过低速验证后

逐项确认左右臂方向正确、没有启动跳变、三路画面对应正确、夹爪响应正确，且十秒内没有
CUDA、特征或相机错误。通过后可将上述完整命令中的：

```text
--robot.max_joint_delta=0.01
```

改为录制时使用的：

```text
--robot.max_joint_delta=0.05
```

其余模型路径、三路相机键、分辨率、任务文本和 30 FPS 保持不变。不要在第一次模型验证
时直接取消限幅或提高控制频率。

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
