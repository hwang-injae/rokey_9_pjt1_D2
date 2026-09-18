source /opt/ros/jazzy/setup.bash; source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
export ROS_DOMAIN_ID=80 PYTHONPATH=$PYTHONPATH:$HOME/ws_cobot_pjt/ws_dsr/src/doosan-robot2/dsr_common2/imp
python3 fake_ctrl.py > ctrl.log 2>&1 & CT=$!
python3 feat2.py D_sepnode > featD.log 2>&1 & FP=$!
python3 flowlike.py > flow.log 2>&1 & FL=$!
sleep 5
timeout 9 ros2 topic hz /flow_like/state > hz.log 2>&1 & HZ=$!
t0=$(date +%s.%N); timeout 5 ros2 service call /flow_like/start std_srvs/srv/Trigger | grep -o "message='[^']*'"; 
sleep 2.5; timeout 5 ros2 service call /flow_like/stop std_srvs/srv/Trigger | grep -o "message='[^']*'"
wait $HZ; grep "average rate" hz.log | tail -1; grep -E "call[0-9]|보류|Error" flow.log
kill -9 $CT $FP $FL 2>/dev/null
