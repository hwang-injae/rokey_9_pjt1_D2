import rclpy, threading, time
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from std_srvs.srv import Trigger
from std_msgs.msg import String
import DR_init
rclpy.init(); DR_init.__dsr__id='dsr01'; DR_init.__dsr__model='m0609'
dsr=Node('cell_dsr', namespace='dsr01'); DR_init.__dsr__node=dsr
from DSR_ROBOT2 import movej, get_current_posj, set_robot_mode, ROBOT_MODE_AUTONOMOUS
# --- "f1/f2/f3 라이브러리" 흉내: 그냥 함수 ---
def f1_pick(): return movej([10.0,0,90,0,90,0],vel=60,acc=60)
def f2_weigh(): return movej([20.0,0,90,0,90,0],vel=60,acc=60)
def f3_wipe(): return movej([30.0,0,90,0,90,0],vel=60,acc=60)
# --- HMI 통신 노드 ---
io=Node('flow_io'); step=['IDLE']; start=threading.Event(); stop=threading.Event()
pub=io.create_publisher(String,'/s4/state',10); io.create_timer(0.5,lambda:pub.publish(String(data=step[0])))
def on_start(q,r): start.set(); r.success=True; r.message='started'; return r
def on_stop(q,r): stop.set(); r.success=True; r.message='stop accepted'; return r
io.create_service(Trigger,'/s4/start',on_start); io.create_service(Trigger,'/s4/stop',on_stop)
ex=SingleThreadedExecutor(); ex.add_node(io); threading.Thread(target=ex.spin,daemon=True).start()
set_robot_mode(ROBOT_MODE_AUTONOMOUS); print('ready',flush=True)
start.wait()
for rnd in range(2):
    for nm,fn in (('PICK',f1_pick),('WEIGH',f2_weigh),('WIPE',f3_wipe)):
        if stop.is_set(): step[0]='PAUSED'; print('PAUSED by stop',flush=True); break
        step[0]=nm; t=time.time(); r=fn(); print(f'round{rnd+1} {nm} ret={r} {time.time()-t:.1f}s j1={get_current_posj()[0]:.1f}',flush=True)
    else: continue
    break
step[0]='DONE' if not stop.is_set() else 'PAUSED'; time.sleep(1.5); print('end',step[0],flush=True)
