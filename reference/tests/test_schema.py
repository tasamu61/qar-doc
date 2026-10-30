import json
import unittest

from qar_ref import schema

Q = {"id": 1, "text": "好きな海は？", "type": "single", "choices": ["静か", "賑やか"]}
R = {"destination": "A", "score": 80, "description": "d", "url": "https://example.com"}


class Extract(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(schema.extract_json_values('{"a": 1}'), [{"a": 1}])

    def test_code_fence_is_removed(self):
        self.assertEqual(schema.extract_json_values('```json\n{"a": 1}\n```'), [{"a": 1}])

    def test_concatenated_objects(self):
        text = json.dumps(Q, ensure_ascii=False) + "\n" + json.dumps(Q, ensure_ascii=False)
        self.assertEqual(len(schema.extract_json_values(text)), 2)

    def test_trailing_text_is_ignored_when_json_was_found(self):
        self.assertEqual(schema.extract_json_values('{"a": 1} 以上です'), [{"a": 1}])

    def test_no_json_raises(self):
        for text in ("申し訳ありません", "", "   ", '{"a": '):
            with self.subTest(text=text), self.assertRaises(ValueError):
                schema.extract_json_values(text)


class Normalize(unittest.TestCase):
    def test_questions_shapes(self):
        wrapped = {"questions": [Q]}
        self.assertEqual(schema.normalize_questions([wrapped]), wrapped)
        self.assertEqual(schema.normalize_questions([[Q]]), wrapped)
        self.assertEqual(schema.normalize_questions([Q, Q]), {"questions": [Q, Q]})

    def test_result_shapes(self):
        wrapped = {"result": [R]}
        self.assertEqual(schema.normalize_result([wrapped]), wrapped)
        self.assertEqual(schema.normalize_result([[R]]), wrapped)

    def test_unknown_shape_raises(self):
        with self.assertRaises(ValueError):
            schema.normalize_result([{"foo": 1}])


class ValidateQuestions(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(schema.validate_questions({"questions": [Q, {"id": 2, "text": "t", "type": "text"}]}), [])

    def test_problems_are_reported(self):
        cases = {
            "empty": {"questions": []},
            "not_dict": [],
            "dup_id": {"questions": [Q, Q]},
            "bad_type": {"questions": [{**Q, "type": "radio"}]},
            "no_choices": {"questions": [{**Q, "choices": []}]},
            "one_choice": {"questions": [{**Q, "choices": ["a"]}]},
            "empty_text": {"questions": [{**Q, "text": " "}]},
            "bool_id": {"questions": [{**Q, "id": True}]},
        }
        for name, obj in cases.items():
            with self.subTest(case=name):
                self.assertTrue(schema.validate_questions(obj))


class ValidateResult(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(schema.validate_result({"result": [R]}), [])

    def test_score_range_and_type(self):
        for bad in (-1, 101, 80.5, "80", True, None):
            with self.subTest(score=bad):
                self.assertTrue(schema.validate_result({"result": [{**R, "score": bad}]}))

    def test_unsafe_urls_are_rejected(self):
        for bad in ("javascript:alert(1)", "data:text/html,x", "ftp://example.com", "example.com", "", None, "https://"):
            with self.subTest(url=bad):
                self.assertTrue(schema.validate_result({"result": [{**R, "url": bad}]}))
        for good in ("http://example.com", "https://example.com/a?b=1"):
            with self.subTest(url=good):
                self.assertEqual(schema.validate_result({"result": [{**R, "url": good}]}), [])


if __name__ == "__main__":
    unittest.main()
