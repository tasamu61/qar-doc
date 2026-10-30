"""提供元が返したテキストを、解析・検証して、画面に渡してよい形にする共通の層。"""
from __future__ import annotations

from typing import Callable

from . import schema
from .providers import Registry


class ProviderError(Exception):
    """AIの返事が使えなかった。category で原因を分類する（評価の集計に使う）。"""

    def __init__(self, category: str, detail: str):
        super().__init__(f"{category}: {detail}")
        self.category = category  # "parse" | "schema"
        self.detail = detail


class QarService:
    def __init__(self, registry: Registry, max_retries: int = 0):
        self._registry = registry
        self._max_retries = max_retries

    def _run(self, produce: Callable[[], str], normalize, validate) -> dict:
        last: ProviderError | None = None
        for _ in range(self._max_retries + 1):
            text = produce()
            try:
                obj = normalize(schema.extract_json_values(text))
            except ValueError as exc:
                last = ProviderError("parse", str(exc))
                continue
            problems = validate(obj)
            if problems:
                last = ProviderError("schema", "; ".join(problems[:3]))
                continue
            return obj
        assert last is not None
        raise last

    def get_questions(self, provider: str, theme: str, instruction: str = "") -> dict:
        p = self._registry.get(provider)
        return self._run(lambda: p.generate_questions(theme, instruction),
                         schema.normalize_questions, schema.validate_questions)

    def get_result(self, provider: str, theme: str, answers: list[dict], instruction: str = "") -> dict:
        p = self._registry.get(provider)
        return self._run(lambda: p.generate_result(theme, answers, instruction),
                         schema.normalize_result, schema.validate_result)
