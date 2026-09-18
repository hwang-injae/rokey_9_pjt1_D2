import rclpy, time
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from dsr_msgs2.srv import MoveJoint
rclpy.init(); n=Node('dsr_controller2', namespace='dsr01')
def cb(req,res):
    n.get_logger().info('fake movej 2s'); time.sleep(2.0); res.success=True; return res
n.create_service(MoveJoint,'/dsr01/dsr_controller2/motion/move_joint',cb,callback_group=ReentrantCallbackGroup())
ex=MultiThreadedExecutor(); ex.add_node(n); ex.spin()
