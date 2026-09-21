#!/usr/bin/env bash
# 9/21 저녁 F2 실기 — 한 단계씩 부르는 묶음 (민범진)
#
#   bash src/f2_sense_flow/test/run_tonight.sh <단계>
#
# 단계 목록은 인자 없이 부르면 나온다. 🚨 로봇이 움직인다 — 한 단계씩 확인하며 부른다.
# 절차·합격 기준은 docs/test_logs/20260921_저녁_F2실기_절차와기록_민범진.md
set -u
R=src/f2_sense_flow/test/rig_f2.py

say() { printf '\n\033[1;36m── %s\033[0m\n' "$*"; }
ask() { printf '\033[1;33m%s\033[0m\n' "$*"; read -r -p '   준비됐으면 Enter (그만두려면 Ctrl+C) '; }

case "${1:-}" in
  check)      # 로봇 없이 — 지금 바로 해도 된다
    say '출발 전 점검 (로봇을 움직이지 않는다)'
    python3 - <<'PYEOF'
from cobot_common.config import load
c = load(); st = c['cell']['stations']; pr = c['cell']['presets']; f2 = c['f2']
bad = []
print('자세')
for name in ('HOME', 'WEIGH', 'WASTE'):
    node = st.get(name) or {}
    if 'posj' in node or 'posx' in node:
        print(f'  {name:6} OK  (공용 1개)')
    else:
        for k in ('BOWL', 'CUP'):
            ok = bool(node.get(k)); print(f'  {name:6} {k:4} {"OK" if ok else "없다 <<<"}')
            if not ok: bad.append(f'{name}.{k}')
print('프리셋')
need = {'BOWL': ('grip_width_mm', 'grip_zero_mm', 'grip_force_n', 'hold_force_n', 'width_tol_mm'),
        'CUP':  ('grip_target_mm', 'grip_zero_mm', 'grip_force_n')}
for k, keys in need.items():
    miss = [x for x in keys if (pr.get(k) or {}).get(x) is None]
    print(f'  {k:5} {"OK" if not miss else "비었다 " + str(miss) + " <<<"}')
    bad += [f'presets.{k}.{x}' for x in miss]
print(f'  그릇 목표 {pr["BOWL"]["grip_width_mm"]} mm · {pr["BOWL"]["grip_force_n"]}/{pr["BOWL"]["hold_force_n"]} N'
      f'   컵 고정 {pr["CUP"]["grip_target_mm"]} mm · {pr["CUP"]["grip_force_n"]} N')
w = f2['shake']['WASTE']
print(f'털기\n  J{w["joint"]} · {w["amp_deg"]}deg (상한 {f2["limits"]["max_amp_deg"]}) · {w["period_s"]} s · {w["cycles"]}회')
if w['amp_deg'] > f2['limits']['max_amp_deg']: bad.append('shake.WASTE.amp_deg 가 상한을 넘는다')
print(f'무게\n  빈 용기 기준값(오늘 다시 잰다) 그릇 {f2["empty_weight_g"]["BOWL"]} g · 컵 {f2["empty_weight_g"]["CUP"]} g')
print('\n' + ('점검 통과 — 로봇만 있으면 된다' if not bad else '>>> 막힌 것: ' + ', '.join(bad)))
raise SystemExit(1 if bad else 0)
PYEOF
    [ $? -ne 0 ] && exit 1
    say '함수가 도는지 (드라이버 없이 반환만)'
    python3 "$R" weigh --kind BOWL -n 1 --no-robot 2>&1 | grep -E 'Result\(' | tail -1
    echo '→ code=ROBOT_ERROR 가 나오면 정상이다 (진짜 로봇이 없으니까)'
    ;;

  bowl-weigh) # ① V-02 그릇
    say '① V-02 — 빈 그릇 기준값'
    python3 "$R" release || exit 1
    ask '빈 그릇을 그리퍼 사이에 대 주세요 (벽을 세로로)'
    python3 "$R" grip --kind BOWL || exit 1
    ask '폭이 2.15 ± 0.6 mm 인가? 경고가 떴으면 Ctrl+C'
    python3 "$R" weigh --kind BOWL -n 3 || exit 1
    ask '쥔 그릇이 뒤 용기·공급 구조에 닿지 않는지 보세요'
    python3 "$R" empty --kind BOWL -n 10
    echo '→ 폭(최대−최소) ≤ 20 g 이면 합격. 중앙값을 params.yaml f2.empty_weight_g.BOWL 에'
    ;;

  cup-lift)   # ② 🔴 E19 숙제 — 78 mm 로 들리는가
    say '② 컵 78 mm — 실제로 들리는지 (E19 가 남긴 숙제)'
    python3 "$R" release || exit 1
    ask '컵을 바닥에 세워 두고 그리퍼 사이에 오게 하세요 (손으로 들지 않는다)'
    python3 "$R" grip --kind CUP || exit 1
    echo '→ 손으로 살짝 당겨 보세요: 딸려 오나? 눌렸나? 놓으면 모양이 돌아오나?'
    ;;

  cup-weigh)  # ② 컵 무게 (E19 ③)
    say '② 컵 무게 — 30 g 보다 무거운가'
    python3 "$R" empty --kind CUP -n 10
    echo '→ 30 g 보다 가벼우면 털다 놓쳐도 모른다(E19 ③). 그대로 적고 PM 에 보고'
    ;;

  bowl-shake) # ③ V-07 그릇
    say '③ V-07 — 털기 (그릇)'
    python3 "$R" release || exit 1
    ask '빈 그릇을 대 주세요'
    python3 "$R" grip --kind BOWL || exit 1
    ask '잔반통 위로 갑니다 (HOME 을 거쳐서 — E15). 주변을 비우세요'
    python3 "$R" shake --mode WASTE --kind BOWL -n 10
    echo '→ 멈춤(충돌 감지) 0/10 이면 합격. 멈추면 f2.shake.WASTE.amp_deg 15 → 12 → 10'
    ;;

  cup-shake)  # ③ V-07 컵 — 🔴 오늘의 핵심
    say '③ V-07 — 털기 (컵) · 5 N 으로 버티는가 (E19 ②)'
    python3 "$R" release || exit 1
    ask '컵을 대 주세요'
    python3 "$R" grip --kind CUP || exit 1
    ask '🚨 컵이 날아갈 수 있습니다. 주변을 비우고 한 발 물러서세요'
    python3 "$R" shake --mode WASTE --kind CUP -n 10
    echo '→ 낙하가 1 이라도 나면 멈추고 PM 에 보고 (컵 파지 방식을 다시 정해야 한다)'
    ;;

  open)       # 언제든 — 그리퍼 열기
    say '그리퍼 열기'
    echo '🚨 용기를 손으로 받을 준비를 하세요'
    ask ''
    python3 "$R" release
    ;;

  *)
    cat <<'HELP'
9/21 저녁 F2 실기 — 단계

  check        로봇 없이 확인 (지금 바로 해도 된다)
  ─────────────────────────────────────────────
  bowl-weigh   ① V-02   빈 그릇 기준값        10회
  cup-lift     ② 🔴     컵 78 mm 로 들리는가   E19 숙제
  cup-weigh    ②        컵 무게 (30 g 넘는지)  10회
  bowl-shake   ③ V-07   털기 (그릇)           10회
  cup-shake    ③ 🔴     털기 (컵)             10회 · 오늘의 핵심
  ─────────────────────────────────────────────
  open         그리퍼 열기 (언제든)

  bash src/f2_sense_flow/test/run_tonight.sh bowl-weigh

🚨 V-16(최소 힘 찾기)은 cell.yaml 의 hold_force_n 을 바꿔 가며 bowl-shake 를 반복한다.
   절차: docs/test_logs/20260921_저녁_F2실기_절차와기록_민범진.md
HELP
    ;;
esac
