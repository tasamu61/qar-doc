"""AI提供元の差し替え口。

方針:
  * 提供元ごとの違い（通信方式・電文の形）は Provider の中に閉じ込める。
  * Provider は「返事のテキスト」だけを返す。解析と検証は共通の層（service.py）が行う。
  * 使える提供元は、登録済みのものだけ（許可リスト）。名前からモジュールを動的に読み込まない。
"""
from __future__ import annotations

import json
import random
from typing import Protocol


class UnknownProvider(KeyError):
    """登録されていない提供元が指定された。"""


class Provider(Protocol):
    name: str

    def generate_questions(self, theme: str, instruction: str) -> str: ...

    def generate_result(self, theme: str, answers: list[dict], instruction: str) -> str: ...


class Registry:
    """許可リスト。登録した名前だけが使える。"""

    def __init__(self, providers: list[Provider]):
        self._providers = {p.name: p for p in providers}

    def names(self) -> list[str]:
        return sorted(self._providers)

    def get(self, name: str) -> Provider:
        try:
            return self._providers[name]
        except (KeyError, TypeError):
            raise UnknownProvider(name) from None


_QUESTIONS = {
    "questions": [
        {"id": 1, "text": "行きたい時期は？", "type": "single", "choices": ["春", "夏", "秋", "冬"]},
        {"id": 2, "text": "やりたいこと（複数可）", "type": "multiple", "choices": ["海", "温泉", "グルメ"]},
        {"id": 3, "text": "補足があれば", "type": "text1"},
    ]
}
_RESULT = {
    "result": [
        {"destination": "候補A", "score": 90, "description": "説明A", "url": "https://example.com/a"},
        {"destination": "候補B", "score": 75, "description": "説明B", "url": "https://example.com/b"},
    ]
}


class FakeProvider:
    """決まった答えを返す偽物。通信も課金もない。fenced=True ならコードフェンス付きで返す。"""

    def __init__(self, name: str = "fake", fenced: bool = False):
        self.name = name
        self.fenced = fenced

    def _wrap(self, payload: dict) -> str:
        text = json.dumps(payload, ensure_ascii=False)
        return f"```json\n{text}\n```" if self.fenced else text

    def generate_questions(self, theme: str, instruction: str) -> str:
        return self._wrap(_QUESTIONS)

    def generate_result(self, theme: str, answers: list[dict], instruction: str) -> str:
        return self._wrap(_RESULT)


class FlakyProvider:
    """本物のAIでありがちな「たまに崩れる返事」を、再現可能な形で作る偽物。

    seed を固定すれば、毎回同じ順序で失敗する。評価の仕組み自体のテストに使う。
    """

    MODES = ("not_json", "wrong_schema", "bad_url", "truncated")

    def __init__(self, name: str, failure_rate: float, seed: int = 0):
        self.name = name
        self._base = FakeProvider(name)
        self._rate = failure_rate
        self._rng = random.Random(seed)

    def _maybe_break(self, text: str, kind: str) -> str:
        if self._rng.random() >= self._rate:
            return text
        mode = self._rng.choice(self.MODES)
        if mode == "not_json":
            return "申し訳ありません。うまく作成できませんでした。"
        if mode == "truncated":
            return text[: len(text) // 2]
        if mode == "wrong_schema":
            return json.dumps({"unexpected": []}, ensure_ascii=False)
        # bad_url: 結果のURLを javascript: に差し替える（質問のときは形式崩れにする）
        if kind == "result":
            return text.replace("https://example.com/a", "javascript:alert(1)")
        return json.dumps({"questions": [{"id": 1, "text": "", "type": "???"}]}, ensure_ascii=False)

    def generate_questions(self, theme: str, instruction: str) -> str:
        return self._maybe_break(self._base.generate_questions(theme, instruction), "questions")

    def generate_result(self, theme: str, answers: list[dict], instruction: str) -> str:
        return self._maybe_break(self._base.generate_result(theme, answers, instruction), "result")
