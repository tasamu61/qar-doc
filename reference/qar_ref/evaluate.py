"""提供元ごとの「使える返事が返ってきた割合」を測る評価の仕組み。

AI側の仕様変更や不調は、ある日突然、返事の形が崩れる、という形で現れる。
同じ条件で繰り返し呼び、成功率と失敗の種類を記録しておけば、変化に気づける。
（本物のAIに対しては、課金されるため、回数と頻度を決めて実行する）
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .providers import Registry
from .service import ProviderError, QarService


@dataclass
class StageStats:
    ok: int = 0
    ng: int = 0
    errors: Counter = field(default_factory=Counter)  # {"parse": n, "schema": n}

    @property
    def total(self) -> int:
        return self.ok + self.ng

    @property
    def rate(self) -> float:
        return self.ok / self.total if self.total else 0.0


def evaluate(registry: Registry, themes: list[str], trials: int, max_retries: int = 0) -> dict:
    """{提供元: {"questions": StageStats, "result": StageStats}} を返す。"""
    service = QarService(registry, max_retries=max_retries)
    report: dict[str, dict[str, StageStats]] = {}
    for name in registry.names():
        stats = {"questions": StageStats(), "result": StageStats()}
        for theme in themes:
            for _ in range(trials):
                _record(stats["questions"], lambda: service.get_questions(name, theme))
                _record(stats["result"], lambda: service.get_result(name, theme, [{"question": "q", "answer": "a"}]))
        report[name] = stats
    return report


def _record(stat: StageStats, call) -> None:
    try:
        call()
        stat.ok += 1
    except ProviderError as exc:
        stat.ng += 1
        stat.errors[exc.category] += 1


def format_report(report: dict) -> str:
    lines = [f"{'提供元':<10}{'段階':<11}{'成功/試行':>10}{'成功率':>8}  失敗の内訳"]
    for name, stages in report.items():
        for stage, s in stages.items():
            detail = ", ".join(f"{k}={v}" for k, v in sorted(s.errors.items())) or "-"
            lines.append(f"{name:<10}{stage:<11}{f'{s.ok}/{s.total}':>10}{s.rate:>7.0%}  {detail}")
    return "\n".join(lines)
