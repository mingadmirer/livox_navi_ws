import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory('spark_fast_lio'), 'config', 'mid360.yaml')

    return LaunchDescription([
        Node(
            package='spark_fast_lio',
            executable='spark_lio_mapping',
            name='spark_fast_lio_node',
            output='screen',
            parameters=[config],
            # 话题名在源码里是写死的相对名，这里 remap 到 livox_ros_driver2 的输出
            remappings=[
                ('lidar', '/livox/lidar'),
                ('imu', '/livox/imu'),
            ],
        ),
    ])
