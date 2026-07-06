#!/bin/bash
# Setup SocketCAN for HHS CANFD Pro-II adapter.
# Run after each boot (or add to systemd service).

set -e

# Load gs_usb kernel module
sudo modprobe gs_usb

# Bind HHS adapter (VID:PID = a8fa:8598) to gs_usb driver
sudo sh -c 'echo "a8fa 8598" > /sys/bus/usb/drivers/gs_usb/new_id' 2>/dev/null || true

# Configure and bring up CAN interface
CAN_IF="${1:-can0}"
sudo ip link set "$CAN_IF" down 2>/dev/null || true
sudo ip link set "$CAN_IF" type can bitrate 1000000
sudo ip link set "$CAN_IF" txqueuelen 1000
sudo ip link set "$CAN_IF" up

echo "SocketCAN ($CAN_IF) ready. Verify with: candump $CAN_IF"
