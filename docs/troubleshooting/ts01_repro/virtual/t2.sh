source /opt/ros/jazzy/setup.bash; source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
export ROS_DOMAIN_ID=91 PYTHONPATH=$PYTHONPATH:$HOME/ws_cobot_pjt/ws_dsr/install/dsr_common2/lib/dsr_common2/imp:$HOME/ws_cobot_pjt/ws_dsr/src/doosan-robot2/dsr_common2/imp
call(){ timeout 25 ros2 service call $1 std_srvs/srv/Trigger 2>&1 | grep -o "success=[A-Za-z]*, message='[^']*'" || echo "$1 응답 없음(멈춤)"; }
echo "##### 구조① 겹침: 서로 다른 프로세스가 동시에 다른 목표로"
python3 s1_feat.py g1 40 > g1.log 2>&1 & P1=$!; python3 s1_feat.py g3 -40 > g3.log 2>&1 & P3=$!
for i in $(seq 1 40); do grep -q ready g1.log && grep -q ready g3.log && break; sleep 1; done
call /g1/move > ca.log & A=$!; sleep 0.4; call /g3/move > cb.log; wait $A; cat ca.log cb.log
kill -9 $P1 $P3 2>/dev/null; sleep 2
echo "##### 구조③ 한 프로세스 · 기능 노드 3개 · 보조 노드 1개 공유"
python3 s3_oneproc.py > s3.log 2>&1 & P=$!
for i in $(seq 1 40); do grep -q ready s3.log && break; sleep 1; done
for round in 1 2 3; do for g in g1 g2 g3; do call /$g/move; done; done
echo "-- 겹침"; call /g1/move > ca.log & A=$!; sleep 0.4; call /g2/move > cb.log; wait $A; cat ca.log cb.log
grep -iE "error|Traceback|already" s3.log | sort | uniq -c | head -3
kill -9 $P 2>/dev/null; sleep 2
echo "##### 구조④ 스크립트형 · 기능은 함수 · HMI 통신 노드만 백그라운드"
python3 s4_script.py > s4.log 2>&1 & P=$!
for i in $(seq 1 40); do grep -q ready s4.log && break; sleep 1; done
timeout 14 ros2 topic hz /s4/state > hz.log 2>&1 & HZ=$!
call /s4/start; sleep 4.5; call /s4/stop; wait $HZ
grep "average rate" hz.log | tail -1; grep -E "round|PAUSED|end" s4.log; grep -iE "error|Traceback|already" s4.log | head -3
kill -9 $P 2>/dev/null
