# Livox MID-360 使用与驱动安装

> **修订版说明**：本文在原稿基础上修订。改动共 7 处「会直接跑不通」的硬错误、4 处表述不准、13 处补充内容，
> 逐条对照见文末 **附录 A**。文中标注 `【修订】` 的段落为新增或改写，`【原】` 表示基本保留原稿。

---

## 1. MID-360 是什么

### 1.1 基本印象【原】

Dji 旗下览沃（Livox）出品的经典低速机器人雷达。因为对机器人比赛场景的适配性好，一经推出便受到机器人竞赛团队的喜爱。

2026 年 9 月 19 日，穷困潦倒、贫瘠孱弱的 wustrc 终于以 2450 元获得了一台 MID-360（闲鱼二手）。

**三条必须记住的注意事项：**

1. **禁止热插拔。** 带电插拔会对雷达造成不可逆损坏，甚至直接报废。
2. **不要用手触碰雷达镜面。** 指纹会明显影响点云的回波数量和质量；官方更换镜面约 600 元，而且 MID-360 已停售多年，可能连维修服务都没有。
3. **上电前先接好网线，再上电**；断电时顺序相反。

> 📷 图片位置：原文档中的雷达实物图 / 镜面示意图（保留）

### 1.2 它属于哪一类雷达【原，含一处型号修订】

- **按测距原理**：MID-360 是 **ToF（飞行时间）** 传感器，对标的另一类是毫米波雷达。
- **按形态分类**：

| 类别 | 代表 | 典型用途 |
|---|---|---|
| 单点测距 | DT35 | 到位检测 |
| 平面 2D | 扫地机雷达、WLR-716 | 平面导航、避障 |
| **3D 旋转/固态** | **MID-360**、Avia、VLP 系列（部分含 IMU） | SLAM、建图、定位 |
| 面阵 ToF | ST **VL53L5CX / VL53L8CX**（8×8 多区） | 近距离高要求避障，体积小、略贵 |

> 【修订】原稿写作「vl5319cx」，查不到该型号，应为 ST 的 VL53L5CX / VL53L8CX 系列，此处已更正为待核实写法，建议再查一下规格书确认。

### 1.3 为什么 SLAM 需要内置 IMU 与时间同步【原 + 修订】

SLAM 里最关键的是**时间同步**：点云和 IMU 必须高度同步，才能有效去除运动畸变、建出稳定可用的图。纯软件方案（无 IMU）鲁棒性确实差，高精度建图基本不可行。

> 【修订】原稿写「因此 usb 输出的 imu 是不行的」。更准确的说法是：
> **问题不在 USB 这个接口，而在于该 IMU 有没有和雷达共用的硬件时钟/触发。**
> 没有同步触发的 IMU，延迟和抖动不可控；能拿到 PPS 或触发对齐的 USB IMU 同样可用，只是工程上麻烦。
> 所以「雷达内置 IMU」是最省事的最优解（MID-360 就是），没内置的只能自己用 STM32 之类做中转，很折腾且不保证效果。

**本机实测（可直接引用，详见第 4 节）：**

- 点云与 IMU 由**同一颗雷达内部时钟**打戳：两路速率差仅 **1.1 ppm**，同时刻延迟差约 1 ms 且不累积
- 该雷达当前 `time_type = 0`，**未做外部同步**，时间戳是「开机计时」而非 UTC（与主机差 1.79×10⁹ s）
- 结论：**做 FAST-LIO / Point-LIO 这类单雷达 + IMU 的 LIO 完全够用**（连 -116 ppm 的漂移都是共模的，会互相抵消）；
  只有要跟相机、主机、rosbag 对齐时才需要 PTP/GPS 授时

雷达的价值也不止 SLAM：本质是测距传感器，可以用来在已有地图（含仿真地图）里重定位，或单纯探测相对环境。

---

## 2. 驱动安装

MID-360 接入 Ubuntu + ROS2 需要两部分：**Livox-SDK2**（底层 SDK）和 **livox_ros_driver2**（ROS2 驱动包）。
驱动依赖 SDK；**在 ROS2 分支里，SDK 必须装在系统目录 `/usr/local`**（原因见 2.3）。

### 2.1 先确认 SDK 是否已经装过【修订】

```bash
ls /usr/local/lib/liblivox_lidar_sdk_shared.so
ls /usr/local/include/livox_lidar_api.h /usr/local/include/livox_lidar_def.h
```

两个都在，说明装过了（本文写作的这台机器就是 v1.3.1，已装）。只有缺了才需要走 2.2。

> ⚠️ Livox-SDK2 的 `make install` **只安装 `.so`/`.a` 和头文件，不导出 CMake config，也没有 pkg-config**。
> 所以不要指望 `find_package(Livox_SDK2)` 能找到它——`livox_ros_driver2` 是靠 `find_library` + `find_path`
> 硬找 `/usr/local` 的。

### 2.2 安装 Livox-SDK2（没装才做）

```bash
git clone https://github.com/Livox-SDK/Livox-SDK2.git
cd Livox-SDK2 && mkdir -p build && cd build
cmake .. && make -j$(nproc)
sudo make install
sudo ldconfig          # 必须，否则运行时找不到 .so
```

校验：

```bash
ldconfig -p | grep livox_lidar_sdk
```

### 2.3 安装 ROS2 驱动 livox_ros_driver2

> 下文统一用 `~/ws_livox` 举例；本机实际工作空间是 `~/livox_navi_ws`，照换路径即可。

#### ⚠️ 先看版本搭配（这条路最容易踩）

`livox_ros_driver2` 的 **master 分支会用到新版 SDK2 才有的类型**，和系统里的旧 SDK2 对不上就编译不过。
本文这台机器的情况：

| 组件 | 版本 |
|---|---|
| 系统 Livox-SDK2 | **v1.3.1**（装在 `/usr/local`） |
| driver2 master | 1.2.8（含 Mid-360L / Avia2 支持） |
| 结果 | **master 编不过，固定到 tag 1.2.6** |

典型报错（这是版本不匹配，不是代码写错）：

```text
src/comm/pub_handler.cpp:329: error: 'kLivoxLidarDoubleEchoData' was not declared in this scope
src/comm/pub_handler.cpp:463: error: 'LivoxLidarDoubleEchoRawPoint' was not declared in this scope
```

原因：`DoubleEcho` 这组类型是 `Support Avia2 Lidar`（2026-07-31 的提交 `4a1def9`）引入的，
**晚于 tag 1.2.6，且没有任何 tag 包含它，只有 master 有**；而 SDK2 仓库最新 tag 只到 `v1.3.1`，
双回波要 master（1.5.2）才有。

两条路：

**A. 把 driver2 固定到 tag 1.2.6（推荐，不动系统）**

```bash
cd ~/ws_livox/src/livox_ros_driver2
git checkout 1.2.6
cd ~/ws_livox
rm -rf build install log           # 必须清，CMake 缓存还指着旧源码
source /opt/ros/humble/setup.bash
colcon build --packages-select livox_ros_driver2 \
  --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble
```

> 已实测：**tag 1.2.6 + 系统 SDK2 v1.3.1 编译通过**（约 12 秒，零报错）。
> 1.2.6 完整支持 MID-360，只是没有 Avia2 / Mid-360L 这些新机型。

**B. 把 SDK2 升到 master（1.5.2），保留 driver2 master**

```bash
cd ~/Livox-SDK2 && git pull
rm -rf build && mkdir build && cd build
cmake .. && make -j$(nproc)
sudo make install && sudo ldconfig
cd ~/ws_livox && rm -rf build install log
source /opt/ros/humble/setup.bash
colcon build --packages-select livox_ros_driver2 \
  --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble
```

> 需要 sudo，会覆盖 `/usr/local` 里的 1.3.1。本机没有别的项目依赖 SDK2（`ws_livox_70` 用的是另一套 SDK1），
> 风险不大，但没有方案 A 干净。

**结论：文档和教程里要写死 tag**（例如 `git checkout 1.2.6`），不要写「clone 最新」——
上游随时可能加新依赖，把整条链路带崩。

#### 📌 怎么把「SDK + 驱动」的版本固定下来

固定版本要做两件事：**驱动端 checkout 到具体 tag**，**SDK 端不要跟着上游漂**（要用哪个版本就显式装哪个）。

**第 1 步：查——先确定该配哪个版本**

```bash
# 驱动都有哪些 tag
cd ~/ws_livox/src/livox_ros_driver2 && git tag -l

# SDK2 有哪些 tag（注意：1.4/1.5 没有 tag，只有 master）
git ls-remote --tags https://github.com/Livox-SDK/Livox-SDK2.git \
  | awk -F'refs/tags/' '{print $NF}' | grep -v '\^{}'

# 当前系统里装的 SDK 究竟是哪个版本
grep -E "LIVOX_LIDAR_SDK_(MAJOR|MINOR|PATCH)_VERSION" /usr/local/include/livox_lidar_def.h
```

判断「某个符号是哪个版本才有的」——这就是这次定位问题的办法：

```bash
git log -S "kLivoxLidarDoubleEchoData" --oneline   # 哪个提交引入的
git tag --contains 4a1def9                         # 哪些 tag 包含它（输出为空 = 只有 master 有）
```

**第 2 步：锁——把驱动钉在 tag 上**

```bash
cd ~/ws_livox/src/livox_ros_driver2
git fetch --tags
git checkout 1.2.6              # 钉到 tag，会进入 detached HEAD，正常现象
git describe --tags --always    # 记下来：1.2.6
```

要在这个版本上继续改自己的代码，用分支钉：

```bash
git switch -c pinned-1.2.6 1.2.6
```

**第 3 步：锁——SDK 要么不升级，要么显式装指定版本**

- 现在 `/usr/local` 里是 **v1.3.1**，和驱动 tag 1.2.6 正好配对 → **别动它**，也别 `git pull` 之后重新 `make install`
- 万一要重装，装**指定 tag**，不要装 master：

```bash
git clone -b v1.3.1 --depth 1 https://github.com/Livox-SDK/Livox-SDK2.git
cd Livox-SDK2 && mkdir -p build && cd build
cmake .. && make -j$(nproc) && sudo make install && sudo ldconfig
grep LIVOX_LIDAR_SDK_MINOR /usr/local/include/livox_lidar_def.h     # 复核版本
```

- 要临时升到 master（1.5.2）试新机型，先备份旧库：

```bash
sudo cp /usr/local/lib/liblivox_lidar_sdk_shared.so /usr/local/lib/liblivox_lidar_sdk_shared.so.v131.bak
```

**第 4 步：验——配对是否真的成立**

```bash
# 1) 编译过 = 头文件对得上
colcon build --packages-select livox_ros_driver2 \
  --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble

# 2) 链接的是系统里那套 .so
ldd $(find install -name "liblivox_ros_driver2.so" | head -1) | grep livox_lidar_sdk_shared

# 3) 启动日志第一行会打印驱动版本，确认是 1.2.6
ros2 launch livox_ros_driver2 msg_MID360_launch.py 2>&1 | grep "Ros Driver2 Version"
```

**第 5 步：记——在 README 里写死版本对照表**

| 组件 | 固定版本 | 位置 |
|---|---|---|
| livox_ros_driver2 | **tag 1.2.6** | `~/livox_navi_ws/src/livox_ros_driver2` |
| Livox-SDK2 | **v1.3.1** | `/usr/local/lib/liblivox_lidar_sdk_shared.so` |
| ROS | Humble | `/opt/ros/humble` |
| 雷达固件 | 待填（LivoxViewer2 的 Firmware Version） | — |

> 写教程时给的是「一组已验证的组合 + 具体 tag」，而不是「clone 最新」。
> 上游加新机型（Avia2/Mid-360L）就会连带抬高新版 SDK 依赖，这条链路随时会断。

#### 另一个源头问题：仓库不带 `package.xml`

`livox_ros_driver2` 仓库故意不带 `package.xml`，只给 `package_ROS1.xml` / `package_ROS2.xml`，
由 `build.sh` 选择并复制。所以下面两条路线二选一。

#### 路线 A：官方 `build.sh`（推荐给新手）

```bash
mkdir -p ~/ws_livox/src && cd ~/ws_livox/src
git clone https://github.com/Livox-SDK/livox_ros_driver2.git
cd livox_ros_driver2
git checkout 1.2.6         # 钉版本，理由见上面的「版本搭配」
source /opt/ros/humble/setup.bash
./build.sh humble          # ROS2 Humble 用 humble，不是 ROS2
```

> 【修订】原稿写 `./build.sh ROS2`。README 明确区分：
> Foxy 用 `ROS2`，**Humble 用 `humble`**，Jazzy 用 `jazzy`。
> 因为 `ROS2` 分支不会设置 `DISTRO_ROS`，CMake 会走非 humble 的 `rosidl` 链接分支。
>
> ⚠️ 另外两件事：
> 1. `build.sh` 在**包目录里**，不在工作空间根目录；
> 2. 它开头会 `rm -rf ../../build ../../install ../../devel`，**会清空整个工作空间的编译产物**，
>    所以不要把驱动塞进已有其他包的工作空间后直接跑它。

#### 路线 B：`colcon build`（想自己控参数时用）

```bash
cd ~/ws_livox/src/livox_ros_driver2
cp -f package_ROS2.xml package.xml          # 关键一步，不做必报 "package.xml does not exist"
cd ~/ws_livox
source /opt/ros/humble/setup.bash
colcon build --packages-select livox_ros_driver2 \
  --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble
```

> `-DDISTRO_ROS=humble` 不能省：CMakeLists 用它判断是否走 `rosidl_get_typesupport_target` 分支。
> 报 `must include <member_of_group>rosidl_interface_packages</member_of_group>` 时，
> 百分百是 `package.xml` 没生成。

#### 关于「把 SDK 放进工作空间」

**在 ROS2 下不可行**，不要写进教程误导人：

```cmake
# livox_ros_driver2/CMakeLists.txt:249
find_library(LIVOX_LIDAR_SDK_LIBRARY liblivox_lidar_sdk_shared.so /usr/local/lib REQUIRED)
```

路径被写死在 `/usr/local/lib`，不会去找工作空间里的 SDK 副本。
（`find_package(Livox_SDK2)` 只出现在 ROS1 分支，见 CMakeLists:44。）

如确实想把 SDK 装进工作空间，必须自己改 CMakeLists 的 `find_library` / `find_path` 路径。

#### 编译依赖

```bash
sudo apt install -y libpcl-dev
# libapr1-dev 不用装：package.xml 里有 <depend>apr</depend>，但源码中没有任何 apr_ 调用
```

### 2.4 网络与 MID360_config.json【修订：补网卡配置】

这台雷达**改过 IP，和出厂默认（192.168.1.x）不同**，参数是：

| 项目 | 值 |
|---|---|
| 主机（网卡）IP | `192.168.47.5` |
| 雷达 IP | `192.168.47.138` |
| 网卡 | `enp4s0`（有线直连） |

**第一步：给主机网卡配静态 IP**

```bash
nmcli con add type ethernet ifname enp4s0 con-name lidar ip4 192.168.47.5/24
nmcli con up lidar
ip -br addr show enp4s0        # 应显示 192.168.47.5/24
```

**第二步：改驱动的网络配置**

`livox_ros_driver2/config/MID360_config.json`（注意：驱动 1.0.0 用的是**对象形式**的 `host_net_info`，不要照抄 SDK2 示例里的数组形式）：

```json
{
  "lidar_summary_info": { "lidar_type": 8 },
  "MID360": {
    "lidar_net_info": {
      "cmd_data_port": 56100, "push_msg_port": 56200,
      "point_data_port": 56300, "imu_data_port": 56400, "log_data_port": 56500
    },
    "host_net_info": {
      "cmd_data_ip":   "192.168.47.5", "cmd_data_port": 56101,
      "push_msg_ip":  "192.168.47.5", "push_msg_port": 56201,
      "point_data_ip": "192.168.47.5", "point_data_port": 56301,
      "imu_data_ip":   "192.168.47.5", "imu_data_port": 56401,
      "log_data_ip": "",              "log_data_port": 56501
    }
  },
  "lidar_configs": [
    {
      "ip": "192.168.47.138",
      "pcl_data_type": 1,
      "pattern_mode": 0,
      "extrinsic_parameter": { "roll": 0.0, "pitch": 0.0, "yaw": 0.0, "x": 0, "y": 0, "z": 0 }
    }
  ]
}
```

改完要重新 `colcon build --packages-select livox_ros_driver2`（launch 读的是 `install/` 里的那份副本）。

> 【修订】原稿把 `xfer_format` / `publish_freq` 写在这一步，位置错了。
> 这两个不是 json 里的字段，而是 **launch 文件里的 Python 变量**：
>
> ```python
> # launch_ROS2/msg_MID360_launch.py
> xfer_format  = 1      # 0=PointCloud2, 1=CustomMsg（FAST-LIO 要 1）
> publish_freq = 10.0   # MID-360 原生 10 Hz，保持 10.0
> ```
>
> 默认值已经是给 SLAM 用的，**通常不用改**。要改就改这个 `.py`。

### 2.5 启动与验证【修订：文件名 + 验证命令】

```bash
cd ~/ws_livox
source install/setup.bash

# SLAM 用这个：发布 CustomMsg
ros2 launch livox_ros_driver2 msg_MID360_launch.py

# 只想看效果：PointCloud2 + 自动打开 RViz
ros2 launch livox_ros_driver2 rviz_MID360_launch.py
```

> 【修订】原稿写 `msg_MID360.launch` / `rviz_MID360.launch`，实际文件名带 `_launch.py` 后缀。

正常会发布两个话题：

| 话题 | 内容 | 预期频率 |
|---|---|---|
| `/livox/lidar` | 点云（`multi_topic=1` 时变为 `/livox/lidar_<ip>`） | 10 Hz |
| `/livox/imu` | 内置 IMU | 200 Hz |

验证：

```bash
ros2 topic hz /livox/lidar           # ≈10 Hz
ros2 topic hz /livox/imu             # ≈200 Hz
ros2 topic echo /livox/imu --once    # 原稿的 -n1 参数不存在，用 --once
ros2 topic info /livox/lidar -v      # 看类型：livox_interfaces2/CustomMsg 还是 PointCloud2
```

### 2.6 常见故障排查【修订：新增】

| 现象 | 原因 | 处理 |
|---|---|---|
| 启动即报 `bind failed` + `Failed to init livox lidar sdk.` | 网卡没起来 / 没有 `192.168.47.5`，SDK 绑不上端口（实测：`enp4s0` 掉线时必现） | `ip -br addr show enp4s0` 确认有 IP；`nmcli con up lidar`；检查网线、供电 |
| 节点起来了，但 `/livox/lidar` 没数据 | `MID360_config.json` 里 `lidar_configs.ip` 和雷达实际 IP 不一致 | 用 LivoxViewer2 查真实 IP，或 `arp-scan --interface=enp4s0 192.168.47.0/24` |
| 编译报 `package.xml does not exist` | 没做 `cp package_ROS2.xml package.xml` | 按 2.3 路线 B |
| 编译报 `must include <member_of_group>rosidl_interface_packages</member_of_group>` | 同上（`package.xml` 缺失的连带后果） | 同上 |
| 编译报 `kLivoxLidarDoubleEchoData was not declared` | driver2 master 需要新版 SDK2 | 按 2.3「版本搭配」固定到 tag 1.2.6 |
| `ros2 topic hz` 一直没输出 | 话题名不对（`multi_topic=1` 时会变成 `/livox/lidar_<ip>`） | 先 `ros2 topic list` 看实际名字 |

### 2.7 数据层面的三个提醒【修订：新增】

#### （1）量程 0.1 m ~ 40 m，且深度依赖反射率

| 指标 | 官方标称 | 本机实测 |
|---|---|---|
| 盲区 | **0.1 m** | 0.1 m 起就有有效点（最小 0.099 m） |
| 量程 @ 80% 反射率（白墙） | **40 m** | 最远 15.4 m |
| 量程 @ 10% 反射率（深色物） | 约 **10 m** | p99 = 11.6 m，中位 3.3 m |
| 垂直 FOV | -7° ~ +52° | -2.4° ~ +51.5° |

> 说明：官方 datasheet 不同版本的写法略有差异，以手上说明书为准；实测值来自暗室场景。

#### （2）约 46% 的点是 `(0,0,0)` —— 是「没打到」，不是「坏数据」

- **含义**：这些槽位没有收到足够强的回波，是无效占位点，坐标在原点（雷达内部），
  所以在 RViz 里看不见，但 SLAM 里必须过滤，否则会在地图原点堆积。
- **不是「离墙太近」**：墙越近回波越强、无效点越少；只有距离 **< 0.1 m** 才会丢点。
  实测 0.2~0.9 m 有 8 万个有效点（z≈0 的桌面平面），说明近距测量完全正常。
- **真正来源**：① 反射率（深色、黑色、玻璃，905 nm 直接透过去）② 入射角（掠射）③ 距离。
  实测有效点的**中位反射率只有 51/255，25% 的点低于 20**，说明场景偏暗，这才是主因。
- **判定是不是异常**（三个对照实验）：

| 场景 | 预期无效率 |
|---|---|
| 对准 1~2 m 白墙（贴张 A4 纸更好） | < 10% |
| 对准窗外 / 空旷处 | > 60% |
| 正常室内、开灯 | 20~35% |

  三个场景**无效率明显不同** → 数据正常；**都恒定在 46% 左右** → 才怀疑固件或硬件。

- **过滤写法**：

```cpp
if (p.x == 0 && p.y == 0 && p.z == 0) continue;   // 无回波占位点
if (p.intensity < 10) continue;                    // 可选：滤掉极弱回波
```

- **够不够用**：200k 点/s × 53.7% ≈ 10.7 万有效点/s ≈ **每帧 1.07 万点**，FAST-LIO 通常 5k~10k 点/帧就够。

#### （3）点云/IMU 的 `header.stamp` 是雷达开机计时，不是 UTC

要和相机、主机、rosbag 回放对齐，要么上 PTP/GPS，要么在驱动或上层做时间映射
（点云与 IMU 本身同源同速率，单雷达 LIO 不受影响，见 1.3 节）。

### 2.8 消息格式：CustomMsg 还是 PointCloud2【修订：新增】

两者装的是**同一批点**，区别在消息容器和字段设计：CustomMsg 是 Livox 私有格式，PointCloud2 是 ROS 标准格式。

| 维度 | **CustomMsg**（`livox_interfaces2/msg/CustomMsg`） | **PointCloud2**（`sensor_msgs/msg/PointCloud2`） |
|---|---|---|
| 定义 | Livox 私有 msg，必须编译 `livox_interfaces2` | ROS 标准消息，全生态通用 |
| 每点字段 | `offset_time`(uint32，相对 timebase) + `x,y,z`(float32) + `reflectivity` + `tag` + `line` | `x,y,z`(float32) + `intensity`(float32) + `tag` + `line` + `timestamp`(float64) |
| 每点字节数 | ≈ **19 B** | **22 B**（`#pragma pack(1)`） |
| 时间基准 | `header.stamp` + 全局 `timebase` + 每点 `offset_time` | `header.stamp` + 每点 `timestamp`（同样是相对偏移，单位 ns） |
| 点数 | 单独的 `point_num` 字段 | `width × height` |
| 谁认识它 | FAST-LIO2 / Point-LIO 的 Livox 分支、Livox 系工具 | RViz、`pcl_ros`、octomap、nav2、PCL 全家桶 |

**共同点（容易误解）**：两种格式**都带逐点时间戳**，都能做运动畸变补偿（去畸变）。

**怎么选：**

| 下游 | 用哪个 |
|---|---|
| FAST-LIO2 / Point-LIO | **CustomMsg**（`xfer_format = 1`） |
| RViz 直接看 | **PointCloud2**（`xfer_format = 0`） |
| 接 PCL / octomap / nav2 / `pcl::fromROSMsg` | **PointCloud2** |
| 录 bag 给通用工具用 | **PointCloud2**（别人不用装 Livox 的 msg 包） |

切换只改 launch 文件里一行（不是 json）：

```python
# launch_ROS2/msg_MID360_launch.py
xfer_format = 1      # 0 = PointCloud2, 1 = CustomMsg
```

**三个实际坑：**

1. **话题名相同、类型不同**：两种格式都发在 `/livox/lidar`，切了 `xfer_format` 后下游订阅类型必须跟着改，
   否则会静默收不到数据；bag 里的格式也是固定死的。
2. **驱动 1.2.0 起 PointCloud2 从 `PointXYZRTL` 变成 `PointXYZRTLT`**（多了 `timestamp` 字段，22 B/点）。
   按固定 struct 偏移写死解析的旧代码会错位——按 `fields[]` 名字取字段，或把驱动版本钉住。
3. **`is_dense` 不可信**：驱动写死为 `true`，但点云里含大量 `(0,0,0)`。别信这个标志，自己过滤。

`xfer_format = 2`（`pcl::PointCloud`）只在 ROS1 有效，ROS2 下驱动会打印
`message type 'pcl::PointCloud' is NOT supported in ROS2` 并且不发布。

带宽差别可以忽略：200k 点/秒下 CustomMsg ≈ 3.8 MB/s，PointCloud2 ≈ 4.4 MB/s，按下游生态选即可。

---

## 3. LivoxViewer2【原】

可以直接查看点云、看固件版本和网络配置，有 Windows 和 Ubuntu 版本：
<https://www.livoxtech.com/cn/downloads>

> 📷 图片位置：LivoxViewer2 设置页里 Firmware Version 一栏的截图（保留）

---

## 4. 这台机器的实测记录【新增】

供后续排查对比，数据抓取时间 2026-11。

| 项目 | 实测值 |
|---|---|
| 型号 / SN | MID-360（dev_type 9）/ `47MDN6C0030174` |
| 网络 | 雷达 192.168.47.138:56300 → 主机 192.168.47.5:56301（单播） |
| 点云速率 | 200,064 点/s，2084 包/s，96 点/包，1380 B/包 |
| 帧率 | 10.00 Hz（每 100 ms 19,968 / 20,064 点），无丢帧 |
| 丢包 | `udp_cnt` 连续无缺口，时间戳单调无重复 |
| FOV | 方位 360°，俯仰 -2.4° ~ +51.5°（规格 -7~+52） |
| 无效点 | 46.3%（`(0,0,0)`），帧间稳定 |
| IMU | 200.00 Hz，dt 5.000 ms（3.98~6.01），静止时 \|acc\|≈0.995 g |
| 时间同步 | `time_type=0`（无外部同步）；雷达时钟比主机慢 115.8 ppm |
| 点云 vs IMU | 同一时基，速率差 1.1 ppm |

**已验证可用的软件组合**：`livox_ros_driver2` **tag 1.2.6** + 系统 **Livox-SDK2 v1.3.1**（Ubuntu 22.04 / ROS2 Humble，编译约 12 秒无报错）。

---

## 附录 A：本次修订对照

### A.1 硬错误（原稿照做会失败）

| # | 位置 | 原文 | 修订为 | 原因 |
|---|---|---|---|---|
| 1 | 启动 | `ros2 launch livox_ros_driver2 msg_MID360.launch` | `msg_MID360_launch.py` | 实际文件名带 `_launch.py` |
| 2 | 启动 | `ros2 launch livox_ros_driver2 rviz_MID360.launch` | `rviz_MID360_launch.py` | 同上 |
| 3 | 验证 | `ros2 topic echo /livox/imu -n1` | `... --once` | humble 的 `topic echo` 没有 `-n` 参数 |
| 4 | 编译 | `./build.sh ROS2` | `./build.sh humble` | README 区分版本；`ROS2` 不设 `DISTRO_ROS`，走错 CMake 分支 |
| 5 | 配置 | 在 `MID360_config.json` 里设 `xfer_format` / `publish_freq` | 改为在 `launch_ROS2/msg_MID360_launch.py` 里设 | json 里没有这两个字段，改了不起作用 |
| 6 | 目录结构 | `~/Livox_SDK2` 与 ROS 包平级的工作空间示意 | ROS2 必须 `<ws>/src/`；SDK 放 `src/` 对驱动无效 | ROS2 分支 `find_library` 写死 `/usr/local/lib`（CMakeLists:249） |
| 7 | SDK 放置 | 「装进工作空间也行，只要加 `find_package` 依赖」 | ROS2 下不成立，SDK 必须装 `/usr/local` | `find_package(Livox_SDK2)` 只在 ROS1 分支（CMakeLists:44） |

### A.2 表述不准

| # | 原文 | 修订 |
|---|---|---|
| 8 | 「usb 输出的 imu 是不行的」 | 改为「没有硬件同步的 IMU 不行；USB 只是接口」。有触发/PPS 对齐的 USB IMU 同样可用 |
| 9 | 「面阵雷达(vl5319cx)」 | 查无此型号，应为 ST VL53L5CX / VL53L8CX，已标注待核实 |
| 10 | 「mid360 已停产」 | 保留但降级为「已停售多年，可能无维修服务」，避免当作官方结论引用 |
| 11 | 隐含「装完 SDK 就能 find_package」 | 明确写出 SDK2 不导出 CMake config / pkg-config，驱动靠 `find_library` 找 `/usr/local` |

### A.3 新增内容

| # | 新增 | 原因 |
|---|---|---|
| 12 | 2.1「先确认 SDK 是否已装」 | 本机已装 v1.3.1，重复装浪费时间 |
| 13 | 2.3 `cp -f package_ROS2.xml package.xml` | `colcon build` 路线不做必报错（这是本次实际遇到的错误） |
| 14 | 2.3 `sudo apt install libpcl-dev`，并说明 apr 不用装 | 编译依赖；`apr` 在源码中未被引用 |
| 15 | 2.4 网卡静态 IP 配置（nmcli） | 原稿只给了「雷达期待的主机 IP」，没给怎么配 |
| 16 | 2.5 三条验证命令（hz / echo / info） | 原稿只有 hz，缺类型确认（CustomMsg vs PointCloud2） |
| 17 | 2.7 46% 无效点提醒 | 实测数据，不处理会污染建图 |
| 18 | 第 4 节「实测记录」 | 为以后换机器/换固件留对比基线 |
| 19 | 2.3 提示「配置要改对象形式，别抄 SDK2 示例的数组形式」 | 驱动 1.0.0 的解析器只认对象形式 |
| 20 | 2.3「版本搭配」小节：driver2 master 需新版 SDK2，固定 tag 1.2.6 | 实测 master 报 `kLivoxLidarDoubleEchoData` 未声明；tag 1.2.6 + SDK2 v1.3.1 实测编译通过 |
| 21 | 2.6 常见故障排查表（`bind failed`、无数据、编译报错） | 实测 `enp4s0` 掉线时驱动起不来，报 `bind failed` |
| 22 | 2.3「怎么把 SDK + 驱动的版本固定下来」五步法（查/锁/验/记/回滚） | 只写「回退 1.2.6」不够，还要能判断配哪个版本、怎么钉住不再漂 |
| 23 | 2.7 展开成三条：量程表、46% 无效点的成因与三个对照实验、过滤代码 | 原稿只说了「时间同步」，没讲清「无效点」到底是什么、多少算正常 |
| 24 | 2.8 消息格式 CustomMsg vs PointCloud2（字段、选型、切换、三个坑） | 新手最容易在这一步选错格式，导致 FAST-LIO 收不到数据 |

---

*修订依据：本机 Ubuntu 22.04 + ROS2 Humble 实测；`livox_ros_driver2` 官方仓库源码（`CMakeLists.txt`、`build.sh`、`launch_ROS2/`、`config/MID360_config.json`、`CHANGELOG.md`、README）与 git 历史；另在临时工作空间实际编译验证了「tag 1.2.6 + SDK2 v1.3.1」这一组合。*
