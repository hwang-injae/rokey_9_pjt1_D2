#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
F1 이동 + GRIP/RELEASE 검증 Virtual STEP 스크립트 v6
- 기능 행동(털기 왕복, 세척 동작, 헹굼 담금, 물버림 등)은 포함하지 않음.\n- GRIP/RELEASE는 Virtual 드라이버에 직접 폭/open 명령. 힘(i/d)은 Virtual에서 검증하지 않음.
- 한석형 담당: 집기/놓기/툴 픽·복귀/스테이션 이동/랙 적재 경로만 확인.
- Enter 한 번 = 한 동작, q = 종료
- Virtual 전용
"""

import sys
import time
import cobot_common as cc
from onrobot_rg_msgs.srv import SetCommand
from cobot_common.bootstrap import dsr

JV, JA = 20.0, 40.0
LV, LA = 60.0, 120.0

# Virtual에서 그리퍼 동작까지 보기 위한 시험값.
# 필요하면 여기 숫자만 바꾸면 됨.
BOWL_GRIP_WIDTH = 2.0
BOWL_GRIP_FORCE = 20.0

CUP_GRIP_WIDTH = 70.0
CUP_GRIP_FORCE = 15.0

SPONGE_GRIP_WIDTH = 30.0
SPONGE_GRIP_FORCE = 30.0

HOME_J = [0.0, 0.0, 90.0, 0.0, 90.0, 0.0]

Q = {
    "BOWL_PICK": [0, 23, 68.4, 0, 88.3, 0],
    "CUP_PICK": [17.78, 35.8, 68.4, 0, 75.84, 22.6],

    "BOWL_SPONGE_PICK": [-40.45, 2.5, 111.5, 0, 66.06, -220.37],
    "CUP_SPONGE_PICK": [-28.7, 17, 84, -0.12, 79, -28.7],

    "CUP_REGRIP": [-29.24, 19.3, 132.86, 68.2, 71.8, -63.8],
}

X = {
    # 스테이션 진입/대기 위치만. 실제 기능 동작은 다른 담당.
    "BOWL_WASTE_READY": [615.7, -171, 241, 164, 179, 164],
    "CUP_WASTE_READY": [114.8, -407.5, 239.4, 85, -166.6, -160.6],

    "BOWL_PLACE_1": [419.7, 17.5, 202.1, 128.2, 180, -52],
    "BOWL_PLACE_2": [419.7, 17.5, 54.4, 128, 180, -52.2],

    "CUP_PLACE_1": [367.56, 114.2, 300, 89, 126.2, 86],
    "CUP_PLACE_2": [367.56, 114.2, 111.8, 89, 126.2, 86],

    "BOWL_WASH_WAIT": [367.5, 8, 235, 157.2, 180, 157],
    "BOWL_WASH_CONTACT": [367.5, 8, 47, 157.2, 180, 157],

    "CUP_WASH_WAIT": [369.19, 152.77, 235, 156.96, 180, 156.8],
    "CUP_WASH_CONTACT": [369.19, 152.77, 156.54, 156.96, 180, 156.8],

    "BOWL_SPONGE_RETURN": [273.6, -222.86, 65.24, 128.22, 180, -52],
    "CUP_SPONGE_RETURN": [422.94, -223, 130, 156.9, 180, 156.7],

    "BOWL_RINSE_READY": [205.8, -445.7, -13.6, 123.2, 180, 123],
    "CUP_RINSE_READY": [152, -422.7, 144.33, 164.5, -180, 72.8],

    "CUP_RACK1_1": [331, 401.4, 411.4, 79.6, 72, -91],
    "CUP_RACK1_2": [331, 401.4, 279.14, 79.6, 72, -91.45],
    "CUP_RACK2_1": [266.6, 471.5, 418.6, 91.5, 74.5, -96.8],
    "CUP_RACK2_2": [268, 473.4, 285.6, 88.7, 76.8, -93],

    "BOWL_RACK_REAR": [301.4, 606.2, 307.8, 92.76, 95, 7.4],
    "BOWL_RACK_NEXT": [303.24, 549.1, 299.3, 93.8, 96.4, 6],
}


def main():
    cc.init("rig_f1_move_only_step")
    d = dsr()
    log = cc.io_node().get_logger()
    step_no = 0
    home_x = None

    def ok(ret, label):
        if ret != 0:
            raise RuntimeError(f"{label} 실패: return={ret}")

    def prompt(label, target=None):
        nonlocal step_no
        step_no += 1
        print("\n" + "=" * 82)
        print(f"[STEP {step_no}] {label}")
        if target is not None:
            print(f"목표 = {target}")
        if input("Enter = 실행 / q = 종료 > ").strip().lower() == "q":
            raise KeyboardInterrupt

    def show_pose(label):
        j = [round(float(v), 2) for v in d.get_current_posj()]
        x = [round(float(v), 2) for v in d.get_current_posx(ref=d.DR_BASE)[0]]
        print(f"[완료] {label}")
        print(f"  J = {j}")
        print(f"  X = {x}")

    def movej_values(label, q):
        prompt(f"MOVEJ  {label}", q)
        ok(d.movej([float(v) for v in q], vel=JV, acc=JA), label)
        show_pose(label)

    def movej(name):
        movej_values(name, Q[name])

    def movel_values(label, x):
        prompt(f"MOVEL  {label}", x)
        ok(d.movel([float(v) for v in x], vel=LV, acc=LA,
                   ref=d.DR_BASE, mod=d.DR_MV_MOD_ABS), label)
        show_pose(label)

    def movel(name):
        movel_values(name, X[name])

    def rel(label, dx=0.0, dy=0.0, dz=0.0):
        delta = [float(dx), float(dy), float(dz), 0.0, 0.0, 0.0]
        prompt(f"MOVEL REL  {label}", delta)
        ok(d.movel(delta, vel=LV, acc=LA,
                   ref=d.DR_BASE, mod=d.DR_MV_MOD_REL), label)
        show_pose(label)

    # Virtual gripper driver는 'i'/'d' 힘 변경 명령을 지원하지 않는다.
    # 따라서 Virtual 경로 검증에서는 /onrobot/sendCommand에
    # 'o'(open) 또는 0.1 mm 단위 폭 문자열만 직접 보낸다.
    # 실제 로봇용 최종 코드에서는 cc.grip(width, force) / cc.release()를 사용한다.
    gripper_client = cc.io_node().create_client(SetCommand, '/onrobot/sendCommand')

    def _virtual_gripper_send(command, label):
        if not gripper_client.wait_for_service(timeout_sec=3.0):
            raise RuntimeError("/onrobot/sendCommand 서비스가 안 보인다")
        req = SetCommand.Request()
        req.command = str(command)
        res = gripper_client.call(req)
        if res is None or not res.success:
            raise RuntimeError(
                f"{label}: 그리퍼 명령 {command!r} 실패 — "
                f"{getattr(res, 'message', '응답 없음')}"
            )
        time.sleep(0.4)

    def grip_step(label, width, force):
        # force는 실제 로봇용 참고값으로 화면에만 표시.
        command = str(int(round(float(width) * 10.0)))  # 0.1 mm 단위
        prompt(
            f"GRIP  {label}",
            f"Virtual width={width} mm -> command={command!r} "
            f"(실물 force={force} N)"
        )
        _virtual_gripper_send(command, label)
        print(f"[완료] {label} GRIP — Virtual 폭 {width:.1f} mm")

    def release_step(label):
        prompt(f"RELEASE  {label}", "Virtual command='o'")
        _virtual_gripper_send('o', label)
        print(f"[완료] {label} RELEASE")

    def home_j():
        nonlocal home_x
        movej_values("HOME", HOME_J)
        home_x = [float(v) for v in d.get_current_posx(ref=d.DR_BASE)[0]]

    def home_l():
        if home_x is None:
            raise RuntimeError("HOME posx가 아직 저장되지 않음")
        movel_values("HOME_LINEAR", home_x)

    def rack_home_z338():
        if home_x is None:
            raise RuntimeError("HOME posx가 아직 저장되지 않음")
        x = list(home_x)
        x[2] = 338.0
        movel_values("RACK_HOME_Z338", x)

    def bowl_cycle():
        print("\n########## BOWL MOVE-ONLY ##########")
        home_j()

        # 첫 파지 전에 빈손 상태에서 그리퍼를 열고 힘 기준을 잡는다.
        release_step("INITIAL OPEN")

        movej("BOWL_PICK")
        grip_step("BOWL", BOWL_GRIP_WIDTH, BOWL_GRIP_FORCE)

        # WASTE 도착까지만. 털기 행동은 F2 담당.
        movel("BOWL_WASTE_READY")


        # 그릇 놓기
        movel("BOWL_PLACE_1")
        movel("BOWL_PLACE_2")
        release_step("BOWL PLACE")
        rel("BOWL_PLACE_EXIT_Z100", dz=100)

        # 수세미 픽
        movej("BOWL_SPONGE_PICK")
        grip_step("BOWL SPONGE", SPONGE_GRIP_WIDTH, SPONGE_GRIP_FORCE)

        # 세척 위치 이동까지만. 실제 닦기는 F3 담당.
        home_l()
        movel("BOWL_WASH_WAIT")
        movel("BOWL_WASH_CONTACT")

        movel("BOWL_WASH_WAIT")
        home_l()

        # 수세미 복귀
        movel("BOWL_SPONGE_RETURN")
        release_step("BOWL SPONGE RETURN")

        # 그릇 재파지
        movel("BOWL_PLACE_1")
        movel("BOWL_PLACE_2")
        grip_step("BOWL RE-GRIP", BOWL_GRIP_WIDTH, BOWL_GRIP_FORCE)
        rel("BOWL_REGRIP_EXIT_Z100", dz=100)

        # 헹굼 위치 도착까지만. 담금/왕복은 F2 담당.
        movel("BOWL_RINSE_READY")


        # 식세기 적재
        home_j()
        rack_home_z338()
        movel("BOWL_RACK_REAR")
        release_step("BOWL RACK REAR")
        rel("BOWL_RACK_EXIT_Y", dy=-25)
        rel("BOWL_RACK_EXIT_Z", dz=200)
        home_j()

    def cup_cycle(slot):
        print(f"\n########## CUP {slot} MOVE-ONLY ##########")

        movej("CUP_PICK")
        grip_step(f"CUP{slot}", CUP_GRIP_WIDTH, CUP_GRIP_FORCE)

        # WASTE 도착까지만
        movel("CUP_WASTE_READY")


        # 컵 놓기
        movel("CUP_PLACE_1")
        movel("CUP_PLACE_2")
        release_step(f"CUP{slot} PLACE")
        rel(f"CUP{slot}_PLACE_EXIT_Z100", dz=100)

        # 수세미 픽
        movej("CUP_SPONGE_PICK")
        grip_step(f"CUP{slot} SPONGE", SPONGE_GRIP_WIDTH, SPONGE_GRIP_FORCE)

        # 세척 위치 도착까지만
        home_l()
        movel("CUP_WASH_WAIT")
        movel("CUP_WASH_CONTACT")

        movel("CUP_WASH_WAIT")
        home_l()

        # 수세미 복귀
        movel("CUP_SPONGE_RETURN")
        release_step(f"CUP{slot} SPONGE RETURN")

        # 컵 재파지
        movej("CUP_REGRIP")
        grip_step(f"CUP{slot} RE-GRIP", CUP_GRIP_WIDTH, CUP_GRIP_FORCE)

        # 헹굼 위치까지만
        movel("CUP_RINSE_READY")


        # 식세기 적재
        home_j()
        rack_home_z338()

        if slot == 1:
            movel("CUP_RACK1_1")
            movel("CUP_RACK1_2")
            release_step("CUP1 RACK")
            movel("CUP_RACK1_1")
        else:
            movel("CUP_RACK2_1")
            movel("CUP_RACK2_2")
            release_step("CUP2 RACK")
            movel("CUP_RACK2_1")

        home_j()

    try:
        if d.get_robot_system() != d.ROBOT_SYSTEM_VIRTUAL:
            log.error("Virtual이 아니다. 실행하지 않는다.")
            return 2

        print("F1 이동 + GRIP/RELEASE STEP 검증")
        print("BOWL -> CUP1 -> CUP2")
        print("털기/세척/헹굼 행동 자체는 제외. Virtual 그리퍼는 폭/open만 검증합니다.")

        bowl_cycle()
        cup_cycle(1)
        cup_cycle(2)

        print("\n========== MOVE-ONLY PATH COMPLETE ==========")
        return 0

    except KeyboardInterrupt:
        print("\n사용자 종료")
        return 130
    finally:
        cc.shutdown()


if __name__ == "__main__":
    sys.exit(main())
