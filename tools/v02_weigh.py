#!/usr/bin/env python3
"""V-02 하중 측정 정밀도 — 측정·기록·분석 도구 (F2 민범진)

무엇을 하나
  로봇이 물건을 잡은 채 가만히 있는 상태에서 하중을 여러 번 읽어 CSV로 남기고,
  자세별·상태별 흔들림과 "넣기 전↔후 차이"를 자동으로 계산해 판정한다.

🚨 이 스크립트는 로봇을 움직이지 않는다. 하중을 읽기만 한다.
   자세 변경·그리퍼 개폐는 사람이 직접 한다 (AGENTS.md 절대규칙 1).

측정 구조 (docs/03_설계_SDD.md §3.1 weigh(n))
  1회 측정 = reset_workpiece_weight → settle 초 정지 → get_workpiece_weight × samples 평균
  한 묶음  = 그 1회 측정을 trials 번 반복
  전체     = (빈 그릇 / 대용품 넣은 그릇) × (자세 P1..Pn)

사용
  python3 tools/v02_weigh.py                     # 기본값 (자세 3 · 10회 · 5샘플)
  python3 tools/v02_weigh.py --poses 2 --trials 5
  python3 tools/v02_weigh.py --expected 100      # 기준 무게를 알 때: 오차도 계산
  python3 tools/v02_weigh.py --fake              # 로봇 없이 동작 확인 (가짜 값)
"""
import argparse
import csv
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

# 기본값 — docs/03_설계_SDD.md §6 f2.yaml 과 맞춘 값. 전부 실행 인자로 덮어쓸 수 있다.
DEFAULTS = {
    "namespace": "dsr01",   # 브링업 네임스페이스
    "poses": 3,             # 자세 수 (기준 + 변경 2회)
    "trials": 10,           # 자세·상태마다 측정 횟수
    "samples": 5,           # 1회 측정에 읽는 횟수 (f2.yaml weigh_samples)
    "settle_s": 0.5,        # 읽기 전 정지 시간
    "timeout_s": 5.0,       # 서비스 응답 대기 상한
    "tolerance_g": 20.0,    # 판정 기준 (SR-04 / V-02)
}
STATES = [("empty", "빈 그릇"), ("loaded", "대용품 넣은 그릇")]
REPO_ROOT = Path(__file__).resolve().parent.parent


class WeightReader:
    """실기 로봇에서 하중을 읽는다. --fake 면 가짜 값을 만든다."""

    def __init__(self, namespace, timeout_s, fake=False):
        self.fake = fake
        self.timeout_s = timeout_s
        if fake:
            import random
            self._rand = random.Random(20260918)
            self._fake_base = 0.0
            return

        import rclpy
        from rclpy.node import Node
        from dsr_msgs2.srv import GetWorkpieceWeight, ResetWorkpieceWeight, GetCurrentPosj

        rclpy.init()
        self._rclpy = rclpy
        self._node = Node("v02_weigh")
        prefix = f"/{namespace.strip('/')}/force"
        self._get = self._node.create_client(GetWorkpieceWeight, f"{prefix}/get_workpiece_weight")
        self._reset = self._node.create_client(ResetWorkpieceWeight, f"{prefix}/reset_workpiece_weight")
        self._GetReq = GetWorkpieceWeight.Request
        self._ResetReq = ResetWorkpieceWeight.Request
        # 자세 기록용 — 읽기 전용. 없으면 경고만 하고 측정은 계속한다.
        self._posj = self._node.create_client(GetCurrentPosj, f"/{namespace.strip('/')}/aux_control/get_current_posj")
        self._PosjReq = GetCurrentPosj.Request
        if not self._posj.wait_for_service(timeout_sec=1.0):
            self._node.get_logger().warn("get_current_posj 서비스 없음 — 자세 기록 없이 진행합니다")
            self._posj = None
        for name, cli in (("get_workpiece_weight", self._get), ("reset_workpiece_weight", self._reset)):
            if not cli.wait_for_service(timeout_sec=timeout_s):
                raise SystemExit(
                    f"[오류] 서비스를 찾지 못했습니다: {prefix}/{name}\n"
                    f"  · 로봇 브링업이 떠 있는지 확인: ros2 service list | grep workpiece\n"
                    f"  · 네임스페이스가 다르면 --ns 로 지정하세요 (지금: {namespace})"
                )

    def _call(self, client, request):
        future = client.call_async(request)
        self._rclpy.spin_until_future_complete(self._node, future, timeout_sec=self.timeout_s)
        if not future.done():
            raise RuntimeError("서비스 응답 시간 초과")
        return future.result()

    def reset(self):
        if self.fake:
            return True
        return bool(self._call(self._reset, self._ResetReq()).success)

    def read(self):
        """하중 1회 읽기 (g)."""
        if self.fake:
            return self._fake_base + self._rand.gauss(0, 2.0)
        res = self._call(self._get, self._GetReq())
        if not res.success:
            raise RuntimeError("get_workpiece_weight 실패 (success=false)")
        if res.weight < 0:
            raise RuntimeError(f"측정값이 음수입니다({res.weight}) — 드라이버 오류")
        return float(res.weight)

    def read_posj(self):
        """현재 관절 각도를 읽는다(도). 못 읽으면 None. 로봇을 움직이지 않는다."""
        if self.fake:
            return [0.0, -12.5, 95.3, 0.0, 97.2, 0.0]
        if self._posj is None:
            return None
        try:
            res = self._call(self._posj, self._PosjReq())
            return [round(float(v), 2) for v in res.pos] if res.success else None
        except Exception:
            return None

    def set_fake_base(self, value):
        if self.fake:
            self._fake_base = value

    def close(self):
        if not self.fake:
            self._node.destroy_node()
            self._rclpy.shutdown()


def measure_once(reader, samples, settle_s):
    """1회 측정 = reset → 정지 → samples 번 읽어 평균. (평균, 원시값 목록) 반환."""
    reader.reset()
    time.sleep(settle_s)
    raw = [reader.read() for _ in range(samples)]
    return statistics.fmean(raw), raw


def describe(values):
    """평균·표준편차·최소·최대·최대편차."""
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    spread = max(values) - min(values)
    worst = max(abs(v - mean) for v in values)
    return {"mean": mean, "sd": sd, "min": min(values), "max": max(values),
            "spread": spread, "worst": worst}


def run(args):
    reader = WeightReader(args.ns, args.timeout, fake=args.fake)
    rows, groups, poses_seen = [], {}, {}
    total = len(STATES) * args.poses
    step = 0
    try:
        for state_key, state_label in STATES:
            if state_key == "loaded":
                print("\n" + "=" * 62)
                print("  ▶ 이제 그릇에 잔반 대용품을 넣어 주세요 (로봇은 그대로 잡고 있음)")
                print("=" * 62)
                input("  넣었으면 엔터 ▮ ")
                reader.set_fake_base(120.0)   # --fake 일 때만 의미 있음
            for pose in range(1, args.poses + 1):
                step += 1
                print(f"\n[{step}/{total}] {state_label} · 자세 P{pose}")
                if state_key == "empty" and pose == 1:
                    print("  자세를 잡고, 로봇이 완전히 멈춘 뒤 엔터를 누르세요.")
                else:
                    print("  자세를 바꾸고, 로봇이 완전히 멈춘 뒤 엔터를 누르세요.")
                    if state_key == "loaded":
                        print("  ⚠️  그릇이 기울면 대용품이 쏟아집니다. 기울기를 작게.")
                input("  준비되면 엔터 ▮ ")

                posj = reader.read_posj()
                posj_txt = "[" + ", ".join(f"{v:g}" for v in posj) + "]" if posj else ""
                if posj:
                    print(f"  자세 기록  posj {posj_txt}")
                poses_seen.setdefault(pose, posj_txt)

                values = []
                for t in range(1, args.trials + 1):
                    mean, raw = measure_once(reader, args.samples, args.settle)
                    values.append(mean)
                    rows.append({
                        "ts": datetime.now().isoformat(timespec="seconds"),
                        "state": state_key, "pose": f"P{pose}", "trial": t,
                        "mean_g": round(mean, 2),
                        "raw_g": " ".join(f"{v:.2f}" for v in raw),
                        "posj": posj_txt,
                    })
                    print(f"    {t:2d}/{args.trials}  {mean:8.2f} g")

                stats = describe(values)
                groups[(state_key, pose)] = stats
                print(f"  → 평균 {stats['mean']:.2f} g · 표준편차 {stats['sd']:.2f} g "
                      f"· 최대편차 {stats['worst']:.2f} g")
    except KeyboardInterrupt:
        print("\n중단되었습니다. 지금까지 측정한 값은 저장합니다.")
    finally:
        reader.close()
    return rows, groups, poses_seen


def report(groups, args, poses_seen=None):
    print("\n" + "=" * 62)
    print("  V-02 결과")
    print("=" * 62)

    poses = sorted({p for (_, p) in groups})
    if not poses:
        print("  측정값이 없습니다.")
        return None

    header = "  " + " " * 14 + "".join(f"{'P'+str(p):>12}" for p in poses)
    print(header)
    for state_key, state_label in STATES:
        cells = "".join(
            f"{groups[(state_key, p)]['mean']:>10.1f} g" if (state_key, p) in groups else f"{'-':>12}"
            for p in poses)
        print(f"  {state_label:<14}{cells}")

    # 흔들림 (같은 자세·같은 상태 안에서)
    worst_sd = max(s["sd"] for s in groups.values())
    worst_spread = max(s["spread"] for s in groups.values())

    # 자세 간 차이 (같은 상태, 자세만 다름)
    pose_gap = {}
    for state_key, state_label in STATES:
        means = [groups[(state_key, p)]["mean"] for p in poses if (state_key, p) in groups]
        if len(means) > 1:
            pose_gap[state_label] = max(means) - min(means)

    # 넣기 전↔후 차이 (자세별)
    deltas = {p: groups[("loaded", p)]["mean"] - groups[("empty", p)]["mean"]
              for p in poses if ("loaded", p) in groups and ("empty", p) in groups}
    if deltas:
        cells = "".join(f"{deltas[p]:>10.1f} g" if p in deltas else f"{'-':>12}" for p in poses)
        print(f"  {'차이(후-전)':<14}{cells}")

    print("-" * 62)
    print(f"  측정 흔들림   표준편차 최대 {worst_sd:.2f} g · 최대-최소 폭 {worst_spread:.2f} g")
    for label, gap in pose_gap.items():
        print(f"  자세 간 차이  {label}: {gap:.2f} g")
    if deltas:
        gaps = list(deltas.values())
        print(f"  넣기 전↔후    평균 {statistics.fmean(gaps):.2f} g "
              f"(자세별 편차 {max(gaps) - min(gaps):.2f} g)")

    print("-" * 62)
    tol = args.tolerance
    verdict_ok = worst_spread <= tol
    print(f"  ① 흔들림 ≤ {tol:.0f} g ?        "
          f"{'✅ PASS' if verdict_ok else '❌ FAIL'}  (실측 {worst_spread:.2f} g)")

    if deltas:
        gap_mean = statistics.fmean(deltas.values())
        margin = gap_mean / worst_spread if worst_spread > 0 else float("inf")
        can_50 = gap_mean > worst_spread and worst_spread <= 50
        print(f"  ② 잔반 50 g 구분 가능 ?     "
              f"{'✅ 가능' if can_50 else '⚠️  확인 필요'}  "
              f"(차이 {gap_mean:.1f} g = 흔들림의 {margin:.1f}배)")

    if args.expected is not None:
        state_key = "loaded" if ("loaded", poses[0]) in groups else "empty"
        errs = [abs(groups[(state_key, p)]["mean"] - args.expected) for p in poses
                if (state_key, p) in groups]
        print(f"  ③ 기준 {args.expected:.0f} g 대비 오차   최대 {max(errs):.2f} g  "
              f"{'✅' if max(errs) <= tol else '❌'}")

    print("-" * 62)
    if verdict_ok:
        print(f"  → f2.yaml  leftover_threshold_g: 50  유지 검토 가능")
    else:
        print(f"  → 흔들림이 기준을 넘음. SDD §9.9 범위 방어대로 "
              f"leftover_threshold_g 를 100 으로 올리고 대용품을 무겁게.")
    if ("empty", poses[0]) in groups:
        print(f"  → f2.yaml  empty_weight_g 실측값(P1): "
              f"{groups[('empty', poses[0])]['mean']:.0f} g")
    if poses_seen:
        print("\n  자세 기록 (f2.yaml WEIGH 좌표 후보)")
        for pose in sorted(poses_seen):
            if poses_seen[pose]:
                print(f"    P{pose}  posj {poses_seen[pose]}")
    print("=" * 62)
    return {"worst_sd": worst_sd, "worst_spread": worst_spread,
            "pose_gap": pose_gap, "deltas": deltas}


def save_csv(rows, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ts", "state", "pose", "trial", "mean_g", "raw_g", "posj"])
        writer.writeheader()
        writer.writerows(rows)


def main():
    d = DEFAULTS
    p = argparse.ArgumentParser(description="V-02 하중 측정 정밀도 — 측정·분석")
    p.add_argument("--ns", default=d["namespace"], help=f"로봇 네임스페이스 (기본 {d['namespace']})")
    p.add_argument("--poses", type=int, default=d["poses"], help=f"자세 수 (기본 {d['poses']})")
    p.add_argument("--trials", type=int, default=d["trials"], help=f"자세·상태마다 측정 횟수 (기본 {d['trials']})")
    p.add_argument("--samples", type=int, default=d["samples"], help=f"1회 측정에 읽는 횟수 (기본 {d['samples']})")
    p.add_argument("--settle", type=float, default=d["settle_s"], help=f"읽기 전 정지 시간 초 (기본 {d['settle_s']})")
    p.add_argument("--timeout", type=float, default=d["timeout_s"], help=f"서비스 응답 대기 상한 초 (기본 {d['timeout_s']})")
    p.add_argument("--tolerance", type=float, default=d["tolerance_g"], help=f"판정 기준 g (기본 {d['tolerance_g']})")
    p.add_argument("--expected", type=float, default=None, help="기준 무게를 아는 경우 g (선택)")
    p.add_argument("--out", default=None, help="CSV 저장 경로 (기본 docs/test_logs/<날짜>_V-02_raw.csv)")
    p.add_argument("--fake", action="store_true", help="로봇 없이 가짜 값으로 동작 확인")
    args = p.parse_args()

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = REPO_ROOT / "docs" / "test_logs" / f"{datetime.now():%Y%m%d}_V-02_raw.csv"

    print("=" * 62)
    print("  V-02 하중 측정 정밀도" + ("   [가짜 값 모드 — 로봇 미사용]" if args.fake else ""))
    print("=" * 62)
    print(f"  자세 {args.poses} · 상태 {len(STATES)} · 측정 {args.trials}회 · 1회당 {args.samples}샘플")
    print(f"  총 측정 {args.poses * len(STATES) * args.trials}회 (읽기 "
          f"{args.poses * len(STATES) * args.trials * args.samples}번)")
    print("  🚨 이 스크립트는 로봇을 움직이지 않습니다. 자세·그리퍼는 직접 조작하세요.")
    print("=" * 62)

    rows, groups, poses_seen = run(args)
    if rows:
        save_csv(rows, out_path)
    summary = report(groups, args, poses_seen)
    if rows:
        try:
            shown = out_path.relative_to(Path.cwd())
        except ValueError:
            shown = out_path
        print(f"\n  원시 측정값 {len(rows)}행 저장: {shown}")
        print("  기록 문서에 위 결과표를 옮겨 적으세요: docs/test_logs/<날짜>_V-02.md")
    return 0 if summary else 1


if __name__ == "__main__":
    sys.exit(main())
