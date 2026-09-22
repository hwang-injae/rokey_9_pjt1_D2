#!/usr/bin/env python3
"""컵 한 바퀴 실기 — F1 실제 제품 함수(f1_handling.pick·place·tool·rack_place) + F3 자리에 soap·wipe_cup (박진용 9/22 5차).

    cd ~/cobot1/rokey_9_pjt1_D2 && soc && PREWASH_VEL_SCALE=0.3 python3 src/f3_wipe/test/rig_cup_scenario_wipe.py
    cd ~/cobot1/rokey_9_pjt1_D2 && soc && PREWASH_VEL_SCALE=0.3 python3 src/f3_wipe/test/rig_cup_scenario_wipe.py --step

🔧 9/22 5차: 예전엔 F1 파지·이송 로직을 이 파일에 손으로 베껴 뒀는데, F1 쪽(한석형·황인재·민범진) 좌표·방식이
   바뀔 때마다(9/22 하루에 결정 E29 컵 벽 집기·E30 컵도 무게까지 포함해 여러 번) 여기도 매번 다시 맞춰야 했다.
   `f1_handling.pick()`·`place()`·`tool()`·`rack_place()`가 이미 **cell.yaml 만 보고 동작하는 진짜 제품
   함수**(PR #74)라, 이제 그걸 그대로 부른다 — F1 쪽 설정이 바뀌어도 이 파일은 안 바꿔도 된다.
   좌표·자리 이름은 전부 cell.yaml 에 있다(patch 없음). 그릇 파일과는 완전히 분리된 별개 파일이다.
"""
import argparse
import sys

import cobot_common as cc
from cobot_common.bootstrap import dsr
from cobot_api import BRUSH, CUP, PICK, RETURN
from f1_handling import handling as f1
from f3_wipe import wipe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", choices=("RACK_C1", "RACK_C2"), default="RACK_C1")
    ap.add_argument("--step", action="store_true", help="구간마다 Enter 로 확인 (기본: 한 번에)")
    args = ap.parse_args()
    slot = args.slot

    cc.init("rig_cup_scenario_wipe")

    try:
        d = dsr()
        cfg = cc.cfg()
        tcp = d.get_tcp()
        tool_setting = d.get_tool()
        vel_scale = float(cfg["run"]["vel_scale"])

        print("\n" + "=" * 74)
        print("CUP REAL route verification (F1 제품 함수 · 9/22 5차, E29 벽 집기 반영)")
        print("=" * 74)
        print("TCP =", repr(tcp))
        print("TOOL =", repr(tool_setting))
        print("vel_scale =", vel_scale)
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
            if not args.step:
                return
            cmd = input("Enter = 실행 / q = 종료 > ").strip().lower()
            if cmd == "q":
                raise KeyboardInterrupt

        ask("시작 HOME")
        cc.move_to("HOME", False)
        pose()

        ask("초기 빈손 RELEASE")
        cc.release()
        pose()

        # ==================================================
        # F1 (한석형/민범진 제품 함수): 반납 구역 컵 집기 — E29(벽 집기·폭 판정)는 cell.yaml 프리셋만 보고 자동 적용
        # ==================================================
        ask("F1: pick(RET_C, CUP)")
        r = f1.pick("RET_C", CUP)
        print(f"[F1] pick: {r.code} · attempts={r.attempts} · 폭={r.width_mm:.2f}mm")
        pose()
        if not r.ok:
            raise RuntimeError(f"pick {r.code} — 여기서 멈춘다")

        # F2 WEIGH/WASTE(E30 · 컵도 무게 측정하는 걸로 되돌아감)는 생략 — F1+F3 연동만 본다
        print("[F2 WEIGH/WASTE 구간 생략 — F1+F3 연동만 본다]")

        ask("F1: place(SPONGE_BED_C, CUP)")
        rp = f1.place("SPONGE_BED_C", CUP)
        print(f"[F1] place: {rp.code}")
        pose()
        if not rp.ok:
            raise RuntimeError(f"place {rp.code} — 여기서 멈춘다")

        # ==================================================
        # F1: 솔 픽업
        # ==================================================
        ask("F1: tool(BRUSH, PICK)")
        rt = f1.tool(BRUSH, PICK)
        print(f"[F1] tool PICK: {rt.code} · 폭={rt.width_mm:.2f}mm")
        pose()
        if not rt.ok:
            raise RuntimeError(f"tool PICK {rt.code} — 여기서 멈춘다")

        # ==================================================
        # F3 (박진용): soap → wipe_cup
        # ==================================================
        print()
        print("=" * 74)
        print("[F3 CUP 담당] soap(비틀기·왕복) → CUP WASH")
        print("=" * 74)

        ask("F3: soap (그 자리에서 좌우 비틀기 3회 → Z 왕복 2회 → 컵 위)")
        r_soap = wipe.soap(3, "CUP")
        print(f"[F3] soap: {r_soap.code}")
        pose()
        if not r_soap.ok:
            raise RuntimeError(f"soap {r_soap.code} — 여기서 멈춘다")

        ask("F3: wipe_cup (컵 위 → 컵 세척 → 그 높이로)")
        r_wipe = wipe.wipe_cup()
        print(
            f"[F3] wipe_cup: {r_wipe.code} · {r_wipe.duration_s:.1f} s · "
            f"삽입 깊이 {r_wipe.insert_depth_mm:.1f} mm · 힘 로그 {r_wipe.force_log_path}"
        )
        pose()
        if not r_wipe.ok:
            raise RuntimeError(f"wipe_cup {r_wipe.code} — 여기서 멈춘다")

        # ==================================================
        # F1: 솔 반납 → 컵 재파지 → 랙 적재
        # ==================================================
        ask("F1: tool(BRUSH, RETURN)")
        rr = f1.tool(BRUSH, RETURN)
        print(f"[F1] tool RETURN: {rr.code}")
        pose()
        if not rr.ok:
            raise RuntimeError(f"tool RETURN {rr.code} — 여기서 멈춘다")

        ask("F1: pick(SPONGE_BED_C, CUP) — 컵 재파지")
        r2 = f1.pick("SPONGE_BED_C", CUP)
        print(f"[F1] regrip: {r2.code} · 폭={r2.width_mm:.2f}mm")
        pose()
        if not r2.ok:
            raise RuntimeError(f"regrip {r2.code} — 여기서 멈춘다")

        print("[F2 RINSE 담금 구간 생략 — F1+F3 연동만 본다]")

        ask(f"F1: rack_place({slot}, CUP)")
        r3 = f1.rack_place(slot, CUP)
        print(f"[F1] rack_place: {r3.code}")
        pose()
        if not r3.ok:
            raise RuntimeError(f"rack_place {r3.code} — 여기서 멈춘다")

        ask("HOME 복귀")
        cc.move_to("HOME", False)
        pose()

        print("\n" + "=" * 74)
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
