# 기능 노드: flow 가 부르는 서비스를 제공하고, 그 콜백 안에서 로봇 서버를 "동기"로 부른다
import sys, rclpy, time
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from std_srvs.srv import Trigger
NAME,MODE=sys.argv[1],sys.argv[2]            # MODE: good(MultiThreaded+Reentrant) | naive(rclpy.spin 기본)
rclpy.init(); node=Node(NAME)
g=ReentrantCallbackGroup() if MODE=='good' else None
cli={k:node.create_client(Trigger,f'/robot/move_{k}',callback_group=g) for k in ('a','b','home')}
n=[0]
def cb(req,res):
    n[0]+=1; t=time.time(); out=[]
    for k in (('a','home') if n[0]%2 else ('b','home')):      # 기능 하나 = 로봇 명령 여러 개
        r=cli[k].call(Trigger.Request()); out.append(f'{k}:{r.message}')
        if not r.success: res.success=False; res.message=f'{NAME} call#{n[0]} '+' | '.join(out); return res
    res.success=True; res.message=f'{NAME} call#{n[0]} {time.time()-t:.2f}s '+' | '.join(out); return res
node.create_service(Trigger,f'/{NAME}/do',cb,callback_group=g)
node.get_logger().info('ready')
if MODE=='good':
    ex=MultiThreadedExecutor(); ex.add_node(node); ex.spin()
else:
    rclpy.spin(node)
