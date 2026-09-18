source /opt/ros/jazzy/setup.bash; source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
export ROS_DOMAIN_ID=92 PYTHONPATH=$PYTHONPATH:$HOME/ws_cobot_pjt/ws_dsr/install/dsr_common2/lib/dsr_common2/imp:$HOME/ws_cobot_pjt/ws_dsr/src/doosan-robot2/dsr_common2/imp
for i in $(seq 1 60); do grep -q "Configured and activated dsr_controller2" bringup.log && break; sleep 1; done; sleep 3
call(){ timeout 30 ros2 service call $1 std_srvs/srv/Trigger 2>&1 | grep -o "success=[A-Za-z]*, message='[^']*'" || echo "$1 응답 없음(멈춤)"; }
python3 robot_server.py > server.log 2>&1 & PS=$!
for g in g1 g2 g3; do python3 feat_client.py $g good > $g.log 2>&1 & done
for i in $(seq 1 40); do grep -q ready server.log && grep -q ready g3.log && break; sleep 1; done
echo "##### 구조② 기능 노드 3개(클라이언트) → 로봇 서버 → 두산 API : 번갈아 3바퀴"
for r in 1 2 3; do for g in g1 g2 g3; do call /$g/do; done; done
echo "##### 겹침: g1 시작 0.5초 뒤 g2"
python3 overlap.py /g1/do /g2/do 0.5
echo "##### 초보가 흔히 쓰는 방식(rclpy.spin + 콜백 안 동기 호출)의 기능 노드"
python3 feat_client.py g9 naive > g9.log 2>&1 & P9=$!; sleep 4; call /g9/do
grep -hiE "error|Traceback|already" server.log g1.log g9.log | sort | uniq -c | head -4
pkill -9 -f "[f]eat_client.py|[r]obot_server.py" 2>/dev/null
