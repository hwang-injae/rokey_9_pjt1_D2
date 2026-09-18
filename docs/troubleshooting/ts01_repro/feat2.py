import sys, rclpy, threading, time
from rclpy.node import Node
from std_srvs.srv import Trigger
import DR_init
MODE=sys.argv[1]
rclpy.init()
DR_init.__dsr__id='dsr01'; DR_init.__dsr__model='m0609'
node=Node('feat_'+MODE, namespace='dsr01')
if MODE=='A_noinit':
    from DSR_ROBOT2 import movej   # 노드 세팅 없이 import
if MODE in ('B_plain','C_fix'):
    DR_init.__dsr__node=node
    if MODE=='C_fix':
        from rclpy.callback_groups import ReentrantCallbackGroup
        node._default_callback_group=ReentrantCallbackGroup()
if MODE=='D_sepnode':
    dsr_node=Node('dsr_cli_'+MODE, namespace='dsr01'); DR_init.__dsr__node=dsr_node
from DSR_ROBOT2 import movej
lock=threading.Lock(); cnt=[0]
def cb(req,res):
    if not lock.acquire(blocking=False):
        res.success=False; res.message='BUSY'; return res
    try:
        cnt[0]+=1; t=time.time(); r=movej([0.0]*6, vel=30, acc=30)
        res.success=True; res.message=f'movej ret={r} {time.time()-t:.1f}s call#{cnt[0]}'
    finally: lock.release()
    return res
node.create_service(Trigger,'/test/move',cb)
# 2 Hz 상태 발행이 모션 중에도 유지되는지
from std_msgs.msg import String
pub=node.create_publisher(String,'/test/state',10); node.create_timer(0.5,lambda:pub.publish(String(data='tick')),callback_group=__import__('rclpy.callback_groups',fromlist=['x']).MutuallyExclusiveCallbackGroup())
if MODE=='B_plain':
    rclpy.spin(node)
elif MODE=='C_fix':
    from rclpy.executors import MultiThreadedExecutor
    ex=MultiThreadedExecutor(); ex.add_node(node); ex.spin()
elif MODE=='D_sepnode':
    from rclpy.executors import MultiThreadedExecutor
    ex=MultiThreadedExecutor(); ex.add_node(node); ex.spin()
