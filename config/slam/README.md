# config/slam — Mid-360 建图可视化配置

| 路径 | 作用 |
|---|---|
| `~/livox_navi_ws/launch/slam_mid360.launch.py` | 一键启动：驱动 + SLAM + RViz（**启动文件统一放 `launch/`**）|
| `~/livox_navi_ws/config/slam/mid360_slam.yaml` | SLAM 参数（改这里，不要改 `src/` 里的副本）|
| `~/livox_navi_ws/config/slam/mid360_map.rviz` | RViz 配置：Fixed Frame=odom，地图/本体点云/轨迹/里程计/TF 都配好 |

## 用法

```bash
cd ~/livox_navi_ws && source install/setup.bash
ros2 launch ~/livox_navi_ws/launch/slam_mid360.launch.py
```

可关闭其中一部分：

```bash
ros2 launch ~/livox_navi_ws/launch/slam_mid360.launch.py rviz:=false      # 不弹 RViz
ros2 launch ~/livox_navi_ws/launch/slam_mid360.launch.py driver:=false    # 驱动已在别处启动
ros2 launch ~/livox_navi_ws/launch/slam_mid360.launch.py params:=/path/to/other.yaml
```

## RViz 里能看到什么

| Display | 话题 | 说明 |
|---|---|---|
| Map | `/cloud_registered` | 世界系点云，**Decay Time 设了 1000 s** 才能累积成一张图 |
| Body | `/cloud_registered_body` | 当前帧（IMU 系），看实时数据是否正常 |
| Path | `/path` | 轨迹 |
| Odometry | `/odometry` | 位姿 + 箭头 |
| TF | — | 坐标轴 |

> ⚠️ Fixed Frame 必须是 **`odom`**（对应 `common.map_frame`）。写成 `map` 会一直报 No transform。

## 建图结果存哪

代码里写死了 `ROOT_DIR + "PCD/scans_N.pcd"`，`ROOT_DIR` 是**源码目录**：

```
~/livox_navi_ws/src/spark-fast-lio/spark_fast_lio/PCD/scans_1.pcd
```

- **必须先建目录**：`mkdir -p ~/livox_navi_ws/src/spark-fast-lio/spark_fast_lio/PCD`
- `pcd_save.interval` 必须 **> 0**（`-1` 在这个 fork 里一个文件都不会生成）
- 每 `interval` 帧写一个文件；结束时不足 `interval` 的残留不会保存

看 pcd：

```bash
sudo apt install pcl-tools
pcl_viewer ~/livox_navi_ws/src/spark-fast-lio/spark_fast_lio/PCD/scans_1.pcd
```

## 消息类型

| 方向 | 话题 | 类型 |
|---|---|---|
| 输入 | `/livox/lidar` | `livox_ros_driver2/msg/CustomMsg`（驱动 `xfer_format=1`）|
| 输入 | `/livox/imu` | `sensor_msgs/Imu` |
| 输出 | `/cloud_registered` 等 | `sensor_msgs/PointCloud2` |

## 排错

| 现象 | 处理 |
|---|---|
| RViz 报 `No transform from [odom]` | Fixed Frame 写错，或 SLAM 还没收到第一帧 |
| 点云只有一片、没有累积 | 把 Map display 的 `Decay Time` 调大（当前 1000）|
| 日志 `Error LiDAR Type` | `preprocess.lidar_type` 不是 1，或编译时没启用 livox_ros_driver2 |
| 日志 `Invalid visualization frame` | `visualization_frame` 只能是 `imu`/`lidar`/`base` |
| `colcon build` 报包名重复 | **`config/` 和 `launch/` 里千万不要放 `CMakeLists.txt` / `package.xml`**，否则 colcon 会当成第二个包（已踩过）|

## 编译

```bash
colcon build --packages-select spark_fast_lio livox_ros_driver2 \
  --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_BUILD_TYPE=Release
```
