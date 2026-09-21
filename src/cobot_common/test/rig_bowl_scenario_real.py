#!/usr/bin/env python3
import argparse
import sys

import cobot_common as cc
from cobot_common.bootstrap import dsr

HOME_J = [0.0, 0.0, 90.0, 0.0, 90.0, 0.0]
WASTE_J = [-180.0, 0.0, 90.0, 0.0, 90.0, 0.0]

RET_B_APPROACH_J = [0.0, 23.0, 68.4, 0.0, 88.3, 0.0]
RET_B_GRIP_J = [0.0, 26.5, 81.6, 0.0, 72.0, 0.0]

BED_B_APPROACH_X = [419.7, 17.5, 202.1, 128.2, 180.0, -52.0]
BED_B_PLACE_X = [419.7, 17.5, 54.4, 128.0, 180.0, -52.2]

TOOL_SPONGE_PICK_J = [-40.45, 2.5, 111.5, 0.0, 66.06, -220.37]
TOOL_BRUSH_PICK_J = [-28.7, 17.0, 84.0, -0.12, 79.0, -28.7]

RINSE_B_APPROACH_X = [205.8, -445.7, 150.0, 123.2, 180.0, 123.0]

RACK_B_VIA_J = [-8.0, 0.0, 107.8, 86.2, 101.5, -108.0]

RACKS = {
    "RACK_B1": {
        "approach_posx": [301.4, 606.2, 407.8, 92.76, 95.0, 7.4],
        "posx": [301.4, 606.2, 307.8, 92.76, 95.0, 7.4],
        "exit_rel_mm": [[0.0, -25.0, 0.0], [0.0, 0.0, 100.0]],
    },
    "RACK_B2": {
        "approach_posx": [303.24, 549.1, 399.3, 93.8, 96.4, 6.0],
        "posx": [303.24, 549.1, 299.3, 93.8, 96.4, 6.0],
        "exit_rel_mm": [[0.0, -25.0, 0.0], [0.0, 0.0, 100.0]],
    },
}

BOWL_EXPECTED_MM = 2.15
BOWL_ZERO_MM = 10.58
BOWL_TOL_MM = 0.6
BOWL_FORCE_N = 20.0
BOWL_CMD_MM = BOWL_ZERO_MM + max(
    0.0,
    BOWL_EXPECTED_MM - 2.0 * BOWL_TOL_MM
)

SPONGE_WIDTH_MM = 30.0
SPONGE_FORCE_N = 40.0

# BRUSH grip 값은 SDD의 기존 초안값이며, 최신 cell.yaml 확정값은 아니다.
# production cell.yaml 은 건드리지 않고, 실기 전에 값이 다시 확정되면 이 자리를 교체한다.
BRUSH_WIDTH_MM = 22.0
BRUSH_FORCE_N = 30.0


def f1_tool_pick(station, width_mm, force_n, label):
    """F1: 툴 홀더에서 꽂는 위치까지 이동해 실제 pick_x를 읽고 grip까지 수행.

    - F1 은 grip 까지만 한다.
    - Z 상승 / HOME 복귀는 여기서 하지 않는다.
    - BOWL/SPONGE 는 검증값을 그대로 유지한다.
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
    return_x = pick.copy()
    return_x[2] += 10.0

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
    beds = cell.setdefault("beds", {})
    rack = cell.setdefault("rack", {})
    rack_slots = rack.setdefault("slots", {})

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

    stations["HOME"] = {"posj": HOME_J}
    stations["WASTE"] = {"BOWL": {"posj": WASTE_J}}
    stations["RET_B_APPROACH_TEST"] = {"posj": RET_B_APPROACH_J}
    stations["RET_B_GRIP_TEST"] = {"posj": RET_B_GRIP_J}
    stations["TOOL_SPONGE"] = {
        "pick": {"posj": TOOL_SPONGE_PICK_J}
    }
    stations["TOOL_BRUSH"] = {
        "pick": {"posj": TOOL_BRUSH_PICK_J}
    }
    stations["RACK_B_VIA_TEST"] = {"posj": RACK_B_VIA_J}

    beds["SPONGE_BED_B"] = {
        "place": {
            "approach_posx": BED_B_APPROACH_X,
            "posx": BED_B_PLACE_X,
        }
    }

    for name, spec in RACKS.items():
        rack_slots[name] = dict(spec)

    return cell


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--kind",
        choices=("BOWL", "CUP"),
        default="BOWL",
        help="BOWL 또는 CUP 시나리오 선택",
    )
    ap.add_argument(
        "--slot",
        choices=("RACK_B1", "RACK_B2", "RACK_C1", "RACK_C2"),
        default=None,
    )
    args = ap.parse_args()

    if args.kind == "BOWL":
        allowed_slots = {"RACK_B1", "RACK_B2"}
        default_slot = "RACK_B1"
    else:
        allowed_slots = {"RACK_C1", "RACK_C2"}
        default_slot = "RACK_C1"

    slot = args.slot or default_slot
    if slot not in allowed_slots:
        raise ValueError(
            f"{args.kind} 시나리오에서는 {sorted(allowed_slots)} 만 허용합니다. "
            f"요청값={slot}"
        )

    cc.init("rig_bowl_scenario_real")

    try:
        d = dsr()
        cfg = cc.cfg()
        cell = patch_runtime_config(cfg)
        stations = cell["stations"]

        tcp = d.get_tcp()

        print("\n" + "=" * 74)
        print("BOWL REAL route verification")
        print("=" * 74)
        print("TCP =", repr(tcp))
        print("vel_scale =", cfg["run"]["vel_scale"])
        print("BOWL raw grip target =", round(BOWL_CMD_MM, 2), "mm")
        print("BOWL force =", BOWL_FORCE_N, "N")
        print("TOOL_VIA = NOT USED")
        print("F3 wash pose = NOT USED")
        print("RACK via =", RACK_B_VIA_J)
        print("=" * 74)

        if not tcp:
            raise RuntimeError(
                "현재 TCP가 비어 있음 — DART에서 RG2 TCP 선택 후 재실행"
            )

        step = 0

        def pose():
            j = [
                round(float(v), 2)
                for v in d.get_current_posj()
            ]
            x = [
                round(float(v), 2)
                for v in d.get_current_posx(ref=d.DR_BASE)[0]
            ]
            print("현재 J =", j)
            print("현재 X =", x)
            return j, x

        def ask(label):
            nonlocal step
            step += 1
            print("\n" + "=" * 74)
            print(f"[STEP {step}] {label}")
            cmd = input(
                "Enter = 실행 / q = 종료 > "
            ).strip().lower()
            if cmd == "q":
                raise KeyboardInterrupt

        def move(name, carrying, *, kind=None, point=None, label=None):
            ask(label or f"MOVE → {name}")
            up = cc.move_to(
                name,
                carrying,
                kind=kind,
                point=point,
            )
            pose()
            return float(up or 0.0)

        def move_fast(
            name,
            carrying,
            *,
            kind=None,
            point=None,
            label=None,
        ):
            """
            넓은 공간에서 이미 확인한 이동만 빠르게.
            global vel_scale=0.3은 유지하고,
            이 이동 동안만 해당 pct를 100으로 올린다.
            """
            limits = cell["limits"]
            key = "vel_carry_pct" if carrying else "vel_free_pct"
            old_pct = limits[key]

            try:
                limits[key] = 100
                print(
                    f"[FAST] {key}: {old_pct} → 100 "
                    f"(vel_scale={cfg['run']['vel_scale']})"
                )

                return move(
                    name,
                    carrying,
                    kind=kind,
                    point=point,
                    label=label,
                )

            finally:
                limits[key] = old_pct

        def rel(dx, dy, dz, label):
            ask(label)
            cc.move_rel(
                float(dx),
                float(dy),
                float(dz),
                "BASE",
            )
            pose()

        def release(label):
            ask(label)
            cc.release()
            print("RG2 RELEASE 완료")
            pose()

        def grip(width, force, label):
            ask(label)
            got = cc.grip(
                float(width),
                float(force),
            )
            print("RG2 실제 폭 =", got)
            pose()
            return got

                def home_keep_j6(carrying, label, fast=False):
            """
            기존 HOME 이동 경로는 그대로 사용한다.

            HOME_J:
                J1~J5 = 기존 HOME 값
                J6    = 현재 값 유지

            즉 HOME XYZ 직선이동으로 바꾸지 않는다.
            """
            j_now = [
                float(v)
                for v in d.get_current_posj()
            ]

            home_j = [
                float(v)
                for v in HOME_J
            ]

            # J6만 현재 자세 유지
            home_j[5] = j_now[5]

            stations["HOME_KEEP_J6_TEST"] = {
                "posj": home_j
            }

            print(
                f"[HOME] J1~J5 HOME / "
                f"J6 유지 = {j_now[5]:.2f}°"
            )

            if fast:
                return move_fast(
                    "HOME_KEEP_J6_TEST",
                    carrying,
                    label=label,
                )

            return move(
                "HOME_KEEP_J6_TEST",
                carrying,
                label=label,
            )

 move("HOME", False, label="시작 HOME")
        _, home_x = pose()

        release("초기 빈손 RELEASE")

        if args.kind == "CUP":
            print("\n" + "=" * 74)
            print("[CUP / TOOL_BRUSH] F1 공용 함수: pick + grip only")
            print("F3: 꺼내기 → CUP WASH → HOME 복귀")
            print("F1: HOME에서 XY → orientation → Z down → release → Z up → HOME orientation → HOME XY")
            print("=" * 74)

            ask("BRUSH PICK 준비")
            brush_pick_x = f1_tool_pick(
                "TOOL_BRUSH",
                BRUSH_WIDTH_MM,
                BRUSH_FORCE_N,
                "BRUSH",
            )

            print()
            print("=" * 74)
            print("[F3 CUP 담당]")
            print("BRUSH 꺼내기 → CUP WASH → HOME 복귀")
            print("=" * 74)
            input("F3가 BRUSH 들고 HOME 복귀했으면 Enter > ")

            # F1: HOME 에서 반납 순서
            # XY 이동 → orientation 맞춤 → Z 하강 → release → Z 상승 → HOME orientation → HOME XY
            f1_tool_return(brush_pick_x, "BRUSH")

            print("\n" + "=" * 74)
            print("CUP TOOL_BRUSH 동선 시험 완료")
            print("=" * 74)
            return 0

        move(
            "RET_B_APPROACH_TEST",
            False,
            label="RET_B 접근",
        )

        move(
            "RET_B_GRIP_TEST",
            False,
            label="RET_B 실제 GRIP 위치",
        )

        grip(
            BOWL_CMD_MM,
            BOWL_FORCE_N,
            f"BOWL GRIP raw={BOWL_CMD_MM:.2f}mm / 20N",
        )

        # BOWL PICK 높이에서 WEIGH.BOWL의 실제 Z까지만 이동한다.
        # 고정 +100을 쓰지 않는다.
        now_x = [
            float(v)
            for v in d.get_current_posx(ref=d.DR_BASE)[0]
        ]
        weigh_x = stations["WEIGH"]["BOWL"]["posx"]
        weigh_dz = float(weigh_x[2]) - now_x[2]

        rel(
            0.0,
            0.0,
            weigh_dz,
            f"BOWL → WEIGH: Z {weigh_dz:+.1f} "
            f"(target z={float(weigh_x[2]):.1f})",
        )

        home_keep_j6(
            True,
            label="WEIGH → HOME",
        )

        move_fast(
            "WASTE",
            True,
            kind="BOWL",
            label="HOME → WASTE BOWL [FAST]",
        )

        print("[F2 SHAKE 구간 생략]")

        home_keep_j6(
            True,
            label="WASTE → HOME [FAST]",
            fast=True,
        )

        bed_up = move(
            "SPONGE_BED_B",
            True,
            point="place",
            label="HOME → SPONGE_BED_B 접근",
        )

        print(
            f"BED 수직 하강량 = {bed_up:.1f} mm "
            "(예상 147.7)"
        )

        rel(
            0, 0, -bed_up,
            f"BED Z -{bed_up:.1f}",
        )

        release("BOWL BED RELEASE")

        rel(
            0, 0, bed_up,
            f"BED Z +{bed_up:.1f} 퇴피",
        )

        # ==================================================
        # F1 : SPONGE PICK + GRIP 까지
        # ==================================================
        # ==================================================
        # F1: SPONGE PICK + GRIP 까지
        # ==================================================
        sponge_pick_x = f1_tool_pick(
            "TOOL_SPONGE",
            SPONGE_WIDTH_MM,
            SPONGE_FORCE_N,
            "SPONGE",
        )

        print()
        print("=" * 74)
        print("[F3 BOWL 담당]")
        print("SPONGE 꺼내기 → BOWL WASH → SPONGE 들고 HOME 복귀")
        print("=" * 74)

        input("F3가 SPONGE 들고 HOME 복귀했으면 Enter > ")

        # ==================================================
        # F1: HOME에서 SPONGE 반납
        # XY → 방향 → Z↓ → RELEASE → Z↑ → 방향 → HOME XY
        # ==================================================
        f1_tool_return(
            sponge_pick_x,
            "SPONGE",
        )

        bed_up = move(
            "SPONGE_BED_B",
            False,
            point="place",
            label="HOME → BOWL REGRIP 접근",
        )

        rel(
            0, 0, -bed_up,
            f"BOWL REGRIP Z -{bed_up:.1f}",
        )

        grip(
            BOWL_CMD_MM,
            BOWL_FORCE_N,
            "BOWL REGRIP",
        )

        rel(
            0, 0, bed_up,
            f"BOWL REGRIP 후 Z +{bed_up:.1f}",
        )

        home_keep_j6(
            True,
            label="BED → HOME [FAST]",
            fast=True,
        )

        _, home_x = pose()

        rinse = RINSE_B_APPROACH_X

        rel(
            rinse[0] - home_x[0],
            rinse[1] - home_x[1],
            0,
            "RINSE: HOME 높이 유지 → X/Y만 이동",
        )

        rinse_high = list(rinse)
        rinse_high[2] = home_x[2]

        stations["RINSE_HIGH_TEST"] = {
            "posx": rinse_high
        }

        move(
            "RINSE_HIGH_TEST",
            True,
            label="RINSE 높은 위치에서 방향 맞춤",
        )

        dz = rinse[2] - home_x[2]

        rel(
            0, 0, dz,
            "RINSE: Z만 하강",
        )

        print("[F2 RINSE/DIP 구간 생략]")

        rel(
            0, 0, -dz,
            "RINSE EXIT: Z 먼저 상승",
        )

        now_x = [
            float(v)
            for v in d.get_current_posx(ref=d.DR_BASE)[0]
        ]

        home_ori_high = [
            now_x[0],
            now_x[1],
            now_x[2],
            home_x[3],
            home_x[4],
            home_x[5],
        ]

        stations["RINSE_HOME_ORI_TEST"] = {
            "posx": home_ori_high
        }

        move(
            "RINSE_HOME_ORI_TEST",
            True,
            label="RINSE 높은 위치에서 HOME 방향 복원",
        )

        now_x = [
            float(v)
            for v in d.get_current_posx(ref=d.DR_BASE)[0]
        ]

        rel(
            home_x[0] - now_x[0],
            home_x[1] - now_x[1],
            0,
            "RINSE EXIT: HOME X/Y로 복귀",
        )

        home_keep_j6(
            True,
            label="RINSE → HOME",
        )

        move(
            "RACK_B_VIA_TEST",
            True,
            label="HOME → RACK_B_VIA",
        )

        rack_up = move(
            slot,
            True,
            label=f"RACK_B_VIA → {slot} 접근",
        )

        # --------------------------------------------------
        # BOWL은 현재 위를 보고 있으므로
        # RACK_B1에서는 내려가기 전에 J6을 180° 뒤집는다.
        #
        # +180 / -180은 최종 자세가 동일하므로
        # 손목이 0°에 더 가까워지는 방향을 자동 선택한다.
        # --------------------------------------------------
        if slot == "RACK_B1":
            j_now = [
                float(v)
                for v in d.get_current_posj()
            ]

            j6_before = j_now[5]

            plus_final = j6_before + 180.0
            minus_final = j6_before - 180.0

            if abs(plus_final) <= abs(minus_final):
                flip_delta = 180.0
            else:
                flip_delta = -180.0

            print(
                f"RACK_B1 접근 J6 = {j6_before:.2f}°"
            )
            print(
                f"BOWL 뒤집기: J6 {flip_delta:+.0f}° "
                f"→ 예상 {j6_before + flip_delta:.2f}°"
            )

            cc.move_joint_rel(
                6,
                flip_delta,
                carrying=True,
            )

            j_after = [
                float(v)
                for v in d.get_current_posj()
            ]

            print(
                f"RACK_B1 FLIP 완료 J6 = "
                f"{j_after[5]:.2f}°"
            )

        print(
            f"{slot} 수직 하강량 = "
            f"{rack_up:.1f} mm"
        )

        rel(
            0, 0, -rack_up,
            f"{slot}: Z -{rack_up:.1f}",
        )

        release(
            f"{slot} BOWL RELEASE"
        )

        for i, xyz in enumerate(
            RACKS[slot]["exit_rel_mm"],
            start=1,
        ):
            rel(
                xyz[0],
                xyz[1],
                xyz[2],
                f"{slot} EXIT {i}: {xyz}",
            )

        move(
            "HOME",
            False,
            label="RACK EXIT → HOME",
        )

        print("\n" + "=" * 74)
        print("REAL BOWL 동선 시험 완료")
        print("=" * 74)

        return 0

    except KeyboardInterrupt:
        print(
            "\n사용자 중단 — 자동 HOME/RELEASE 하지 않음."
        )
        return 130

    finally:
        cc.shutdown()


if __name__ == "__main__":
    sys.exit(main())
