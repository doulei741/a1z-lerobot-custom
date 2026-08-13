# A1Z Web 人工实机 Smoke Test

自动测试永远使用 `A1Z_WEB_MOCK=1`。下面各步骤必须由现场操作者逐项完成；任何一步失败都停止，不跳过。

1. 打开设备发现，核对两条 Leader 串口及三个 RealSense 序列号。
2. 用 `ip -details link show can0` 与 `can1` 确认两接口均为 `UP / ERROR-ACTIVE / 1000000 bit/s`。
3. 在无 Follower 运动的流程中完成左右 Leader 只读/校准文件检查。
4. 使用现有只读诊断分别核对两条 Follower 状态，不同时占用运行任务的 CAN。
5. 核对左右 Leader MotorCalibration 文件与不同的 calibration id。
6. 将 Leader/Follower 放在相同安全姿态，读取并核对 Pairing Profile 的 sign、scale、offset。
7. 不启用相机，以 Safe preset 启动低速 Teleoperation。
8. 启动后静止 2–5 秒，确认没有姿态跳变或自行运动。
9. J1–J6 与夹爪逐轴小幅动作，确认轴序、方向、幅值与延迟。
10. 停止遥操后连接 D435、左右 D405，核对 health、640×480 RGB、30 FPS，并在 Rerun 查看。
11. 新建临时 Dataset，录制 5–10 秒；测试 Finish、Rerecord、Reset Done、Quick Next。
12. 检查 `meta/info.json`、parquet/video，确认双臂 state/action 为 14D，label 是 `send_action()` 返回的 actual action。
13. 在 Inference 页仅读取 checkpoint，确认全部 Compatibility 项通过，此时硬件尚未连接。
14. 准备初始姿态、物理急停和空工作区，以 Safe Test 执行 5–10 秒 ACT 推理。

软件停止不是工业物理急停。CAN 掉线、SDK emergency stop 或 RealSense critical timeout 后，必须人工确认硬件状态并重新初始化，不能直接继续下一 Episode。
