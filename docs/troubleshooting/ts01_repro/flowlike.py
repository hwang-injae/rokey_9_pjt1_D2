# flow_node 흉내: /flow/start 는 즉시 응답, 순서 실행은 작업 스레드에서 client.call()(동기), 상태 타이머 2 Hz
import rclpy, threading, time
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from std_srvs.srv import Trigger
from std_msgs.msg import String
rclpy.init(); n=Node('flow_like'); g=ReentrantCallbackGroup()
cli=n.create_client(Trigger,'/test/move',callback_group=g)
pub=n.create_publisher(String,'/flow_like/state',10); step=['IDLE']; stop=threading.Event()
n.create_timer(0.5,lambda:pub.publish(String(data=step[0])),callback_group=g)
def seq():
    for i in range(3):
        if stop.is_set(): step[0]='PAUSED'; n.get_logger().info('stop 요청으로 보류'); return
        step[0]=f'CALL{i+1}'; r=cli.call(Trigger.Request()); n.get_logger().info(f'call{i+1}: {r.message}')
    step[0]='DONE'
def on_start(req,res): threading.Thread(target=seq,daemon=True).start(); res.success=True; res.message='started'; return res
def on_stop(req,res): stop.set(); res.success=True; res.message='stop accepted'; return res
n.create_service(Trigger,'/flow_like/start',on_start,callback_group=g); n.create_service(Trigger,'/flow_like/stop',on_stop,callback_group=g)
ex=MultiThreadedExecutor(); ex.add_node(n); ex.spin()
