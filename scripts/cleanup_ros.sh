#!/usr/bin/env bash
# 清理残留的 ROS 进程与 daemon 缓存
# 用法: bash ~/livox_navi_ws/scripts/cleanup_ros.sh
set +e
echo "=== 清理前 ==="
ps -eo pid,etime,cmd | grep -E "livox_ros_driver2_node|spark_lio_mapping|rviz2|ros2 launch" | grep -v grep

pkill -f livox_ros_driver2_node
pkill -f spark_lio_mapping
pkill -f "ros2 launch"
pkill -f rviz2
sleep 1

ros2 daemon stop  >/dev/null 2>&1
ros2 daemon start >/dev/null 2>&1
sleep 1

echo "=== 清理后：节点列表（应为空）==="
ros2 node list
echo "=== 清理后：话题列表 ==="
ros2 topic list | head -5
