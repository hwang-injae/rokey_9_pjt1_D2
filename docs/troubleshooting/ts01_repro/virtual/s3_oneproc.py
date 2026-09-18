import rclpy, threading, time
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from std_srvs.srv import Trigger
import DR_init
rclpy.init(); DR_init.__dsr__id='dsr01'; DR_init.__dsr__model='m0609'
dsr=Node('robot_dsr', namespace='dsr01'); DR_init.__dsr__node=dsr
from DSR_ROBOT2 import movej, get_current_posj, set_robot_mode, ROBOT_MODE_AUTONOMOUS
lock=threading.Lock(); ex=MultiThreadedExecutor()
def make(NAME,J1):
    node=Node(NAME, namespace='dsr01'); n=[0]
    def cb(req,res):
        if not lock.acquire(blocking=False): res.success=False; res.message='BUSY'; return res
        try:
            n[0]+=1; t=time.time(); r=movej([J1 if n[0]%2 else 0.0,0.0,90.0,0.0,90.0,0.0], vel=60, acc=60); p=get_current_posj()
            res.success=(r==0); res.message=f'{NAME} call#{n[0]} movej ret={r} {time.time()-t:.1f}s j1={p[0]:.1f}'
        finally: lock.release()
        return res
    node.create_service(Trigger,f'/{NAME}/move',cb); ex.add_node(node)
for nm,j in (('g1',10.0),('g2',20.0),('g3',30.0)): make(nm,j)
set_robot_mode(ROBOT_MODE_AUTONOMOUS); print('ready',flush=True); ex.spin()
