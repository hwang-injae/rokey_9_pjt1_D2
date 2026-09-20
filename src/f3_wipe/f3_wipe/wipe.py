"""F3 접촉 닦기 — 박진용 (IRD v3.0 §5, SDD §5.4).

flow_node(메인 프로그램)나 test/rig_f3.py 가 cobot_common.init() 뒤 **메인 스레드**에서 부르는
평범한 함수다(SDD §3.2). 이름·인자·반환은 cobot_api.F3Api 그대로이고, 실패는 예외가 아니라
Result.fail(code) 로 돌려준다. 숫자는 전부 params.yaml 의 f3 절 · cell.yaml 에서 읽는다(AGENTS 규칙 6).

시작 전제: 용기는 스펀지 홈에 안착돼 있고(F1 place) 툴을 쥔 상태(F1 tool PICK).
끝난 뒤: 툴을 쥔 채 안전 높이. 툴 반납·재파지는 flow 가 F1 을 부른다.

🔸 툴 파지 기준(9/20 확정): 수세미·솔 모두 세척부 위에 손잡이가 있고, **그리퍼 끝을 세척부 윗면에 닿게** 쥔다
   → 그리퍼 끝에서 툴 끝까지 = 세척부 높이 = params.yaml 의 f3.wipe_bowl.tool.clean_h_mm(수세미 45) · f3.wipe_cup.tool.clean_h_mm(솔 95).
   내려가는 거리·삽입 깊이·닦는 반경은 이 값과 cell.yaml 좌표로 계산한다 — 길이를 코드에 적지 않는다.

PKG-01 골격: 지금은 약속된 반환 타입만 돌려준다(로봇 동작 없음, V-20 재료).
본문은 F3-02(wipe_bowl) · F3-03(soap · wipe_cup) 에서 cobot_common 의 motion(S) · force(P) 로 채운다.
실측 근거는 docs/test_logs/20260918_CELL-02a_용기치수측정.md.
"""
import csv
import os
import time

from cobot_api import Result, WipeBowlResult, WipeCupResult

FORCE_LOG_HEADER = ('t', 'fx', 'fy', 'fz', 'target')   # SDD §4.2 힘 로그 열


def soap(count: int) -> Result:
    """툴 든 채 세제 수조(SOAP)에 count 회 담근다(모션만, 물 없음). — F3-03.

    절차: move_to('SOAP', carrying=True) → count 회 [f3.soap.depth_mm 하강 → hold_s 유지 → 상승]
    → 안전 높이. 접촉 동작이 아니라 힘 감시는 없지만 cell.limits.timeout_s 는 지킨다(넘으면 TIMEOUT).
    """
    return Result()


def wipe_bowl() -> WipeBowlResult:
    """그릇 안쪽을 수세미 툴로 힘제어(목표 힘 유지) 닦기. 상한 초과 FORCE_LIMIT. — F3-02.

    절차(V-03 로 확정한 방식 — 그릇 크기를 정해 두지 않는다):
      move_to('SPONGE_BED_B', carrying=True) → 남은 높이만큼 move_rel 하강
      → contact_down(바닥 접촉 — 시작 힘 대비 변화량으로 판정)
      → force_on('z', f3.wipe_bowl.target_force_n)
      → 손목을 좌우로 비틀며(슥삭) 나선으로 반경을 넓혀 간다
      → **명령한 반경을 못 따라가면(순응 때문에 벽에 막힘) 벽** → 그 자리에서 반대 방향으로 크게 2바퀴(벽을 눌러 옆면 닦기)
      → force_off → 곧게 상승(하강과 같은 속도) → safe_retreat.
    최대 반경 = (받을 수 있는 가장 큰 그릇 반지름) − f3.wipe_bowl.tool.d_mm / 2. 가장 작은 그릇 = 수세미와 같은 크기.
    도는 동안 force_check 로 힘을 보고 로그로 남긴다. limit_n 초과 → force_off·safe_retreat·FORCE_LIMIT,
    duration_s 초과 → TIMEOUT. 힘은 Z, 이동은 XY 라 동시에 가능(중급2 "폴리싱").
    🚨 벽 판정을 힘 크기로 하지 않는다 — 가운데에서 바깥으로 갈 때 마찰이 안쪽으로 걸려 벽과 구분되지 않는다(9/20 실기).
    """
    return WipeBowlResult()


def wipe_cup() -> WipeCupResult:
    """컵 안에 솔 삽입(힘 감시) → 회전 + Z 스트로크. 상한 초과 FORCE_LIMIT. — F3-03.

    절차: move_to('SPONGE_BED_C', carrying=True) → contact_down(삽입, cell.limits.insert_limit_n,
    최대 깊이 f3.wipe_cup.insert_depth_mm ≤ f3.wipe_cup.tool.clean_h_mm) — 목표 깊이 전에 힘 상한에 걸리면 safe_retreat·FORCE_LIMIT
    → cycles 회 [툴 Z 축 회전 ±rot_deg + Z 스트로크 stroke_mm] (limit_n 감시) → 컵 밖으로 곧게 상승 → safe_retreat.
    🚨 순응제어 중에는 관절 이동(movej) 불가(중급2, 오류 2.1903) → 회전은 툴 기준 직교 이동으로 하거나
    회전하는 동안 순응을 끈다. 솔은 95 mm 세척부 위에 별도의 파지용 손잡이가 있어
    세척부 전체를 삽입할 수 있다. 바닥 접촉 전 힘 상한과 실제 삽입 깊이는 V-10에서 확정한다.
    """
    return WipeCupResult()


def _save_force_log(samples, log_dir):
    """힘 샘플 [(t, fx, fy, fz, target), ...] 을 CSV 로 남기고 경로를 돌려준다(SDD §4.2).

    파일 이름 force_YYYYMMDD_HHMMSS.csv. log_dir 는 상대경로로 받는다(AGENTS 규칙 7).
    """
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, time.strftime('force_%Y%m%d_%H%M%S.csv'))
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(FORCE_LOG_HEADER)
        w.writerows(samples)
    return path
