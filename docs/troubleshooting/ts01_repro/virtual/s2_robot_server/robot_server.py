# 구조 ②: 로봇 서버 노드 — 두산 API를 독점. 서비스 콜백 안에서 movej (DSR 전용 노드 분리 + 자체 실행기)
import rclpy, threading, time
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from std_srvs.srv import Trigger
import DR_init
rclpy.init(); DR_init.__dsr__id='dsr01'; DR_init.__dsr__model='m0609'
node=Node('robot_server'); dsr=Node('robot_server_dsr', namespace='dsr01'); DR_init.__dsr__node=dsr
from DSR_ROBOT2 import movej, get_current_posj, set_robot_mode, ROBOT_MODE_AUTONOMOUS
lock=threading.Lock(); g=ReentrantCallbackGroup()
def make(j1):
    def cb(req,res):
        if not lock.acquire(blocking=False): res.success=False; res.message='BUSY'; return res
        try:
            t=time.time(); r=movej([j1,0.0,90.0,0.0,90.0,0.0],vel=60,acc=60); p=get_current_posj()
            res.success=(r==0); res.message=f'ret={r} {time.time()-t:.2f}s j1={p[0]:.1f}'
        finally: lock.release()
        return res
    return cb
for name,j in (('a',15.0),('b',-15.0),('home',0.0)): node.create_service(Trigger,f'/robot/move_{name}',make(j),callback_group=g)
set_robot_mode(ROBOT_MODE_AUTONOMOUS); ex=MultiThreadedExecutor(); ex.add_node(node); node.get_logger().info('ready'); ex.spin()
