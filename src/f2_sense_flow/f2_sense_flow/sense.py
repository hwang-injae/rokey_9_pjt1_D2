# -*- coding: utf-8 -*-
"""F2 무게·털기·헹굼 — 민범진 · 모듈 f2_sense_flow.sense

약속(정본) : src/cobot_api/cobot_api/contracts.py 의 F2Api
설계       : docs/02_인터페이스_IRD.md §4 · docs/03_설계_SDD.md §5.3

🚧 PKG-01 단계 — 지금은 **껍데기**다.
   이름·인자·반환만 약속대로 맞춰 두고, 속은 F2-01(9/20)에서 채운다.
   껍데기라도 flow_node 가 부를 수 있어서, 순서·연결을 먼저 시험할 수 있다(V-20).

속을 채울 때 지킬 것 (SDD §3.2 · AGENTS.md §3):
  · 로봇은 `import cobot_common as cc` 를 통해서만 부른다. DSR_ROBOT2 직접 import 금지
  · 숫자(임계·횟수·진폭)는 코드에 쓰지 않고 cc.cfg()['f2'] 에서 읽는다
  · 실패는 예외를 던지지 않고 Result.fail(코드) 로 돌려준다
  · 이 함수들은 flow_node 의 메인 스레드에서만 불린다. 여기서 노드를 만들지 않는다
"""

# cobot_api = 팀이 정한 "함수 약속" 패키지(황인재 관리). 우리는 읽어 쓰기만 한다.
# Result        : 모든 기능 함수의 공통 반환 (ok: 성공여부, code: 실패코드 문자열)
# WeighResult   : Result + weight_g (측정 무게)
# LeftoverResult: Result + 털기 전/후 무게, 반복 횟수
from cobot_api import Result, WeighResult, LeftoverResult

# 🚧 F2-01 에서 아래 줄의 주석을 푼다 (지금은 cobot_common 이 아직 없다 — 황인재 INF-02a)
# import cobot_common as cc


def weigh(kind: str) -> WeighResult:
    """무게를 잰다.

    kind : 'BOWL'(그릇) 또는 'CUP'(컵)  ← IRD §2 의 문자열 그대로
    반환 : WeighResult (ok, code, weight_g)

    F2-01 에서 채울 내용 (SDD §5.3):
        cc.move_to('WEIGH', True) → 0.5초 정지 → cc.weigh(n) 로 N회 평균
        0점 재설정(reset)은 **선택 동작** — 응답 3초 넘으면 포기하고 그냥 진행(TS-03)
        판정은 '측정값 − 빈 용기 기준값'이라 고정 옵셋은 저절로 상쇄된다
    """
    return WeighResult(weight_g=0.0)      # 🚧 껍데기: 항상 0 g · ok=True


def leftover_loop(kind: str, max_rounds: int) -> LeftoverResult:
    """잔반이 남았으면 털고 다시 재는 것을 반복한다(폐루프).

    kind       : 'BOWL' / 'CUP'
    max_rounds : 최대 몇 번까지 털어볼지
    반환       : LeftoverResult (ok, code, weight_before_g, weight_after_g, rounds)

    F2-01 에서 채울 내용 (SDD §5.3):
        weigh → 임계(기본 50 g) 넘으면 → move_to('WASTE') → shake('WASTE') → 다시 weigh
        max_rounds 를 넘겨도 계속 넘으면 Result.fail(LEFTOVER_REMAIN)
        임계 미만이면 통과(본세척은 식기세척기 담당)
    """
    return LeftoverResult(weight_before_g=0.0, weight_after_g=0.0, rounds=0)   # 🚧 껍데기


def shake(mode: str, count: int, kind: str) -> Result:
    """흔들어 턴다.

    mode  : 'WASTE'(잔반 털기) 또는 'RINSE'(물 털기)
    count : 흔들 횟수
    kind  : 'BOWL' / 'CUP'  ← 파지 힘 프리셋을 고르려고 받는다
    반환  : Result

    F2-01 에서 채울 내용 (IRD §4 · 9/18 V-17 결과):
        🚨 시작할 때 cc.grip_level(kind, 'HOLD')  ← 흔들 때는 더 꽉 잡는다
           끝날 때 cc.grip_level(kind, 'NORMAL')  ← 반드시 되돌린다
        J5/J6 관절 왕복, 진폭·속도는 cc.cfg()['f2']['shake'][mode]
        동작 전후 그리퍼 폭을 비교해 변했으면(미끄러짐) Result.fail(GRIP_FAIL)
    """
    return Result()                        # 🚧 껍데기: ok=True, code='OK'


def dip(station: str, count: int, kind: str) -> Result:
    """수조에 담갔다 뺀다.

    station : 'RINSE'(헹굼 수조)
    count   : 담글 횟수
    kind    : 'BOWL' / 'CUP'
    반환    : Result

    F2-01 에서 채울 내용 (SDD §5.3):
        🚨 담그는 동안 강한 파지(HOLD), 끝나면 NORMAL 로 되돌린다
        수조 상공 → depth_mm 하강 → hold_s 유지 → 상승
        깊이·시간은 cc.cfg()['f2']['dip'][station]
    """
    return Result()                        # 🚧 껍데기
