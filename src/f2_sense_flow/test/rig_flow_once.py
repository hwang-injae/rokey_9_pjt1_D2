"""flow 의 process_one 을 **용기 1개**에 실기로 — HMI·서비스 없이 터미널에서 (민범진 · 9/22 · INT-F2 = FLOW-04).

    soc && python3 src/f2_sense_flow/test/rig_flow_once.py check                              # 로봇 없이: 어떤 모듈이 진짜/가짜인지 · 빈 껍데기
    soc && PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_flow_once.py --kind BOWL --mock f3          # 그릇 1개 — F3(세제·닦기)만 가짜
    soc && python3 src/f2_sense_flow/test/rig_flow_once.py --kind BOWL --mock f3 -n 3                           # 연속 3개 (반납 구역에 3개)
    python3 src/f2_sense_flow/test/rig_flow_once.py --kind BOWL --mock f1,f2,f3 --no-robot                       # 대본만 (로봇 없이)

왜 flow_node 가 아니라 이것인가: flow_node 는 /flow/start 를 기다리고 plan(그릇 2 · 컵 2) 전체를 돈다. 첫 실기는 **그릇 1개**를
    같은 코드(flow.py process_one — PICK → WEIGH → SEAT → SOAP → WIPE → RINSE → RACK · 실패 정책 · 기록)로 돌리되, 멈추면 사람이
    터미널에서 재개/중단을 고른다. 통합의 "뼈대" 는 따로 만들지 않는다 — 제품 경로(flow.py) 가 뼈대다(INT-F2 · SKEL-01 논의).
    끝나면 flow_node + HMI 로 같은 것을 한 번 더 돌리면 L3(INT-3a) 다.

🚨 f1.tool 이 아직 빈 껍데기다(F1-03 · 황인재): --mock 에 f3 을 넣지 않으면 진짜 닦기가 **툴 없이** 그릇 바닥을 누르러 간다 → check 가 막는다.
🚨 실패로 PAUSED 되면 로봇은 그 자리(정책대로 후퇴 뒤). Enter = 그 단계부터 다시 · a = 이 용기를 접고 격리(HOME → 격리 → HOME) · q = 끝(안 움직임).
파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import sys
import time

import cobot_common as cc
from cobot_common.config import parse_use_mock
from f2_sense_flow.flow import Flow, Signals, load_features
from f2_sense_flow.preflight import require_controller

FEATURES = ('f1', 'f2', 'f3')


class HumanSignals(Signals):
    """PAUSED 에서 사람이 고른다 — flow.wait_resume 이 take('abort') → take('resume') 순으로 묻는다."""

    def __init__(self, log):
        super().__init__()
        self.log = log
        self._asked = False

    def take(self, name):
        if name == 'abort' and not self._asked:
            self._asked = True
            self.log.warn('⏸ PAUSED — Enter = 그 단계부터 다시 · a = 이 용기 접고 격리 · q = 끝')
            try:
                ans = input().strip().lower()
            except EOFError:
                ans = 'q'
            if ans == 'q':
                raise KeyboardInterrupt
            self.raise_('abort' if ans == 'a' else 'resume')
        v = super().take(name)
        if v:
            self._asked = False
        return v


def _make_flow(cfg, log, features, robot):
    """flow_node.main 과 **같은 주입** — 후퇴·힘 끄기·정지·중단 예외."""
    events = []
    f = Flow(cfg, log, features=features,
             publish_event=lambda ev: (events.append(ev), log.info(f'📣 event {ev["result"]} · {ev["code"]} · {ev["duration_s"]} s')),
             safe_retreat=cc.safe_retreat if robot else None,
             force_off=cc.force_off if robot else None,
             no_retreat_errors=(cc.MoveIncomplete,) if robot else (),
             is_paused=cc.is_paused if robot else None,
             halt=cc.halt if robot else None,
             clear_halt=cc.clear_halt if robot else None,
             halt_errors=(cc.MotionHalted,) if robot else ())
    return f, events


def main():
    ap = argparse.ArgumentParser(description='flow.process_one 을 용기 1개에 실기로')
    ap.add_argument('which', nargs='?', default='run', choices=['run', 'check'])
    ap.add_argument('--kind', default='BOWL', choices=['BOWL', 'CUP'])
    ap.add_argument('--zone', help='반납 구역 (기본 flow.plan 의 그 종류 첫 구역)')
    ap.add_argument('--mock', default='f3', help='가짜로 돌릴 기능, 쉼표 (기본 f3 — 툴·닦기는 가짜)')
    ap.add_argument('-n', type=int, default=1, help='연속 몇 개 (반납 구역에 그만큼)')
    ap.add_argument('--no-robot', action='store_true', help='전부 가짜일 때만')
    a = ap.parse_args()
    use_mock = [m for m in parse_use_mock(a.mock) if m in FEATURES] if a.mock else []
    robot = not (a.no_robot or set(FEATURES) <= set(use_mock))
    if a.which == 'check':
        robot = False                                            # check 는 로봇·드라이버 없이 설정만 본다
    if a.no_robot and robot:
        sys.exit('--no-robot 은 --mock f1,f2,f3 일 때만')

    cc.init('rig_flow_once', robot=robot)
    log = cc.io_node().get_logger()
    try:
        if robot:
            require_controller(cc.io_node(), cc.cfg(), log)          # TS-07
        features = load_features(use_mock, log)
        cfg = cc.cfg()
        f, events = _make_flow(cfg, log, features, robot)
        zone = a.zone or next(p['zone'] for p in f.plan if p['kind'] == a.kind)

        if a.which == 'check' or ('f3' not in use_mock and 'f1' not in use_mock):
            # 🚨 f1.tool 이 빈 껍데기면 SOAP 에서 "툴 잡았다" 고 거짓 대답 → 진짜 f3 가 툴 없이 누른다
            from cobot_api import ToolResult
            tool_fn = getattr(features['f1'], 'tool', None)
            stub = False
            if 'f1' not in use_mock and callable(tool_fn):
                try:
                    r = tool_fn('SPONGE', 'PICK') if not robot else None   # robot 이면 실제로 부르지 않는다 — 빈 껍데기는 아래 check 로
                    stub = isinstance(r, ToolResult) and r.ok and r.width_mm == 0.0
                except Exception:                     # noqa: BLE001 — 진짜 구현은 로봇 없이 예외
                    stub = False
            if a.which == 'check':
                log.info(f'모듈: ' + ' · '.join(f'{k}={"가짜" if k in use_mock else "진짜"}' for k in FEATURES) + f' · robot={robot}')
                log.info(f'plan {f.plan} · weigh_kinds {f.weigh_kinds} · zone {zone} · rack {f.rack_order.get(a.kind)}')
                log.info('빈 껍데기 확인은 rig_int12.py check 로 (pick · rack_place · tool)')
                return
            if stub:
                sys.exit('🚨 f1.tool 이 빈 껍데기인데 f3 이 진짜다 — 툴 없이 닦으러 간다. --mock f3 으로 돌린다')

        if robot:
            log.info('E15 — 먼저 HOME 으로 간다')
            cc.force_off()
            cc.move_to('HOME', False)
        sig = HumanSignals(log)
        f.zone_id, f.kind = zone, a.kind
        for i in range(1, a.n + 1):
            log.info(f'━━ 용기 {i}/{a.n} · {a.kind} · {zone} · 팔레트 {f._next_slot()} ━━')
            t0 = time.monotonic()
            outcome = f.process_one(sig)
            log.info(f'━━ 결과 {outcome} · {time.monotonic() - t0:.1f} s · 완료 그릇 {f.done_bowl} 컵 {f.done_cup} 격리 {f.isolated} · 기록 {f.records.path}')
            if outcome != 'go_on':
                break
        log.info('event 요약: ' + ', '.join(f'{e["result"]}({e["code"]})' for e in events))
    except KeyboardInterrupt:
        log.warn('Ctrl+C / q — 로봇은 그 자리에 선다')
    finally:
        cc.shutdown()


if __name__ == '__main__':
    main()
