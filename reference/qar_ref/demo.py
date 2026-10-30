"""動作確認用のデモ。  python -m qar_ref.demo"""
from . import scoring
from .evaluate import evaluate, format_report
from .providers import FakeProvider, FlakyProvider, Registry
from .scoring import Constraint


def main() -> None:
    weights = {1: 2, 2: 3, 3: 0}  # 「日程が短い」=2、「海がきれい」=3 の重み
    constraints = [Constraint("days", "<=", 5), Constraint("cost", "<=", 150000)]
    ranked, excluded = scoring.rank(scoring.SAMPLE_CANDIDATES, weights, constraints)

    print("■ 決定的なスコア計算（絶対条件: 5日以内・15万円以内）")
    for i, r in enumerate(ranked, 1):
        print(f"  {i}位 {r.candidate.name}  適合度={r.total}  内訳={r.breakdown}")
    for name, reason in excluded.items():
        print(f"  除外 {name}（{reason}）")

    print("\n■ 提供元ごとの成功率（3つの偽のAIで、崩れ方を再現）")
    registry = Registry([
        FakeProvider("stable"),
        FlakyProvider("flaky-20", 0.2, seed=1),
        FlakyProvider("flaky-50", 0.5, seed=2),
    ])
    print(format_report(evaluate(registry, ["旅行", "ペット"], trials=50)))
    print("\n■ 同じ条件で、失敗時に最大2回やり直す設定にすると")
    registry2 = Registry([
        FlakyProvider("flaky-20", 0.2, seed=1),
        FlakyProvider("flaky-50", 0.5, seed=2),
    ])
    print(format_report(evaluate(registry2, ["旅行", "ペット"], trials=50, max_retries=2)))


if __name__ == "__main__":
    main()
