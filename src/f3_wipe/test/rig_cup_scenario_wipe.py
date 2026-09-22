#!/usr/bin/env python3
"""컵 한 바퀴 실기 — 한석형 동선(rig_bowl_scenario_real.py CUP 분기, main 최신)에서 컵만 떼어낸 것
   + F3 자리에 soap·wipe_cup (박진용 9/22 3차).

    cd ~/cobot1/rokey_9_pjt1_D2 && soc && PREWASH_VEL_SCALE=0.3 python3 src/f3_wipe/test/rig_cup_scenario_wipe.py
    cd ~/cobot1/rokey_9_pjt1_D2 && soc && PREWASH_VEL_SCALE=0.3 python3 src/f3_wipe/test/rig_cup_scenario_wipe.py --step

🔸 F1(한석형) 쪽은 확정됐다(더 이상 안 바뀐다) — 이 파일은 그 확정본에서 컵 경로만 떼어 우리(F3) 코드와
   연동 시험하는 용도다. `rig_bowl_scenario_wipe.py`(그릇)와는 완전히 분리된 별개 파일이다(박진용 9/22 요청 —
   공용 함수를 같이 쓰다 그릇·컵이 서로 영향받는 걸 피한다). 그래서 f1_tool_pick·f1_tool_return·
   patch_runtime_config 는 이 파일에도 그대로 들어 있다(그릇 파일과 중복, 의도된 것).

   F1 원본에서 바꾼 곳(값·좌표·속도·순서는 전부 그대로):
     ① 구간마다 Enter — --step 을 줄 때만 묻는다(기본은 한 번에)
     ② "F3 세척 완료" 수동 대기 자리 = F1 f1_tool_pick(TOOL_BRUSH) → F3: soap('CUP') → wipe_cup() →
        f1_tool_return(BRUSH) → 실패면 멈춘다
"""
import argparse
import sys

import cobot_common as cc
from cobot_common.bootstrap import dsr
from f3_wipe import wipe

HOME_J = [0.0, 0.0, 90.0, 0.0, 90.0, 0.0]
TOOL_BRUSH_PICK_J = [-28.7, 17.0, 84.0, -0.12, 79.0, -28.7]

# 🔧 9/22 박진용 3차: 손잡이 실측 8mm(캘리퍼스) → 목표 폭을 그보다 타이트하게(수세미와 같은 방식) —
#    목표가 실제 손잡이보다 좁아야 잡았을 때 손잡이에 막혀 목표보다 큰 값에서 멈추고(=잡음),
#    빈손이면 막힘 없이 목표까지 그대로 닫힌다(=빈손). 5.0은 첫 추정값 — 실기로 "잡았을 때 실제 몇 mm에서
#    멈추는지" 확인해서 맞는지 봐야 한다(수세미도 25.6mm로 실측 확인 전까지는 추정이었다).
BRUSH_WIDTH_MM = 5.0
BRUSH_FORCE_N = 40.0                  # 🔧 9/22 3차: 수세미(SPONGE_FORCE_N)와 통일 — 둘 다 단단한 손잡이라 다를 이유 없다


def f1_tool_pick(station, width_mm, force_n, label):
    """F1: 툴 홀더에서 꽂는 위치까지 이동해 실제 pick_x를 읽고 grip까지 수행.

    - F1 은 grip 까지만 한다.
    - Z 상승 / HOME 복귀는 여기서 하지 않는다.
    - BRUSH 는 현재 설정이 비어 있어 실기 전에 확정이 필요하다.
    """
    d = dsr()
    station_name = str(station)
    width_value = float(width_mm)
    force_value = float(force_n)

    if station_name == "TOOL_BRUSH":
        width_value = float(BRUSH_WIDTH_MM)
        force_value = float(BRUSH_FORCE_N)

    print(f"\n[F1 {label}] {station_name} PICK")
    cc.move_to(station_name, False, point="pick")
    pick_x = [float(v) for v in d.get_current_posx(ref=d.DR_BASE)[0]]
    print(f"[F1 {label}] 실제 PICK posx = {pick_x}")
    actual = cc.grip(width_value, force_value)
    print(f"[F1 {label}] grip 실제 폭 = {actual} mm")
    return pick_x


def f1_tool_return(pick_x, label):
    """F3가 들고 HOME로 복귀한 뒤, 반납 위치를 X/Y → orientation → Z 순으로 정리한다.

    반드시 HOME에서 바로 return_x 전체 POSX로 이동하지 않고,
    X/Y only → 높은 위치에서 반납 orientation 맞춤 → Z만 하강
    → RELEASE → Z만 상승 → HOME orientation 복원 → HOME X/Y 순서를 따른다.
    """
    d = dsr()
    current = [float(v) for v in d.get_current_posx(ref=d.DR_BASE)[0]]
    pick = [float(v) for v in pick_x]
    return_x = pick.copy()               # 🔧 9/22 박진용: 잡을 때와 완전히 같은 깊이 — 실기로 눌리지 않는 걸 확인, +10mm 여유 없앰

    print(f"\n[F1 {label}] 반납 준비: return_x = {return_x}")
    dx = return_x[0] - current[0]
    dy = return_x[1] - current[1]
    if abs(dx) > 1e-6 or abs(dy) > 1e-6:
        cc.move_rel(dx, dy, 0.0, "BASE")
        current = [float(v) for v in d.get_current_posx(ref=d.DR_BASE)[0]]

    high_z = max(current[2], return_x[2] + 60.0)
    orient_high = [return_x[0], return_x[1], high_z, return_x[3], return_x[4], return_x[5]]
    d.amovel(
        orient_high,
        vel=200.0,
        acc=400.0,
        ref=d.DR_BASE,
        mod=d.DR_MV_MOD_ABS,
    )

    dz_down = return_x[2] - high_z
    if abs(dz_down) > 1e-6:
        cc.move_rel(0.0, 0.0, dz_down, "BASE")

    cc.release()
    print(f"[F1 {label}] RELEASE 완료")

    dz_up = abs(high_z - return_x[2])
    if dz_up > 1e-6:
        cc.move_rel(0.0, 0.0, dz_up, "BASE")

    home_ori = [current[0], current[1], high_z, 0.0, 90.0, 0.0]
    d.amovel(
        home_ori,
        vel=200.0,
        acc=400.0,
        ref=d.DR_BASE,
        mod=d.DR_MV_MOD_ABS,
    )

    current_after = [float(v) for v in d.get_current_posx(ref=d.DR_BASE)[0]]
    home_dx = 0.0 - current_after[0]
    home_dy = 0.0 - current_after[1]
    if abs(home_dx) > 1e-6 or abs(home_dy) > 1e-6:
        cc.move_rel(home_dx, home_dy, 0.0, "BASE")

    print(f"[F1 {label}] 반납 완료: HOME X/Y 복귀")


def patch_runtime_config(cfg):
    cell = cfg.setdefault("cell", {})
    limits = cell.setdefault("limits", {})
    motion = cell.setdefault("motion", {})
    stations = cell.setdefault("stations", {})

    limits.update({
        "vel_free_pct": 60,
        "vel_carry_pct": 30,
        "safe_z_mm": 235,
        "contact_limit_n": 2.0,
        "insert_limit_n": 15.0,
        "timeout_s": 10.0,
    })

    motion.update({
        "vel_tcp_max_mm_s": 400.0,
        "acc_tcp_max_mm_s2": 800.0,
        "vel_joint_max_deg_s": 100.0,
        "acc_joint_max_deg_s2": 200.0,
        "move_timeout_s": 30.0,
    })

    stations["HOME"] = {"posj": HOME_J, "posx_z_mm": 215.11, "posx_x_mm": 367.48, "posx_y_mm": 8.09}  # cell.yaml 실측(9/21 --where)
    stations["TOOL_BRUSH"] = {
        "pick": {"posj": TOOL_BRUSH_PICK_J}
    }

    return cell


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--slot",
        choices=("RACK_C1", "RACK_C2"),
        default="RACK_C1",
    )
    ap.add_argument("--step", action="store_true", help="구간마다 Enter 로 확인 (기본: 한 번에)")
    args = ap.parse_args()
    slot = args.slot

    cc.init("rig_cup_scenario_wipe")

    try:
        d = dsr()
        cfg = cc.cfg()
        cell = patch_runtime_config(cfg)
        stations = cell["stations"]

        tcp = d.get_tcp()
        tool_setting = d.get_tool()
        vel_scale = float(cfg["run"]["vel_scale"])

        print("\n" + "=" * 74)
        print("CUP REAL route verification")
        print("=" * 74)
        print("TCP =", repr(tcp))
        print("TOOL =", repr(tool_setting))
        print("vel_scale =", vel_scale)
        cup_preset = cell["presets"]["CUP"]
        print("CUP grip target =", cup_preset["grip_target_mm"], "mm")
        print("CUP force =", cup_preset["grip_force_n"], "N")
        print("RACK via =", cell["rack"]["cup_via"])
        print("=" * 74)

        if tcp != "GripperDA_v1" or tool_setting != "Tool Weight":
            raise RuntimeError(
                "TCP/TOOL 설정 불일치 — DART에서 GripperDA_v1 / Tool Weight를 "
                "선택하고 브링업을 다시 시작한 뒤 재실행"
            )
        if vel_scale > 0.3:
            raise RuntimeError(
                f"실기 동선 검증은 vel_scale 0.3 이하만 허용한다 (현재 {vel_scale})"
            )

        step = 0

        def pose():
            j = [round(float(v), 2) for v in d.get_current_posj()]
            x = [round(float(v), 2) for v in d.get_current_posx(ref=d.DR_BASE)[0]]
            print("현재 J =", j)
            print("현재 X =", x)
            return j, x

        def ask(label):
            nonlocal step
            step += 1
            print("\n" + "=" * 74)
            print(f"[STEP {step}] {label}")
            if not args.step:                                              # 🔧 박진용: 기본은 한 번에 — --step 줄 때만 Enter로 확인
                return
            cmd = input("Enter = 실행 / q = 종료 > ").strip().lower()
            if cmd == "q":
                raise KeyboardInterrupt

        def move(name, carrying, *, kind=None, point=None, label=None):
            ask(label or f"MOVE → {name}")
            up = cc.move_to(name, carrying, kind=kind, point=point)
            pose()
            return float(up or 0.0)

        def rel(dx, dy, dz, label):
            ask(label)
            cc.move_rel(float(dx), float(dy), float(dz), "BASE")
            pose()

        def release(label):
            ask(label)
            cc.release()
            print("RG2 RELEASE 완료")
            pose()

        def grip(width, force, label):
            ask(label)
            got = cc.grip(float(width), float(force))
            print("RG2 실제 폭 =", got)
            pose()
            return got

        move("HOME", False, label="시작 HOME")
        _, home_x = pose()

        release("초기 빈손 RELEASE")

        print("\n" + "=" * 74)
        print("CUP REAL route verification")
        print("PICK → BED → F3 세척 → REGRIP → RINSE → RACK")
        print("[동선 시험 한정] CUP WEIGH/WASTE(E25로 원래 없음)와 RINSE SHAKE(F2 담당)를 생략한다")
        print("=" * 74)

        cup_width = float(cup_preset["grip_target_mm"])
        cup_force = float(cup_preset["grip_force_n"])
        bed = cell["beds"]["SPONGE_BED_C"]["place"]
        rack_cfg = cell["rack"]

        pick_up = move(
            "RET_C",
            False,
            point=1,
            label="HOME → CUP PICK X/Y+방향 동시 이동",
        )
        rel(0.0, 0.0, -pick_up, f"CUP PICK: Z -{pick_up:.2f}")
        grip(cup_width, cup_force, f"CUP GRIP {cup_width:.1f} mm / {cup_force:.0f} N")

        now_z = float(cc.where()[2])
        travel_z = float(bed["approach_posx"][2])
        rel(0.0, 0.0, travel_z - now_z, f"CUP PICK EXIT: Z {travel_z:.1f}")

        bed_up = move(
            "SPONGE_BED_C",
            True,
            point="place",
            label="CUP → BED X/Y+방향 동시 이동",
        )
        rel(0.0, 0.0, -bed_up, f"CUP BED: Z -{bed_up:.2f}")
        release("CUP BED RELEASE")
        for i, xyz in enumerate(bed.get("exit_rel_mm") or [], start=1):
            rel(xyz[0], xyz[1], xyz[2], f"CUP BED EXIT {i}: {xyz}")

        print("\n" + "=" * 74)
        print("[F3 CUP 담당]")
        print("BRUSH 꺼내기 → soap(비틀기·왕복) → CUP WASH → BRUSH 들고 HOME 복귀")
        print("=" * 74)

        # ==================================================
        # F3 (박진용): 솔 꺼내기 → soap → wipe_cup → 솔 들고 HOME
        # (컵은 방금 SPONGE_BED_C 에 놓였다 — 세척 끝나면 F1 이 그 자리에서 다시 잡는다)
        # ==================================================
        ask("F3: BRUSH 픽업 준비")
        brush_pick_x = f1_tool_pick(
            "TOOL_BRUSH",
            BRUSH_WIDTH_MM,
            BRUSH_FORCE_N,
            "BRUSH",
        )

        got = cc.grip_width()
        if got <= BRUSH_WIDTH_MM + 0.3:
            # 목표 폭(BRUSH_WIDTH_MM)이 손잡이 실측(8mm)보다 타이트해서(박진용 9/22 3차),
            # 잡았으면 손잡이에 막혀 목표보다 큰 값에서 멈춘다 — 목표 근처(±0.3mm)면 막힌 것 없이
            # 그대로 닫힌 것 = 빈손(수세미와 같은 판정 방식).
            raise RuntimeError(
                f"솔을 못 잡았다(폭 {got:.1f} mm = 목표 {BRUSH_WIDTH_MM:g} mm 까지 그대로 닫힘) — 멈춘다"
            )

        ask("F3: soap (그 자리에서 좌우 비틀기 3회 → Z 왕복 2회 → HOME)")
        r_soap = wipe.soap(3, 'CUP')
        print(f"[F3] soap: {r_soap.code}")
        pose()
        if not r_soap.ok:
            raise RuntimeError(f"soap {r_soap.code} — 여기서 멈춘다")

        ask("F3: wipe_cup (HOME → 컵 위 → 컵 세척 → HOME)")
        r = wipe.wipe_cup()
        print(
            f"[F3] wipe_cup: {r.code} · {r.duration_s:.1f} s · "
            f"삽입 깊이 {r.insert_depth_mm:.1f} mm · 힘 로그 {r.force_log_path}"
        )
        pose()
        if not r.ok:
            raise RuntimeError(f"wipe_cup {r.code} — 여기서 멈춘다")

        # F1: HOME 에서 BRUSH 반납
        # XY → 방향 → Z↓ → RELEASE → Z↑ → 방향 → HOME XY
        f1_tool_return(brush_pick_x, "BRUSH")

        move(
            "SPONGE_BED_C",
            False,
            point="regrip",
            label="CUP BED REGRIP",
        )
        grip(cup_width, cup_force, f"CUP REGRIP {cup_width:.1f} mm / {cup_force:.0f} N")

        entry_z = float(rack_cfg["cup_entry_z_mm"])
        now_z = float(cc.where()[2])
        if abs(now_z - entry_z) > 1e-6:
            rel(0.0, 0.0, entry_z - now_z, f"CUP REGRIP EXIT: Z {entry_z:.1f}")

        rinse_up = move(
            "RINSE",
            True,
            kind="CUP",
            label="CUP → RINSE 접근",
        )
        print(f"[F2 RINSE/DIP 인계] 수직 하강 가능량 = {rinse_up:.1f} mm")
        ask("F2 DIP 완료 · RINSE 접근점(z=150) 복귀")
        print("[CUP RINSE SHAKE 생략]")

        now_z = float(cc.where()[2])
        rel(0.0, 0.0, entry_z - now_z, f"RINSE EXIT: Z {entry_z:.1f}")

        stations["RACK_C_VIA_TEST"] = dict(rack_cfg["cup_via"])
        move(
            "RACK_C_VIA_TEST",
            True,
            label="RINSE EXIT → RACK CUP VIA",
        )

        rack_up = move(
            slot,
            True,
            label=f"RACK CUP VIA → {slot} 접근",
        )
        rel(0.0, 0.0, -rack_up, f"{slot}: Z -{rack_up:.2f}")
        release(f"{slot} CUP RELEASE")
        for i, xyz in enumerate(rack_cfg["slots"][slot].get("exit_rel_mm") or [], start=1):
            rel(xyz[0], xyz[1], xyz[2], f"{slot} EXIT {i}: {xyz}")

        move("HOME", False, label="RACK EXIT → HOME")

        print("=" * 74)
        print("REAL CUP 동선 시험 완료")
        print("=" * 74)
        return 0

    except KeyboardInterrupt:
        print("\n사용자 중단 — 자동 HOME/RELEASE 하지 않음.")
        return 130

    finally:
        cc.shutdown()


if __name__ == "__main__":
    sys.exit(main())
