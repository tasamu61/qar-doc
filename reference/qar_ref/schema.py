"""AIの返事（テキスト）を取り出して、形式を検証する。

提供元ごとに返事の形は揺れる（コードフェンス付き、JSONが連続、配列だけ、など）。
そこで「取り出し(extract) → 正規化(normalize) → 検証(validate)」を共通の層に置く。
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

QUESTION_TYPES = ("single", "multiple", "text", "text1")
_FENCE = re.compile(r"```[a-zA-Z]*\s*|```")


def extract_json_values(text: str) -> list[Any]:
    """テキストの中のJSON値を、出てきた順にすべて取り出す。

    - ```json ... ``` のコードフェンスは取り除く
    - {..}{..} のようにJSONが連続していても、すべて取り出す
    JSONが1つも取り出せなければ ValueError。
    """
    cleaned = _FENCE.sub("", text).strip()
    decoder = json.JSONDecoder()
    values: list[Any] = []
    pos = 0
    while pos < len(cleaned):
        if cleaned[pos].isspace():
            pos += 1
            continue
        try:
            value, end = decoder.raw_decode(cleaned, pos)
        except json.JSONDecodeError as exc:
            if values:  # 後ろに余計な文章が付いていても、取れた分は使う
                break
            raise ValueError(f"JSONとして解釈できません: {exc.msg}") from exc
        values.append(value)
        pos = end
    if not values:
        raise ValueError("JSONが含まれていません")
    return values


def normalize_questions(values: list[Any]) -> dict:
    """質問の返事を {"questions": [...]} の形にそろえる。"""
    if len(values) == 1 and isinstance(values[0], dict) and "questions" in values[0]:
        return values[0]
    if len(values) == 1 and isinstance(values[0], list):
        return {"questions": values[0]}
    if all(isinstance(v, dict) and "questions" not in v for v in values):
        return {"questions": values}  # 質問オブジェクトが連続して返ってきた場合
    raise ValueError("質問の形式を判別できません")


def normalize_result(values: list[Any]) -> dict:
    """結果の返事を {"result": [...]} の形にそろえる。"""
    if len(values) == 1 and isinstance(values[0], dict) and "result" in values[0]:
        return values[0]
    if len(values) == 1 and isinstance(values[0], list):
        return {"result": values[0]}
    raise ValueError("結果の形式を判別できません")


def validate_questions(obj: Any) -> list[str]:
    """問題点のリストを返す。空なら妥当。"""
    errors: list[str] = []
    if not isinstance(obj, dict) or not isinstance(obj.get("questions"), list) or not obj["questions"]:
        return ["questions が空、または配列ではありません"]
    seen: set[int] = set()
    for i, q in enumerate(obj["questions"]):
        where = f"questions[{i}]"
        if not isinstance(q, dict):
            errors.append(f"{where}: オブジェクトではありません")
            continue
        qid = q.get("id")
        if isinstance(qid, bool) or not isinstance(qid, int):
            errors.append(f"{where}.id: 整数ではありません")
        elif qid in seen:
            errors.append(f"{where}.id: 重複しています ({qid})")
        else:
            seen.add(qid)
        if not isinstance(q.get("text"), str) or not q["text"].strip():
            errors.append(f"{where}.text: 空です")
        qtype = q.get("type")
        if qtype not in QUESTION_TYPES:
            errors.append(f"{where}.type: 不正な種類です ({qtype!r})")
        elif qtype in ("single", "multiple"):
            choices = q.get("choices")
            if not isinstance(choices, list) or len(choices) < 2 or not all(isinstance(c, str) and c for c in choices):
                errors.append(f"{where}.choices: 2つ以上の文字列が必要です")
    return errors


def validate_result(obj: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(obj, dict) or not isinstance(obj.get("result"), list) or not obj["result"]:
        return ["result が空、または配列ではありません"]
    for i, r in enumerate(obj["result"]):
        where = f"result[{i}]"
        if not isinstance(r, dict):
            errors.append(f"{where}: オブジェクトではありません")
            continue
        if not isinstance(r.get("destination"), str) or not r["destination"].strip():
            errors.append(f"{where}.destination: 空です")
        score = r.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
            errors.append(f"{where}.score: 0〜100の整数ではありません")
        if not isinstance(r.get("description"), str) or not r["description"].strip():
            errors.append(f"{where}.description: 空です")
        if not is_safe_http_url(r.get("url")):
            errors.append(f"{where}.url: http/https のURLではありません")
    return errors


def is_safe_http_url(value: Any) -> bool:
    """リンクとして表示してよいURLか。javascript: などのスキームを通さない。"""
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)
