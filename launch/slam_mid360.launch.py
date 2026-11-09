"""一键启动：激光驱动 + SLAM + RViz。

用法:
    ros2 launch ~/livox_navi_ws/launch/slam_mid360.launch.py
    ros2 launch .../slam_mid360.launch.py rviz:=false
    ros2 launch .../slam_mid360.launch.py driver:=false     # 雷达已在别处启动
    ros2 launch .../slam_mid360.launch.py params:=/path/to/other.yaml

目录约定:
    ~/livox_navi_ws/launch/slam_mid360.launch.py     ← 启动文件
    ~/livox_navi_ws/config/slam/mid360_slam.yaml     ← SLAM 参数
    ~/livox_navi_ws/config/slam/mid360_map.rviz      ← RViz 配置
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.normpath(os.path.join(THIS_DIR, '..', 'config', 'slam'))


def generate_launch_description():
    params = LaunchConfiguration('params')
    use_rviz = LaunchConfiguration('rviz')
    use_driver = LaunchConfiguration('driver')

    driver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('livox_ros_driver2'),
            'launch_ROS2', 'msg_MID360_launch.py')),
        condition=IfCondition(use_driver))

    slam = Node(
        package='spark_fast_lio',
        executable='spark_lio_mapping',
        name='spark_fast_lio_node',
        output='screen',
        parameters=[params],
        # 源码里话题名是写死的相对名，必须 remap
        remappings=[('lidar', '/livox/lidar'), ('imu', '/livox/imu')])

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', os.path.join(CONFIG_DIR, 'mid360_map.rviz')],
        condition=IfCondition(use_rviz))

    return LaunchDescription([
        DeclareLaunchArgument('params', default_value=os.path.join(CONFIG_DIR, 'mid360_slam.yaml')),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('driver', default_value='true'),
        driver,
        slam,
        rviz,
    ])
