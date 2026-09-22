#!/usr/bin/env python3
"""그릇 한 바퀴 실기 — F1 실제 제품 함수(f1_handling.pick·place·tool·rack_place) + F3 자리에 soap·wipe_bowl (박진용 9/22 5차).

    cd ~/cobot1/rokey_9_pjt1_D2 && soc && PREWASH_VEL_SCALE=0.3 python3 src/f3_wipe/test/rig_bowl_scenario_wipe.py
    cd ~/cobot1/rokey_9_pjt1_D2 && soc && PREWASH_VEL_SCALE=0.3 python3 src/f3_wipe/test/rig_bowl_scenario_wipe.py --step

🔧 9/22 5차: 예전엔 F1 파지·이송 로직을 이 파일에 손으로 베껴 뒀는데, F1 쪽(한석형·황인재·민범진) 좌표·방식이
   바뀔 때마다(9/22 하루에만 세 번) 여기도 매번 다시 맞춰야 했다. `f1_handling.pick()`·`place()`·`tool()`·
   `rack_place()`가 이미 **cell.yaml 만 보고 동작하는 진짜 제품 함수**(PR #74)라, 이제 그걸 그대로 부른다 —
   F1 쪽 설정이 바뀌어도 이 파일은 안 바꿔도 된다. 좌표·자리 이름은 전부 cell.yaml 에 있다(patch 없음).
"""
import argparse
import sys

import cobot_common as cc
from cobot_common.bootstrap import dsr
from cobot_api import BOWL, PICK, RETURN, SPONGE
from f1_handling import handling as f1
from f3_wipe import wipe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", choices=("RACK_B1", "RACK_B2"), default="RACK_B1")
    ap.add_argument("--step", action="store_true", help="구간마다 Enter 로 확인 (기본: 한 번에)")
    args = ap.parse_args()
    slot = args.slot

    cc.init("rig_bowl_scenario_wipe")

    try:
        d = dsr()
        cfg = cc.cfg()
        tcp = d.get_tcp()
        tool_setting = d.get_tool()
        vel_scale = float(cfg["run"]["vel_scale"])

        print("\n" + "=" * 74)
        print("BOWL REAL route verification (F1 제품 함수 · 9/22 5차)")
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
        # F1 (한석형/민범진 제품 함수): 반납 구역 그릇 집기
        # ==================================================
        ask("F1: pick(RET_B, BOWL)")
        r = f1.pick("RET_B", BOWL)
        print(f"[F1] pick: {r.code} · attempts={r.attempts} · 폭={r.width_mm:.2f}mm")
        pose()
        if not r.ok:
            raise RuntimeError(f"pick {r.code} — 여기서 멈춘다")

        # F2 WEIGH/WASTE(E30 · 잔반 버리기)는 생략 — F1+F3 연동만 본다
        print("[F2 WEIGH/WASTE 구간 생략 — F1+F3 연동만 본다]")

        ask("F1: place(SPONGE_BED_B, BOWL)")
        rp = f1.place("SPONGE_BED_B", BOWL)
        print(f"[F1] place: {rp.code}")
        pose()
        if not rp.ok:
            raise RuntimeError(f"place {rp.code} — 여기서 멈춘다")

        # ==================================================
        # F1: 수세미 픽업
        # ==================================================
        ask("F1: tool(SPONGE, PICK)")
        rt = f1.tool(SPONGE, PICK)
        print(f"[F1] tool PICK: {rt.code} · 폭={rt.width_mm:.2f}mm")
        pose()
        if not rt.ok:
            raise RuntimeError(f"tool PICK {rt.code} — 여기서 멈춘다")

        # ==================================================
        # F3 (박진용): soap → wipe_bowl
        # ==================================================
        print()
        print("=" * 74)
        print("[F3 BOWL 담당] soap(비틀기·왕복) → BOWL WASH")
        print("=" * 74)

        ask("F3: soap (그 자리에서 좌우 비틀기 3회 → Z 왕복 2회 → HOME)")
        r_soap = wipe.soap(3, "BOWL")
        print(f"[F3] soap: {r_soap.code}")
        pose()
        if not r_soap.ok:
            raise RuntimeError(f"soap {r_soap.code} — 여기서 멈춘다")

        ask("F3: wipe_bowl (HOME → 그릇 닦기 → HOME)")
        r_wipe = wipe.wipe_bowl()
        print(
            f"[F3] wipe_bowl: {r_wipe.code} · {r_wipe.duration_s:.1f} s · "
            f"평균 힘 {r_wipe.force_mean_n:.1f} N · 힘 로그 {r_wipe.force_log_path}"
        )
        pose()
        if not r_wipe.ok:
            raise RuntimeError(f"wipe_bowl {r_wipe.code} — 여기서 멈춘다")

        # ==================================================
        # F1: 수세미 반납 → 그릇 재파지 → 랙 적재
        # ==================================================
        ask("F1: tool(SPONGE, RETURN)")
        rr = f1.tool(SPONGE, RETURN)
        print(f"[F1] tool RETURN: {rr.code}")
        pose()
        if not rr.ok:
            raise RuntimeError(f"tool RETURN {rr.code} — 여기서 멈춘다")

        ask("F1: pick(SPONGE_BED_B, BOWL) — 그릇 재파지")
        r2 = f1.pick("SPONGE_BED_B", BOWL)
        print(f"[F1] regrip: {r2.code} · 폭={r2.width_mm:.2f}mm")
        pose()
        if not r2.ok:
            raise RuntimeError(f"regrip {r2.code} — 여기서 멈춘다")

        print("[F2 RINSE 담금 구간 생략 — F1+F3 연동만 본다]")

        ask(f"F1: rack_place({slot}, BOWL)")
        r3 = f1.rack_place(slot, BOWL)
        print(f"[F1] rack_place: {r3.code}")
        pose()
        if not r3.ok:
            raise RuntimeError(f"rack_place {r3.code} — 여기서 멈춘다")

        ask("HOME 복귀")
        cc.move_to("HOME", False)
        pose()

        print("\n" + "=" * 74)
        print("REAL BOWL 동선 시험 완료")
        print("=" * 74)
        return 0

    except KeyboardInterrupt:
        print("\n사용자 중단 — 자동 HOME/RELEASE 하지 않음.")
        return 130

    finally:
        cc.shutdown()


if __name__ == "__main__":
    sys.exit(main())
