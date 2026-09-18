source /opt/ros/jazzy/setup.bash; source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
export ROS_DOMAIN_ID=79 PYTHONPATH=$PYTHONPATH:$HOME/ws_cobot_pjt/ws_dsr/src/doosan-robot2/dsr_common2/imp
python3 fake_ctrl.py > ctrl.log 2>&1 & CT=$!
sleep 2
echo "===== C_fix 재시도"; python3 feat.py C_fix > feat_C2.log 2>&1 & FP=$!; sleep 4
for i in 1 2; do timeout 10 ros2 service call /test/move std_srvs/srv/Trigger > call.log 2>&1; [ $? -eq 124 ] && echo "호출 $i: 응답 없음" || grep -o "message='[^']*'" call.log; done
kill -9 $FP; sleep 1
echo "===== D_sepnode + 타이머 별도 그룹"; python3 feat2.py D_sepnode > feat_D2.log 2>&1 & FP=$!; sleep 4
timeout 9 ros2 topic hz /test/state > hz.log 2>&1 & HZ=$!
for i in 1 2 3; do timeout 10 ros2 service call /test/move std_srvs/srv/Trigger > call.log 2>&1; grep -o "message='[^']*'" call.log; done
wait $HZ; grep "average rate" hz.log | tail -1
kill -9 $FP $CT 2>/dev/null
