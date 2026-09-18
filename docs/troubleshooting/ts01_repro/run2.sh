source /opt/ros/jazzy/setup.bash; source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
export ROS_DOMAIN_ID=78 PYTHONPATH=$PYTHONPATH:$HOME/ws_cobot_pjt/ws_dsr/src/doosan-robot2/dsr_common2/imp
python3 fake_ctrl.py > ctrl.log 2>&1 & CT=$!
sleep 2
for M in C_fix D_sepnode; do
  echo "===== $M"
  python3 feat.py $M > feat_$M.log 2>&1 & FP=$!
  sleep 4
  for i in 1 2 3; do
    timeout 12 ros2 service call /test/move std_srvs/srv/Trigger > call.log 2>&1; rc=$?
    [ $rc -eq 124 ] && { echo "호출 $i: 응답 없음(멈춤)"; break; }
    grep -o "success=[A-Za-z]*, message='[^']*'" call.log
  done
  echo "-- 동작 중 상태 발행 주기 + 겹친 호출"
  timeout 8 ros2 topic hz /test/state > hz.log 2>&1 & HZ=$!
  timeout 12 ros2 service call /test/move std_srvs/srv/Trigger > c1.log 2>&1 & C1=$!
  sleep 0.7; timeout 12 ros2 service call /test/move std_srvs/srv/Trigger > c2.log 2>&1
  wait $C1 $HZ 2>/dev/null
  grep "average rate" hz.log | tail -1; grep -ho "success=[A-Za-z]*, message='[^']*'" c1.log c2.log
  grep -E "Error|already" feat_$M.log | tail -2
  kill -9 $FP 2>/dev/null; sleep 1
done
kill -9 $CT 2>/dev/null
