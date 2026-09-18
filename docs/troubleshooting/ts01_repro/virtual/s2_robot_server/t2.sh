source /opt/ros/jazzy/setup.bash; source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
export ROS_DOMAIN_ID=92 PYTHONPATH=$PYTHONPATH:$HOME/ws_cobot_pjt/ws_dsr/install/dsr_common2/lib/dsr_common2/imp:$HOME/ws_cobot_pjt/ws_dsr/src/doosan-robot2/dsr_common2/imp
python3 robot_server.py > server.log 2>&1 & PS=$!
python3 feat_client.py g1 good > g1.log 2>&1 & P1=$!; python3 feat_client.py g2 good > g2.log 2>&1 & P2=$!; python3 feat_client.py g9 naive > g9.log 2>&1 & P9=$!
for i in $(seq 1 40); do grep -q ready server.log && grep -q ready g2.log && grep -q ready g9.log && break; sleep 1; done
echo "##### 겹침: g1 시작 0.5초 뒤 g2 (서로 다른 기능 노드가 동시에 서버에 요청)"
python3 overlap.py /g1/do /g2/do 0.5
echo "##### 초보가 흔히 쓰는 방식(rclpy.spin + 콜백 안에서 서버를 동기 호출)"
timeout 15 ros2 service call /g9/do std_srvs/srv/Trigger 2>&1 | grep -o "success=[A-Za-z]*, message='[^']*'" || echo "/g9/do 15초 안에 응답 없음(멈춤)"
grep -hiE "error|Traceback|already" server.log g1.log g9.log | sort | uniq -c | head -4
kill -9 $PS $P1 $P2 $P9 2>/dev/null
