import sys, rclpy, time, threading
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from std_srvs.srv import Trigger
a,b,delay=sys.argv[1],sys.argv[2],float(sys.argv[3])
rclpy.init(); n=Node('overlap_cli'); ex=MultiThreadedExecutor(); ex.add_node(n); threading.Thread(target=ex.spin,daemon=True).start()
ca=n.create_client(Trigger,a); cb=n.create_client(Trigger,b); ca.wait_for_service(10); cb.wait_for_service(10)
t0=time.time(); fa=ca.call_async(Trigger.Request()); time.sleep(delay); fb=cb.call_async(Trigger.Request())
while not (fa.done() and fb.done()) and time.time()-t0<30: time.sleep(0.05)
for nm,f in ((a,fa),(b,fb)): print(f'  {nm}: '+(f'{f.result().success} {f.result().message}' if f.done() else '응답 없음'))
