# A1Z Leader 独立校准命令设计

日期：2026-07-31

## 目标

提供可重复执行的 `a1z-calibrate-leader` 命令，替代临时 Python heredoc，用于单独校准
七轴 STS3215 Leader。该命令只操作串口上的 Leader，不构造 `a1z_single` Robot、不连接
CAN、不读取相机，也不向 A1Z 跟随臂发送动作。

## 命令接口

```bash
a1z-calibrate-leader --port=/dev/ttyACM0 --id=a1z_leader
```

- `--port` 必填，传给 `A1ZLeaderConfig`。
- `--id` 可选，默认 `a1z_leader`，用于 LeRobot 校准文件命名。
- 六轴 `joint_signs`、`joint_scales`、`joint_offsets_rad` 使用 `A1ZLeaderConfig` 的默认值；
  该命令仅校准舵机行程，不用于调整 A1Z 运动学映射。

## 行为与故障处理

命令构造 `A1ZLeader` 后调用 `connect()`。若没有校准，或操作者在已有校准提示中输入
`c`，复用既有交互式流程：中位对齐、记录 `arm_0..arm_4` 与夹爪行程，并将 `arm_5`
设为全圈。校准正常结束、用户中断或异常时，只要串口仍连接就调用 `disconnect()`。

该命令不绕过现有校准确认提示，不自动移动任何 Leader 关节。操作者必须确保 Leader
可安全手动活动；A1Z 的安全由未连接 Robot/CAN 的结构性边界保证。

## 验收标准

1. `--help` 可用并显示 `--port` 与 `--id`。
2. 使用替身 Leader 时，入口以命令行串口和 ID 构造配置，调用连接，并在结束时断开。
3. 无论校准流程抛出异常与否，已连接的 Leader 都会断开。
4. 回归测试不连接真实串口、CAN 或相机。
