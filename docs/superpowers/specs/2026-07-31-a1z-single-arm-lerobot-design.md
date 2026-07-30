# A1Z 单臂 LeRobot 数据采集、ACT 训练与推理设计

日期：2026-07-31

## 1. 目标

在不破坏现有 A1Z 双臂适配的前提下，为本仓库增加一套完整的单臂工作流：

- 使用一个改装为 7 个 STS3215 舵机的 LeRobot 示教臂遥控一条 A1Z；
- 示教臂 ID 1–6 分别对应 A1Z J1–J6，ID 7 对应夹爪；
- 使用一台 Intel RealSense D435 作为顶部相机、一台 Intel RealSense D405
  作为手腕相机；
- 两台相机只采集 RGB，不采集深度，分辨率为 640×480，帧率为 30 FPS；
- 直接生成符合当前 LeRobot v3 规范的数据集；
- 使用 LeRobot 原生 ACT 训练入口训练策略；
- 加载 ACT checkpoint，在单臂 A1Z 上按与双臂相同的控制方式执行推理；
- 相机数量通过配置参数决定，代码不固定为两台相机。

本设计只覆盖单臂关节位置控制、RGB 录制、ACT 训练与 ACT 实机推理。它不增加深度
输入、末端笛卡尔控制、双臂协调、力控或远程网络控制。

## 2. 已确认的硬件与时间基准

- 示教臂：7 个 7.4 V STS3215，通过同一串口控制板连接。
- 舵机映射：ID 1–6 对应 A1Z J1–J6，ID 7 对应 A1Z 夹爪。
- 跟随臂：一条 A1Z，通过单个 SocketCAN 接口连接，默认 `can0`。
- 顶部视觉：Intel RealSense D435。
- 手腕视觉：Intel RealSense D405。
- 图像：RGB，640×480，30 FPS，RealSense `use_depth=false`。
- LeRobot 录制与推理外环：30 FPS。
- A1Z SDK 内部控制环：保持现有 250 Hz。
- 训练设备：NVIDIA RTX 4060，ACT 默认训练 batch size 为 8，并允许通过参数降为 4。

## 3. 方案选择

采用独立适配方案：

- 在 `a1z_lerobot` 包内增加 `a1z_single` Robot；
- 在 `a1z_lerobot` 包内增加 `a1z_leader` Teleoperator；
- 复用现有 `A1ZArm` 单臂硬件包装和 GALAXEA-A1Z SDK；
- 通过薄脚本注册本地 Robot/Teleoperator，再调用 LeRobot 原生遥控、录制、训练和
  rollout 流程；
- 保留现有 `a1z` 双臂 Robot、14D 数据定义和三相机配置。

不修改 LeRobot 内置 `so101_leader`。标准 SO101 仍保持 5 个臂关节加夹爪的上游定义，
避免本地七轴硬件改变标准设备行为，也减少未来同步 LeRobot 上游代码时的冲突。

## 4. 组件边界

### 4.1 单臂 Robot

注册名为 `a1z_single`，负责：

- 从配置接收单个 `can_channel`；
- 构造并管理现有 `A1ZArm`；
- 公开七维状态和动作特征；
- 根据相机配置字典动态构造、连接和读取相机；
- 对动作执行有限值校验、EMA、逐帧关节增量限制、A1Z 硬限位和夹爪限位；
- 返回实际发送给 A1Z 的动作；
- 失败或退出时停止 A1Z、断开相机并失能，不默认回零。

配置提供 `return_home_on_disconnect: bool = false`。只有显式设置为 `true` 时，正常退出
才执行回零；异常退出不执行回零。

### 4.2 七轴示教器

注册名为 `a1z_leader`，负责：

- 在同一个 Feetech 串口总线上配置 ID 1–7 的 STS3215；
- 前六个舵机采用角度校准，第七个夹爪采用 `[0,100]` 行程归一化；
- 将前六轴从校准后的角度转换为 A1Z 弧度目标；
- 对每一轴应用可配置的 `scale`、`sign` 和 `offset_rad`；
- 将夹爪转换为 `[0,1]`；
- 使用与 A1Z Robot 完全相同的动作键返回动作；
- 使用 LeRobot 现有校准文件机制持久化 STS3215 校准。

转换公式为：

```text
a1z_joint_rad[i] =
    radians(leader_joint_degrees[i]) * scale[i] * sign[i] + offset_rad[i]
```

默认 `scale=1`、`sign=1`、`offset_rad=0`。方向或零位不一致时只修改配置，不修改采集
代码。

### 4.3 相机

相机继续使用 LeRobot `CameraConfig` 字典，不在 Robot 中写死 D435/D405 数量或型号。
默认示例包含：

- `top_rgb`：D435，640×480，30 FPS，RGB，`use_depth=false`；
- `wrist_rgb`：D405，640×480，30 FPS，RGB，`use_depth=false`。

设备通过 RealSense 序列号选择。命令行可以传入空字典、单个相机、默认两个相机或更多
相机。录制数据和 checkpoint 必须使用相同的相机键、数量、分辨率和颜色通道。

### 4.4 运行入口

增加薄入口以导入本地注册类型后调用 LeRobot 原生功能：

- 单臂遥控：只运行示教器到 A1Z 的控制闭环，不写数据集；
- 单臂录制：调用 LeRobot 原生 `record` 流程生成 v3 数据集；
- ACT 训练：调用 LeRobot 原生训练入口；
- ACT rollout：调用 LeRobot 原生 rollout，加载 ACT checkpoint 并控制 `a1z_single`。

所有硬件地址、相机配置、数据集路径、episode 数量、任务文本、ACT checkpoint、batch
size 和控制参数均通过命令行或配置文件传入。

## 5. 数据契约

### 5.1 动作和状态

七维顺序固定为：

```text
arm_0, arm_1, arm_2, arm_3, arm_4, arm_5, gripper
```

字典特征键固定为：

```text
arm_0.pos
arm_1.pos
arm_2.pos
arm_3.pos
arm_4.pos
arm_5.pos
gripper.pos
```

- `arm_0.pos` 至 `arm_5.pos` 的单位为弧度；
- `gripper.pos` 为归一化值，`0` 表示闭合，`1` 表示张开；
- `observation.state` 和 `action` 都使用同一顺序和单位；
- GALAXEA SDK 内部的夹爪原始弧度只存在于硬件边界，不写入数据集。

### 5.2 图像

默认数据集图像特征为：

```text
observation.images.top_rgb:   uint8, (480, 640, 3)
observation.images.wrist_rgb: uint8, (480, 640, 3)
```

颜色顺序是 RGB。数据集 FPS 为 30。关闭深度流，不创建深度特征。

### 5.3 实际动作入库

数据集中的 `action` 必须是 Robot 完成有限值校验、EMA、单步增量限制、关节硬限位和
夹爪限位后实际发送的七维动作。

当前 LeRobot 录制循环保存的是处理后的 Teleoperator 动作，而没有使用
`Robot.send_action()` 的返回值。单臂录制入口需要通过局部、可测试的方式确保实际下发
动作被写入数据集；不得为此改变所有上游 Robot 的全局录制语义。

## 6. 控制与安全

### 6.1 限制顺序

每一帧动作按以下顺序处理：

1. 检查七个键完整且值均为有限数；
2. 按上一次实际动作执行 EMA；
3. 对 J1–J6 执行逐帧最大变化量限制；
4. 按 GALAXEA-A1Z SDK 的六轴物理范围裁剪；
5. 将夹爪裁剪到 `[0,1]`；
6. 向 SDK 发送动作；
7. 返回并记录实际动作。

初次连接后，上一帧动作初始化为 A1Z 当前状态，防止第一帧跳变。

### 6.2 故障行为

以下情况在发送新 CAN 目标前失败：

- 动作缺键或包含非有限值；
- 配置数组不是六项；
- 相机键重复或配置无效；
- checkpoint 的状态、动作或相机特征与实机配置不一致。

相机断流、示教器断连或控制循环异常时停止本轮控制并进入清理：

- 停止 A1Z SDK 控制环并失能；
- 断开已连接相机；
- 断开示教器；
- 保留已经完整保存的 episode；
- 默认不移动机械臂回零。

## 7. ACT 训练与推理

ACT 使用 LeRobot 原生策略实现。单臂适配不复制或修改 ACT 网络。

默认训练建议：

- `policy.type=act`
- `policy.device=cuda`
- `batch_size=8`
- 数据输入为七维状态、七维动作和两路 RGB；
- 若 RTX 4060 显存不足，仅通过参数把 batch size 降为 4，不改变数据契约。

训练、验证和 rollout 使用完全相同的图像键和七维顺序。rollout 在连接硬件前读取
checkpoint 元数据并检查：

- 动作维度为 7；
- 状态维度为 7；
- 相机键和图像形状与配置一致；
- 策略类型可由 LeRobot 加载；
- 推理设备可用。

## 8. 验收标准

### 8.1 自动化验收

1. `a1z_single` 和 `a1z_leader` 可被配置解析器注册并从命令行构造。
2. Robot 的状态和动作严格为七维，并保持规定顺序和键名。
3. Teleoperator 转换公式在比例、正反方向和偏移组合下得到准确结果。
4. 缺键、多键、NaN 和 Inf 在硬件发送前产生明确错误。
5. 六轴目标不超过 GALAXEA-A1Z 的物理关节范围，夹爪始终位于 `[0,1]`。
6. `send_action()` 返回 EMA 和逐帧限幅后实际下发的动作。
7. 使用 0、1、2 个模拟相机时，观测特征数量和形状与配置一致。
8. 默认 D435/D405 配置均解析为 RGB、640×480、30 FPS、无深度。
9. 最小模拟数据集可由 `LeRobotDataset` 重新加载，episode 数、frame 数、FPS、任务、
   状态、动作和图像特征一致。
10. ACT 可基于模拟数据完成至少一次前向和反向训练步。
11. rollout 对匹配的 checkpoint 通过预检，对错误动作维度、缺失相机键或错误图像
    形状在连接 Robot 前失败。
12. 新增测试、现有 A1Z 相关测试、模块导入和所有新增 CLI 的 `--help` 均通过。

### 8.2 实机验收

1. 示教臂逐轴活动时，读取结果只改变对应的 A1Z 目标轴，ID 7 只改变夹爪。
2. 在低速和急停可用条件下，A1Z 六轴逐轴跟随的方向、零位和限位正确。
3. 夹爪开闭方向正确，目标和反馈均为 `[0,1]`。
4. D435 和 D405 连续采集 10 分钟，输出始终为 RGB 640×480，且没有设备串位。
5. 至少录制三个 episode；重新加载并可视化后，状态、实际动作、顶部 RGB 和手腕 RGB
   时间同步且内容正确。
6. 使用所录数据完成 ACT 冒烟训练并保存可重新加载的 checkpoint。
7. ACT 实机 rollout 在低速、空工作区和急停可用条件下运行，首帧无关节跳变，连续动作
   满足逐帧限制。

自动化验收不替代实机验收。没有连接实际硬件时，只报告软件验证结果，不声称实机可用。

## 9. 兼容性与修改范围

- 保留现有 `a1z` 双臂类型、14D 顺序、三个 RGB 相机示例和 rollout；
- 不修改用户已有的 `CLAUDE.md`；
- 不把本地七轴硬件定义写入 LeRobot 上游标准 `so101_leader`；
- 优先在 `a1z_lerobot` 中新增文件，只有确认存在通用缺陷时才修改 LeRobot 或
  GALAXEA-A1Z 子目录；
- 纯 Python 逻辑必须可在无 CAN、无串口、无 RealSense 的环境中测试；
- 实机测试命令由操作者在确认工作空间、急停和硬件连接安全后执行。
