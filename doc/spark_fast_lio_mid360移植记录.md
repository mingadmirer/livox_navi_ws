# spark-fast-lio 接入 Livox Mid-360 移植记录

> 目标：让 `MIT-SPARK/spark-fast-lio` 在 **ROS 2 Humble + Livox Mid-360** 上真正跑起来
> 结果：**已跑通**，`/cloud_registered` ≈ 10 Hz、`/path` ≈ 1 Hz
> 环境：Ubuntu 22.04 / ROS 2 Humble / GCC 11 / Livox-SDK2 v1.3.1 + livox_ros_driver2 tag 1.2.6

---

## 0. TL;DR

| 项 | 值 |
|---|---|
| 上游版本 | `MIT-SPARK/spark-fast-lio`，commit **`17b36d2`**（`git describe` = `v0.1.0-16-g17b36d2`，2026‑02‑17）|
| 代码改动 | **17 处**（CMake 2 + preprocess 6 + spark_fast_lio 8 + 头文件 1）|
| 新增文件 | `config/mid360.yaml`、`launch/mapping_mid360.launch.py` |
| 实测输出 | `/livox/lidar` 10.0 Hz、`/livox/imu` 200 Hz、**`/cloud_registered` 9.98 Hz**、`/path` 1.0 Hz |
| 补丁脚本 | `patch_spark_mid360.py`（幂等，可重复执行）|

---

## 1. 为什么"原生 ROS2"的包却跑不起来

这个仓库主体确实是 ROS 2（`rclcpp` / `ament_cmake` / `rclcpp_components`，**没有** `ros/ros.h`、`catkin`、`ros::NodeHandle`），
但 **Livox 这一支是 ROS1 时代的残留，只迁了一半**：

| 已迁到 ROS2（5 处） | 仍停留 ROS1（9 处） |
|---|---|
| `spark_fast_lio.cpp:97,393`、`spark_fast_lio.h:33,81,155` → `livox_ros_driver2::msg::CustomMsg` | `preprocess.h:13,91,108`、`preprocess.cpp:47,115` → `livox_ros_driver::CustomMsg` |
| | `CMakeLists.txt:85,103,105,108,111` → `find_package(livox_ros_driver)` |

**为什么上游没发现**：他们的数据集全是 Ouster / Velodyne（8 个 config 里没有 Livox；
`is_from_pilot_zone()` 只处理 `"ouster"` / `"velodyne"`，其它直接 `throw`），
Livox 分支默认关闭：`find_package(livox_ros_driver **QUIET**)` + `Missing livox driver! AVIA Lidar will be disabled!`。
**这套代码在启用 Livox 的情况下从来没被编译过**，所以一堆潜伏错误。

---

## 2. 问题清单（按严重程度）

| # | 位置 | 问题 | 后果 |
|---|---|---|---|
| 1 | `CMakeLists.txt:85` | `find_package(livox_ros_driver QUIET)` 用的是 **ROS1 包名** | 找不到 → `LIVOX_ROS_DRIVER_FOUND` 未定义 → Livox 代码整体被编译掉，**但编译能过** |
| 2 | `preprocess.h:13` | `#include <livox_ros_driver/CustomMsg.h>`（ROS1 头） | 启用 Livox 后编不过 |
| 3 | `preprocess.h:91,108`、`preprocess.cpp:47,115` | 类型名还是 `livox_ros_driver::CustomMsg`；且 `108` 声明 `ConstPtr` 与实现 `const&` **签名不一致** | 编不过 |
| 4 | `spark_fast_lio.cpp:391` | 宏名拼错：`LIVOXROS_DRIVER_FOUND`（少一个下划线） | **Livox 回调函数整体消失** → 链接期找不到 `livoxLiDARCallback` |
| 5 | `spark_fast_lio.cpp:100` | `std::bind(&SPARKFastLIO2::livoxLidarCallback...)` 与定义 `livoxLiDARCallback` **大小写不一致** | 编不过 |
| 6 | `spark_fast_lio.cpp:393` | 回调形参 `ConstSharedPtr`（shared_ptr），但 `process()` 收 `const&` | 编不过（需改成 `const&`，与 `standardLiDARCallback` 一致）|
| 7 | `spark_fast_lio.cpp:417` | `imu_buffer` 少写了下划线（成员是 `imu_buffer_`） | 编不过 |
| 8 | `spark_fast_lio.cpp:422` | `last_lidar_timestamp_.nanseconds()` 拼写错误 | 编不过 |
| 9 | `spark_fast_lio.cpp:91-101` | **同一个话题 `lidar` 上同时建 PointCloud2 和 CustomMsg 两个订阅** | 运行期直接抛异常：<br>`create_subscription() called for existing topic name rt/livox/lidar with incompatible type livox_ros_driver2::msg::dds_::CustomMsg_` → `invalid allocator` → 进程 abort |
| 10 | `preprocess.cpp:179` | `ROS_DEBUG(...)`（ROS2 没有这个宏） | 编不过 |

> #4、#7、#8、#10 都是典型的"这段代码从没被编译过"的证据。

---

## 3. 修改清单

### 3.1 CMake：换成 ROS2 驱动包 + 用 messages 的 typesupport target

```cmake
# 之前
find_package(livox_ros_driver QUIET)
...
if(livox_ros_driver_FOUND)
  target_link_libraries(spark_lio_component ${livox_ros_driver_LIBRARIES})
  target_include_directories(spark_lio_component PRIVATE ${livox_ros_driver_INCLUDE_DIRS})
  target_compile_definitions(spark_lio_component PRIVATE -DLIVOX_ROS_DRIVER_FOUND=${livox_ros_driver_FOUND})
else()
  message(STATUS "Missing livox driver! AVIA Lidar will be disabled!")
endif()

# 之后
find_package(livox_ros_driver2 QUIET)
...
if(livox_ros_driver2_FOUND)
  target_link_libraries(spark_lio_component
    livox_ros_driver2::livox_interfaces2__rosidl_typesupport_cpp)
  target_compile_definitions(spark_lio_component PRIVATE -DLIVOX_ROS_DRIVER_FOUND=1)
  message(STATUS "livox_ros_driver2 found: Livox (Mid-360/AVIA) support ENABLED")
else()
  message(STATUS "Missing livox_ros_driver2! Livox support DISABLED (PointCloud2 lidars only)")
endif()
```

> 只需要消息的 typesupport，不需要链接驱动本身的 `.so`。
> 目标名可在 `install/livox_ros_driver2/share/livox_ros_driver2/cmake/*.cmake` 里确认。

### 3.2 preprocess：类型与头文件换成 ROS2

```cpp
// include/preprocess.h
#include <livox_ros_driver2/msg/custom_msg.hpp>          // 原 <livox_ros_driver/CustomMsg.h>
void process(const livox_ros_driver2::msg::CustomMsg &msg, PointCloudXYZI::Ptr &pcl_out);
void avia_handler(const livox_ros_driver2::msg::CustomMsg &msg);   // 原 ...::ConstPtr &，与实现不一致

// src/preprocess.cpp
void Preprocess::process(const livox_ros_driver2::msg::CustomMsg &msg, ...)
void Preprocess::avia_handler(const livox_ros_driver2::msg::CustomMsg &msg)
// 第 179 行
RCLCPP_DEBUG(rclcpp::get_logger("Preprocess"), "Feature extraction time: %lf \n", time / count);
```

### 3.3 spark_fast_lio：修拼写 + 订阅二选一

```cpp
// 1) 宏名
#if defined(LIVOX_ROS_DRIVER_FOUND) && LIVOX_ROS_DRIVER_FOUND      // 原 LIVOXROS_DRIVER_FOUND

// 2) 回调签名（与 standardLiDARCallback 对齐）
void SPARKFastLIO2::livoxLiDARCallback(const livox_ros_driver2::msg::CustomMsg & msg) {

// 3) 绑定名字
std::bind(&SPARKFastLIO2::livoxLiDARCallback, this, std::placeholders::_1)   // 原 livoxLidarCallback

// 4) 订阅按 lidar_type 二选一（关键！同一话题不能有两种消息类型）
const int lidar_type_param =
    declare_parameter<int>("preprocess.lidar_type", static_cast<int>(AVIA));
...
if (lidar_type_param == static_cast<int>(AVIA)) {
  sub_lidar_livox_ = create_subscription<livox_ros_driver2::msg::CustomMsg>(
      "lidar", lidar_qos, std::bind(&SPARKFastLIO2::livoxLiDARCallback, this, std::placeholders::_1));
} else {
  sub_lidar_ = create_subscription<sensor_msgs::msg::PointCloud2>(
      "lidar", lidar_qos, std::bind(&SPARKFastLIO2::standardLiDARCallback, this, std::placeholders::_1));
}

// 5) 后面这行改成复用（参数只能声明一次）
preprocessor_->lidar_type = lidar_type_param;

// 6) 拼写
if (... && !imu_buffer_.empty()) { ... }
last_lidar_timestamp_.nanoseconds()
```

---

## 4. 新增文件

### 4.1 `config/mid360.yaml`

关键取值理由：

| 参数 | 值 | 理由 |
|---|---|---|
| `preprocess.lidar_type` | `1` | 1 = Livox（非重复扫描），同时决定建哪个订阅 |
| `preprocess.blind` | `0.1` | Mid-360 盲区 0.1 m |
| `preprocess.timestamp_unit` | `3`（ns） | CustomMsg 的 `offset_time` 单位是 ns |
| `mapping.det_range` | `60.0` | 有效量程约 40 m，留余量 |
| `mapping.fov_degree` | `360.0` | 水平全向 |
| `mapping.extrinsic_T/R` | `0,0,0` + 单位阵 | Mid-360 的 IMU 与雷达**同壳体**，外参用默认；雷达相对车体的安装角写 **TF**（`base_link → livox_frame`），不要塞这里 |
| `point_filter_num` | `3` | 200k 点/s 抽稀到约 66k/s |
| `common.visualization_frame` | **`imu`** | ⚠️ 代码只接受 `imu` / `lidar` / `base`，写错会抛 `Invalid visualization frame` |

### 4.2 `launch/mapping_mid360.launch.py`

源码里话题名是**写死的相对名** `lidar` / `imu`（不读 yaml 里的 `lid_topic`），所以必须 remap：

```python
Node(package='spark_fast_lio', executable='spark_lio_mapping',
     parameters=[config],
     remappings=[('lidar', '/livox/lidar'), ('imu', '/livox/imu')])
```

---

## 5. 验证

```bash
cd ~/livox_navi_ws && source install/setup.bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py      # 终端 1
ros2 launch spark_fast_lio mapping_mid360.launch.py     # 终端 2
```

实测：

| 话题 | 频率 |
|---|---|
| `/livox/lidar` | 10.007 Hz |
| `/livox/imu` | 200.153 Hz |
| **`/cloud_registered`** | **9.979 Hz** |
| `/path` | 1.000 Hz |

发布的话题：`/cloud_registered`、`/cloud_registered_lidar`、`/cloud_registered_body`、`/cloud_registered_base`、`/odometry`、`/path`。

**日志里这几条是正常的，不用管：**

| 日志 | 含义 |
|---|---|
| `Livox loopback, clearing buffers`（首帧一条） | 构造函数把 `last_lidar_timestamp_` 初始化成 `now()`，而雷达时间戳是开机计时 → 第一帧必然"倒退"一次 |
| `No point, skip this scan!`（IMU 初始化那一帧一条） | 该帧只做 IMU 初始化，不输出点云 |
| `Multi thread started` | 正常 |

---

## 6. 已知限制 / 后续

1. **首帧 loopback 警告**：`last_lidar_timestamp_(now())` 与雷达时间基不同源。若想消掉，把初始化改成 `rclcpp::Time(0, 0, RCL_ROS_TIME)`。
2. **话题名写死**：`lidar` / `imu`，只能靠 remap（已在 launch 里处理）。
3. **无外部时间同步**：雷达 `time_type=0`，`header.stamp` 是开机计时；本包 IMU 与点云同源，所以 LIO 不受影响，但 bag 不能直接和相机对齐。
4. **无回环检测**：长时间跑会累积漂移，需要回环请换 GLIM。
5. **输出坐标系**：点云发在 `map_frame: odom` 下；要看 `base_link` 需自行配 TF。
6. **未做性能测量**：未记录 CPU 占用与内存。

---

## 7. 从零复现

```bash
cd ~/livox_navi_ws/src
git clone https://github.com/MIT-SPARK/spark-fast-lio.git
python3 /path/to/patch_spark_mid360.py ~/livox_navi_ws/src/spark-fast-lio/spark_fast_lio
cd ~/livox_navi_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select spark_fast_lio --cmake-args -DCMAKE_BUILD_TYPE=Release
```

编译日志里应出现：

```
-- livox_ros_driver2 found: Livox (Mid-360/AVIA) support ENABLED
```

---

## 8. 排错备忘

| 现象 | 原因 | 处理 |
|---|---|---|
| 编译过了但没点云，日志 `Error LiDAR Type` | `LIVOX_ROS_DRIVER_FOUND` 没生效 | 看编译日志有没有 `support ENABLED`；没有就说明 `find_package` 没找到 |
| `invalid allocator` / `incompatible type ... CustomMsg_` | 同一话题建了两种消息类型的订阅 | 按 `lidar_type` 二选一（见 3.3）|
| `Invalid visualization frame` | `visualization_frame` 不是 `imu`/`lidar`/`base` | 改 yaml |
| `colcon build` 报重名 / 配置改了不生效 | 工作空间里有**重复包目录**（本次实际踩到：`config/spark-fast-lio/` 被误放进工作空间，colcon 当成第二个 `spark_fast_lio`，构建直接失败，`install/` 里的旧配置一直没更新）| `colcon list | grep <包名>` 确认只有一个路径 |
| `No point, skip this scan!` 持续出现 | 预处理没产出点（点全被过滤）或 IMU 未覆盖帧时间 | 打开 `publish.scan_publish_en` 看原始点；确认 `/livox/imu` 有 200 Hz |

---

## 附录：补丁脚本

`patch_spark_mid360.py`（同目录）：

```bash
python3 patch_spark_mid360.py <spark_fast_lio 包目录>
```

- 幂等：已应用的替换会 `[SKIP]`，可重复执行
- 会同时写出 `config/mid360.yaml` 与 `launch/mapping_mid360.launch.py`
- 找不到锚点时会 `[FAIL]` 并退出（避免静默改坏文件）

---

*记录时间：2026‑11‑09；上游版本 `17b36d2`；ROS 2 Humble / GCC 11 / Livox-SDK2 v1.3.1 / livox_ros_driver2 1.2.6*
