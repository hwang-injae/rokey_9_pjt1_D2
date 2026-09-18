import sys, rclpy, DR_init, time
from rclpy.node import Node
from std_srvs.srv import Trigger
MODE=sys.argv[1]
rclpy.init(); DR_init.__dsr__id='dsr01'; DR_init.__dsr__model='m0609'
node=Node('cls_'+MODE, namespace='dsr01'); DR_init.__dsr__node=node
from DSR_ROBOT2 import CDsrRobot
robot=CDsrRobot('dsr01','m0609')
print('movej client 서비스 이름:', robot._ros2_movej.srv_name, flush=True)
if MODE=='script':
    t=time.time(); r=robot.movej([0.0]*6, vel=30, acc=30); print('script movej ret',r,f'{time.time()-t:.1f}s',flush=True)
else:
    def cb(q,res):
        r=robot.movej([0.0]*6, vel=30, acc=30); res.success=True; res.message=f'ret={r}'; return res
    node.create_service(Trigger,'/test/cls',cb); rclpy.spin(node)
