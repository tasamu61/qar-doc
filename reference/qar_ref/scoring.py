"""2002年版の考え方（積和スコア）を、現代版の部品として書き直したもの。

  適合度(候補) = Σ 回答の重み(着眼点k) × 候補の持つ値(着眼点k)

  * 計算は決定的（同じ入力なら、いつも同じ結果）。根拠を数字で説明できる。
  * 2002年版の課題だった「絶対条件」（例: 日程5日まで・予算15万まで）は、
    スコアに混ぜず、先に候補を除外する条件として扱う。
  * LLMの役割は、自由記述の解釈（回答の重みへの変換）と、結果の説明文の生成に限る。
    候補の順位そのものはここで決める。

注意: サンプルデータの数値は、説明のための架空のものです。
"""
from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Iterable

_OPS = {"<=": operator.le, ">=": operator.ge, "==": operator.eq}


@dataclass(frozen=True)
class Candidate:
    id: int
    name: str
    scores: dict[int, int]                      # 着眼点番号 -> この候補の値
    attrs: dict[str, float] = field(default_factory=dict)  # 絶対条件の判定に使う実数値


@dataclass(frozen=True)
class Constraint:
    attr: str
    op: str      # "<=", ">=", "=="
    value: float

    def __post_init__(self):
        if self.op not in _OPS:
            raise ValueError(f"未対応の演算子: {self.op}")

    def satisfied_by(self, c: Candidate) -> bool:
        if self.attr not in c.attrs:
            return False  # 判定できない候補は、安全側に倒して除外する
        return _OPS[self.op](c.attrs[self.attr], self.value)


@dataclass(frozen=True)
class Ranked:
    candidate: Candidate
    total: int
    breakdown: dict[int, int]  # 着眼点ごとの寄与（根拠の説明に使う）


def apply_constraints(candidates: Iterable[Candidate], constraints: Iterable[Constraint]):
    """(残った候補, {除外された候補名: 理由}) を返す。"""
    constraints = list(constraints)
    kept: list[Candidate] = []
    excluded: dict[str, str] = {}
    for c in candidates:
        failed = [k for k in constraints if not k.satisfied_by(c)]
        if failed:
            excluded[c.name] = ", ".join(f"{k.attr}{k.op}{k.value}" for k in failed)
        else:
            kept.append(c)
    return kept, excluded


def rank(candidates: Iterable[Candidate], answer_weights: dict[int, int],
         constraints: Iterable[Constraint] = (), top: int = 5):
    """絶対条件で絞ってから、積和スコアで並べる。(順位表, 除外理由) を返す。"""
    kept, excluded = apply_constraints(candidates, constraints)
    table = []
    for c in kept:
        parts = {k: w * c.scores.get(k, 0) for k, w in answer_weights.items()}
        table.append(Ranked(c, sum(parts.values()), parts))
    table.sort(key=lambda r: (-r.total, r.candidate.id))  # 同点は番号順で、結果を安定させる
    return table[:top], excluded


def build_explanation_prompt(ranked: list[Ranked], request_text: str) -> str:
    """LLMに渡す説明用のプロンプト。順位と根拠は渡すだけで、LLMには変えさせない。"""
    lines = [f"{i}位 {r.candidate.name}（適合度 {r.total}）" for i, r in enumerate(ranked, 1)]
    return (
        "次の順位は確定済みです。順位・候補・数値を変更せず、追加もしないでください。\n"
        "利用者の希望に沿って、各候補がその順位である理由を、2文以内で説明してください。\n"
        f"利用者の希望: {request_text}\n" + "\n".join(lines)
    )


# --- 説明用のサンプルデータ（2002年版の資料の例を、現代版の形に置き換えたもの）---
SAMPLE_SCORES = {1: "日程が短い", 2: "海がきれい", 3: "現地物価が安い"}
SAMPLE_CANDIDATES = [
    Candidate(1, "グアム", {1: 11, 2: 5, 3: 2}, {"days": 4, "cost": 120000}),
    Candidate(2, "沖縄", {1: 12, 2: 12, 3: 2}, {"days": 5, "cost": 140000}),
    Candidate(3, "タヒチ", {1: 4, 2: 12, 3: 1}, {"days": 8, "cost": 350000}),
    Candidate(4, "江ノ島", {1: 15, 2: 1}, {"days": 1, "cost": 5000}),
]
