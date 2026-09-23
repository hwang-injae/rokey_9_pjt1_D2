#!/usr/bin/env python3

import argparse

import cobot_common as cc
from cobot_api import BRUSH, PICK, SPONGE
from f1_handling import handling as f1


# ============================================================
# 미스트 펌프 임시 티칭값
# 용기 바뀌면 여기만 다시 수정
# ============================================================

MIST_HEAD_POSJ = [
    -33.43, 9.5, 95.0, 0.0, 75.64, -33.42
]

MIST_HEAD_POSX = [
    357.42, -226.50, 117.94,
    154.27, 180.0, 154.0
]

SOAP_X = MIST_HEAD_POSX[0]
SOAP_Y = MIST_HEAD_POSX[1]

HEAD_Z = MIST_HEAD_POSX[2]       # 117.94
HEAD_LIFT_MM = 30.0

# gripper
HEAD_OPEN_MM = 35.0
HEAD_GRIP_MM = 22.0
PRESS_GRIP_MM = 0.0
HEAD_GRIP_FORCE_N = 10.0

# 기준 방향 +Y
# SPONGE 쪽 = -90 deg
# BRUSH  쪽 = +90 deg
TOOL_TURN_DEG = {
    SPONGE: -90.0,
    BRUSH: +90.0,
}

# force press
FORCE_START_Z = 130.0

CONTACT_N = 5.0                  # 접촉 확인
FULL_PRESS_N = 10.0              # 눌림 끝 / 상한

FORCE_STEP_MM = 0.5              # 저속 힘 구간 이동 단위
FORCE_VEL_MM_S = 8.0
FORCE_ACC_MM_S2 = 20.0

# Z130에서 최대 여기까지만 탐색
# 접촉이 안 잡혀도 무한정 내려가지 않는다.
MAX_CONTACT_SEARCH_MM = 30.0
MAX_PRESS_DEPTH_MM = 10.0

# 자유이동: 현재 cell에서 허용하는 최대값
FAST_TCP_VEL = 400.0
FAST_TCP_ACC = 800.0

FAST_ROT_VEL = 100.0
FAST_ROT_ACC = 200.0


class UserQuit(Exception):
    pass


# ============================================================
# 기본
# ============================================================

def pose():
    return [float(v) for v in cc.where()[:6]]


def show(prefix="현재"):
    p = pose()

    print(
        f"{prefix}: "
        f"X={p[0]:.2f}, "
        f"Y={p[1]:.2f}, "
        f"Z={p[2]:.2f}, "
        f"A={p[3]:.2f}, "
        f"B={p[4]:.2f}, "
        f"C={p[5]:.2f}"
    )

    return p


def step(name, detail=""):
    print()
    print("=" * 78)
    print(f"[NEXT] {name}")

    if detail:
        print(f"       {detail}")

    show()

    cmd = input("Enter=실행 / q=종료 > ").strip().lower()

    if cmd == "q":
        raise UserQuit()


# ============================================================
# 빠른 자유이동
# ============================================================

def fast_rel(dx, dy, dz):
    cc.move_rel(
        dx,
        dy,
        dz,
        'BASE',
        vel_mm_s=FAST_TCP_VEL,
        acc_mm_s2=FAST_TCP_ACC,
    )


def fast_xy(name, x, y):
    p = pose()

    step(
        name,
        f"XY ({p[0]:.2f}, {p[1]:.2f})"
        f" -> ({x:.2f}, {y:.2f}), Z 유지"
    )

    fast_rel(
        x - p[0],
        y - p[1],
        0.0
    )

    show("도착")


def fast_z(name, z):
    p = pose()

    step(
        name,
        f"Z {p[2]:.2f} -> {z:.2f}"
    )

    fast_rel(
        0.0,
        0.0,
        z - p[2]
    )

    show("도착")


def fast_z_rel(name, dz):
    p = pose()

    step(
        name,
        f"Z {p[2]:.2f} -> {p[2] + dz:.2f} "
        f"({dz:+.2f} mm)"
    )

    fast_rel(
        0.0,
        0.0,
        dz
    )

    show("도착")


def orient_current_xyz(name, abc):
    p = pose()

    target = [
        p[0],
        p[1],
        p[2],
        float(abc[0]),
        float(abc[1]),
        float(abc[2]),
    ]

    step(
        name,
        f"XYZ 유지 / "
        f"A,B,C -> "
        f"{abc[0]:.2f}, {abc[1]:.2f}, {abc[2]:.2f}"
    )

    cc.move_pose(
        target,
        vel_mm_s=FAST_TCP_VEL,
        vel_deg_s=FAST_ROT_VEL,
        acc_mm_s2=FAST_TCP_ACC,
        acc_deg_s2=FAST_ROT_ACC,
    )

    show("자세 변경 후")


def turn_j6(name, deg):
    step(
        name,
        f"J6 상대회전 {deg:+.1f} deg"
    )

    # 90deg / 100deg/s = 약 0.9s
    cc.move_joint_rel(
        6,
        deg,
        time_s=abs(deg) / FAST_ROT_VEL,
        carrying=False,
    )

    show("회전 후")


# ============================================================
# RG2
# ============================================================

def grip_width(name, width):
    step(
        name,
        f"RG2 width={width:.1f} mm / "
        f"force={HEAD_GRIP_FORCE_N:.1f} N"
    )

    actual = cc.grip(
        float(width),
        HEAD_GRIP_FORCE_N
    )

    print(
        f"[GRIP] target={width:.1f} mm / "
        f"actual={actual:.2f} mm"
    )


# ============================================================
# 펌프 힘 감시
# ============================================================

def force_press():
    """
    미스트 펌프 임시 실기 구조 검증용.

    현재 용기는 최종 세제 용기가 아니므로
    아래 수치는 모두 TEMP 값이다.

      CONTACT_N       = 접촉 확인 기준
      FULL_PRESS_N    = 임시 펌핑 목표 힘
      MAX_FORCE_TRAVEL_MM = 탐색 명령 상한

    최종 세제 용기로 교체한 뒤
    실제 접촉력 / 작동력 / 스트로크를 다시 측정한다.

    현재 PR 목적:
      세제 접근
      -> 헤드 방향 전환
      -> 힘 기반 펌핑 구간
      -> 헤드 원위치
      -> 선택 툴 PICK

    전체 동작 구조 검증.
    """

    MAX_FORCE_TRAVEL_MM = 30.0

    step(
        "10 FORCE PRESS",
        f"[TEMP 미스트 용기]\n"
        f"접촉 기준={CONTACT_N:.1f} N\n"
        f"임시 펌핑 목표={FULL_PRESS_N:.1f} N\n"
        f"최대 하강 명령={MAX_FORCE_TRAVEL_MM:.1f} mm\n"
        f"최종 세제 용기 교체 후 값 재측정 예정"
    )

    baseline = cc.read_force()

    print()
    print(
        "[BASELINE] "
        f"Fx={baseline[0]:.2f}, "
        f"Fy={baseline[1]:.2f}, "
        f"Fz={baseline[2]:.2f} N"
    )

    start_z = pose()[2]

    travelled = 0.0
    contact_found = False
    contact_z = None
    peak = 0.0
    full_press = False

    cc.compliance_on()

    try:
        while travelled < MAX_FORCE_TRAVEL_MM:

            cc.move_rel(
                0.0,
                0.0,
                -FORCE_STEP_MM,
                'BASE',
                vel_mm_s=FORCE_VEL_MM_S,
                acc_mm_s2=FORCE_ACC_MM_S2,
            )

            travelled += FORCE_STEP_MM

            f = cc.read_force()

            dfz = abs(
                float(f[2]) -
                float(baseline[2])
            )

            peak = max(peak, dfz)

            z = pose()[2]

            print(
                f"[FORCE] "
                f"Z={z:7.2f} "
                f"travel={travelled:5.1f} mm "
                f"ΔFz={dfz:5.2f} N"
            )

            # ------------------------------------------------
            # 접촉 판정
            # ------------------------------------------------

            if (
                not contact_found
                and dfz >= CONTACT_N
            ):
                contact_found = True
                contact_z = z

                print()
                print(
                    f">>> CONTACT "
                    f"ΔFz={dfz:.2f} N "
                    f"@ Z={z:.2f}"
                )
                print()

            # ------------------------------------------------
            # 임시 펌핑 목표 힘
            # ------------------------------------------------

            if dfz >= FULL_PRESS_N:

                full_press = True

                print()
                print(
                    f">>> FULL PRESS "
                    f"ΔFz={dfz:.2f} N "
                    f"@ Z={z:.2f}"
                )

                break

    finally:
        cc.compliance_off()

    final_z = pose()[2]

    print()
    print("=" * 78)
    print("PUMP RESULT [TEMP MIST CONTAINER]")

    if contact_z is not None:
        print(f"접촉 Z          : {contact_z:.2f}")
    else:
        print("접촉 Z          : 미검출")

    print(f"종료 Z          : {final_z:.2f}")
    print(f"최대 ΔFz        : {peak:.2f} N")
    print(f"명령 하강량     : {travelled:.2f} mm")

    if full_press:
        print(
            f"결과             : 임시 목표 "
            f"{FULL_PRESS_N:.1f} N 도달"
        )
    else:
        print(
            "결과             : TEMP WARNING"
        )
        print(
            f"                   현재 미스트 용기에서 "
            f"{FULL_PRESS_N:.1f} N 미도달"
        )
        print(
            "                   최종 세제 용기 교체 후 "
            "힘/스트로크 재측정"
        )
        print(
            "                   구조 검증을 위해 다음 STEP 계속"
        )

    print("=" * 78)


# ============================================================
# SPONGE / BRUSH 공용 세제 펌프 -> F1 TOOL PICK
# ============================================================

def normalize_tool(value):
    v = str(value).strip().upper()

    if v in ('SPONGE', '스폰지'):
        return SPONGE

    if v in ('BRUSH', 'SCRUBBER', '수세미'):
        return BRUSH

    raise ValueError(
        f"지원하지 않는 tool={value!r} "
        "(SPONGE / BRUSH / SCRUBBER)"
    )


def pump_and_pick(tool):
    """
    F1 세제 펌프 전처리.

    공통:
      HOME
      -> 세제 헤드 접근
      -> 헤드 파지
      -> 선택 툴 방향으로 J6 회전
      -> 펌프 누르기
      -> 헤드 +Y 원위치
      -> F1 tool(tool, PICK)

    차이:
      SPONGE = -90 deg
      BRUSH  = +90 deg

    현재 미스트 펌프의 좌표/힘/스트로크는 TEMP.
    최종 용기로 교체 후 파라미터만 재티칭한다.
    """

    if tool not in (SPONGE, BRUSH):
        raise ValueError(
            f"tool={tool!r} — SPONGE/BRUSH만 가능"
        )

    turn_deg = TOOL_TURN_DEG[tool]

    print()
    print("=" * 78)
    print(f"MIST SOAP -> {tool} PICK / REAL")
    print("=" * 78)
    print(f"TOOL            : {tool}")
    print(f"HEAD TURN       : {turn_deg:+.1f} deg")
    print(f"MIST HEAD POSX  : {MIST_HEAD_POSX}")
    print(
        f"FORCE TEMP      : "
        f"contact {CONTACT_N:.1f} N / "
        f"target {FULL_PRESS_N:.1f} N"
    )
    print("용기 종속 좌표/힘/스트로크는 TEMP")
    print("=" * 78)

    # ------------------------------------------------------
    # 빈손 시작
    # ------------------------------------------------------

    step(
        "00 RG2 초기화",
        f"빈손 확인 / 선택 툴={tool}"
    )

    cc.release()

    # ------------------------------------------------------
    # HOME
    # ------------------------------------------------------

    step(
        "01 HOME",
        f"{tool} 세제 시퀀스 시작"
    )

    cc.move_to(
        'HOME',
        False
    )

    # ------------------------------------------------------
    # MIST 접근
    # ------------------------------------------------------

    fast_xy(
        "02 SOAP X/Y",
        SOAP_X,
        SOAP_Y
    )

    orient_current_xyz(
        "03 MIST HEAD orientation",
        MIST_HEAD_POSX[3:6]
    )

    grip_width(
        "04 HEAD OPEN 30 mm",
        HEAD_OPEN_MM
    )

    fast_z(
        "05 MIST HEAD Z117.94",
        HEAD_Z
    )

    grip_width(
        "06 HEAD GRIP 20 mm",
        HEAD_GRIP_MM
    )

    # ------------------------------------------------------
    # +Y -> 선택 툴 방향
    # SPONGE -90 / BRUSH +90
    # ------------------------------------------------------

    turn_j6(
        f"07 HEAD -> {tool} {turn_deg:+.0f} deg",
        turn_deg
    )

    # ------------------------------------------------------
    # 펌프 누르기 준비
    # 30mm OPEN -> Z +30 -> 0mm
    # ------------------------------------------------------

    grip_width(
        "08 HEAD OPEN 30 mm",
        HEAD_OPEN_MM
    )

    fast_z_rel(
        "08-1 HEAD 위로 +30 mm",
        HEAD_LIFT_MM
    )

    grip_width(
        "09 PRESS GRIP 0 mm",
        PRESS_GRIP_MM
    )

    fast_z(
        "09-1 FORCE START Z130",
        FORCE_START_Z
    )

    # ------------------------------------------------------
    # 힘 기반 펌프 구간
    # ------------------------------------------------------

    force_press()

    # ------------------------------------------------------
    # 펌프에서 빠져나오기
    # ------------------------------------------------------

    fast_z_rel(
        "11 펌프에서 +30 mm 상승",
        +30.0
    )

    grip_width(
        "12 HEAD OPEN 30 mm",
        HEAD_OPEN_MM
    )

    fast_z(
        "13 HEAD Z117.94",
        HEAD_Z
    )

    grip_width(
        "14 HEAD GRIP 20 mm",
        HEAD_GRIP_MM
    )

    # ------------------------------------------------------
    # 선택 툴 방향 -> +Y 원위치
    # ------------------------------------------------------

    turn_j6(
        f"15 {tool} -> +Y {-turn_deg:+.0f} deg",
        -turn_deg
    )

    grip_width(
        "16 HEAD RELEASE 30 mm",
        HEAD_OPEN_MM
    )

    # ------------------------------------------------------
    # F1 제품 함수로 실제 TOOL PICK
    # ------------------------------------------------------

    fast_z(
        "17 TOOL PICK 이동 높이 Z150",
        150.0
    )

    step(
        f"18 F1 tool({tool}, PICK)",
        "세제 펌프 완료 -> 툴 PICK -> F3 인계"
    )

    result = f1.tool(
        tool,
        PICK
    )

    print()
    print(
        f"[F1 TOOL PICK] "
        f"tool={tool} / "
        f"code={result.code} / "
        f"width={result.width_mm:.2f} mm"
    )

    if not result.ok:
        raise RuntimeError(
            f"F1 tool({tool}, PICK) 실패: "
            f"{result.code}"
        )

    print()
    print("=" * 78)
    print(f"SOAP -> {tool} PICK 완료")
    print("이 상태에서 F3 인계")
    print("=" * 78)

    return result


def main():
    ap = argparse.ArgumentParser(
        description=(
            "세제 펌프 작동 후 "
            "SPONGE/BRUSH PICK 실기 rig"
        )
    )

    ap.add_argument(
        "--tool",
        default="SPONGE",
        help=(
            "SPONGE / BRUSH "
            "(SCRUBBER도 BRUSH로 처리)"
        ),
    )

    args = ap.parse_args()
    tool = normalize_tool(args.tool)

    cc.init('rig_soap_tool_real')

    try:
        pump_and_pick(tool)

    except UserQuit:
        print()
        print("[STOP] 사용자 종료")
        print("현재 자세 유지 / 자동 HOME 없음")

    except KeyboardInterrupt:
        print()
        print("[STOP] Ctrl+C")
        print("현재 자세 유지 / 자동 HOME 없음")

    except Exception as e:
        print()
        print(
            f"[ERROR] {type(e).__name__}: {e}"
        )
        print(
            "자동 HOME / 자동 RELEASE / "
            "자동 추가 이동 없음"
        )
        raise

    finally:
        try:
            cc.force_off()
        except Exception:
            pass

        cc.shutdown()


if __name__ == '__main__':
    main()
