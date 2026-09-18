source /opt/ros/jazzy/setup.bash; source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
export ROS_DOMAIN_ID=77 PYTHONPATH=$PYTHONPATH:$HOME/ws_cobot_pjt/ws_dsr/src/doosan-robot2/dsr_common2/imp
python3 fake_ctrl.py > ctrl.log 2>&1 & CT=$!
sleep 2
for M in A_noinit B_plain C_fix D_sepnode; do
  echo "===== $M"
  python3 feat.py $M > feat_$M.log 2>&1 & FP=$!
  sleep 4
  if ! kill -0 $FP 2>/dev/null; then echo "노드가 기동 중 죽음:"; grep -E "Error|error" feat_$M.log | tail -2; continue; fi
  for i in 1 2 3; do
    timeout 12 ros2 service call /test/move std_srvs/srv/Trigger 2>&1 | grep -E "message=|success" | tail -1 || true
    [ ${PIPESTATUS[0]} -eq 124 ] && echo "호출 $i: 12초 안에 응답 없음(멈춤)" && break
  done
  ( timeout 6 ros2 topic hz /test/state 2>&1 | grep "average rate" | tail -1 ) &
  sleep 1; timeout 10 ros2 service call /test/move std_srvs/srv/Trigger >/dev/null 2>&1; wait
  grep -E "Error|already" feat_$M.log | tail -2
  kill -9 $FP 2>/dev/null; sleep 1
done
kill -9 $CT 2>/dev/null
