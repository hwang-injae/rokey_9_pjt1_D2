source /opt/ros/jazzy/setup.bash; source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
export ROS_DOMAIN_ID=91 PYTHONPATH=$PYTHONPATH:$HOME/ws_cobot_pjt/ws_dsr/install/dsr_common2/lib/dsr_common2/imp:$HOME/ws_cobot_pjt/ws_dsr/src/doosan-robot2/dsr_common2/imp
python3 s1_feat.py g1 10 > g1.log 2>&1 & P1=$!
python3 s1_feat.py g2 20 > g2.log 2>&1 & P2=$!
python3 s1_feat.py g3 30 > g3.log 2>&1 & P3=$!
for i in $(seq 1 40); do grep -q ready g1.log && grep -q ready g2.log && grep -q ready g3.log && break; sleep 1; done
echo "기동: $(grep -c ready g1.log g2.log g3.log | tr '\n' ' ')"
ok=0; fail=0
for round in 1 2 3; do for g in g1 g2 g3; do
  timeout 25 ros2 service call /$g/move std_srvs/srv/Trigger > c.log 2>&1; rc=$?
  if [ $rc -eq 124 ]; then echo "round$round $g: 응답 없음(멈춤)"; fail=$((fail+1)); else grep -o "success=[A-Za-z]*, message='[^']*'" c.log; grep -q "success=True" c.log && ok=$((ok+1)) || fail=$((fail+1)); fi
done; done
echo "== 같은 노드 연속 3회"; for i in 1 2 3; do timeout 25 ros2 service call /g2/move std_srvs/srv/Trigger 2>&1 | grep -o "message='[^']*'" || echo "응답 없음"; done
echo "== 두 노드 동시에 호출(겹침)"; timeout 25 ros2 service call /g1/move std_srvs/srv/Trigger > ca.log 2>&1 & A=$!; sleep 0.3; timeout 25 ros2 service call /g3/move std_srvs/srv/Trigger > cb.log 2>&1; wait $A
grep -ho "success=[A-Za-z]*, message='[^']*'" ca.log cb.log
echo "결과: 번갈아 9회 중 성공 $ok · 실패 $fail"; grep -hiE "error|exception|Traceback" g1.log g2.log g3.log | sort | uniq -c | head -5
kill -9 $P1 $P2 $P3 2>/dev/null
