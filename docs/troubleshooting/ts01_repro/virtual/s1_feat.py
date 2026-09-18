import sys, rclpy, threading, time
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from std_srvs.srv import Trigger
import DR_init
NAME=sys.argv[1]; J1=float(sys.argv[2])
rclpy.init(); DR_init.__dsr__id='dsr01'; DR_init.__dsr__model='m0609'
node=Node(NAME, namespace='dsr01'); dsr=Node(NAME+'_dsr', namespace='dsr01'); DR_init.__dsr__node=dsr
from DSR_ROBOT2 import movej, get_current_posj, set_robot_mode, ROBOT_MODE_AUTONOMOUS
lock=threading.Lock(); n=[0]
def cb(req,res):
    if not lock.acquire(blocking=False): res.success=False; res.message='BUSY'; return res
    try:
        n[0]+=1; t=time.time(); tgt=[J1 if n[0]%2 else 0.0,0.0,90.0,0.0,90.0,0.0]
        r=movej(tgt, vel=60, acc=60); p=get_current_posj()
        res.success=(r==0); res.message=f'{NAME} call#{n[0]} movej ret={r} {time.time()-t:.1f}s j1={p[0]:.1f}'
    finally: lock.release()
    return res
node.create_service(Trigger,f'/{NAME}/move',cb)
set_robot_mode(ROBOT_MODE_AUTONOMOUS)
ex=MultiThreadedExecutor(); ex.add_node(node); node.get_logger().info('ready'); ex.spin()
