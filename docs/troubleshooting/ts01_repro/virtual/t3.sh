source /opt/ros/jazzy/setup.bash; source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
export ROS_DOMAIN_ID=91 PYTHONPATH=$PYTHONPATH:$HOME/ws_cobot_pjt/ws_dsr/install/dsr_common2/lib/dsr_common2/imp:$HOME/ws_cobot_pjt/ws_dsr/src/doosan-robot2/dsr_common2/imp
echo "##### 구조① 프로세스 2개, g1→+40 시작 0.5초 뒤 g3→-40"
python3 s1_feat.py g1 40 > g1.log 2>&1 & P1=$!; python3 s1_feat.py g3 -40 > g3.log 2>&1 & P3=$!
for i in $(seq 1 40); do grep -q ready g1.log && grep -q ready g3.log && break; sleep 1; done
python3 overlap.py /g1/move /g3/move 0.5
echo "  (복귀)"; python3 overlap.py /g1/move /g3/move 6 | sed 's/^/  /'
echo "  한 번 더:"; python3 overlap.py /g1/move /g3/move 0.5
kill -9 $P1 $P3 2>/dev/null; sleep 2
echo "##### 구조③ 한 프로세스(공유 잠금), g1 시작 0.3초 뒤 g3"
python3 s3_oneproc.py > s3.log 2>&1 & P=$!
for i in $(seq 1 40); do grep -q ready s3.log && break; sleep 1; done
python3 overlap.py /g1/move /g3/move 0.3
kill -9 $P 2>/dev/null
