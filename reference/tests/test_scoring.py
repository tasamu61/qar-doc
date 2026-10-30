import unittest

from qar_ref import scoring
from qar_ref.scoring import Candidate, Constraint

W = {1: 2, 2: 3, 3: 0}  # 「日程が短い」を2、「海がきれい」を3の重みで重視


class Rank(unittest.TestCase):
    def test_sum_of_products(self):
        table, _ = scoring.rank(scoring.SAMPLE_CANDIDATES, W)
        totals = {r.candidate.name: r.total for r in table}
        self.assertEqual(totals, {"沖縄": 60, "タヒチ": 44, "グアム": 37, "江ノ島": 33})
        self.assertEqual([r.candidate.name for r in table], ["沖縄", "タヒチ", "グアム", "江ノ島"])

    def test_breakdown_explains_the_total(self):
        table, _ = scoring.rank(scoring.SAMPLE_CANDIDATES, W)
        top = table[0]
        self.assertEqual(top.breakdown, {1: 24, 2: 36, 3: 0})
        self.assertEqual(sum(top.breakdown.values()), top.total)

    def test_same_input_gives_same_output(self):
        a, _ = scoring.rank(scoring.SAMPLE_CANDIDATES, W)
        b, _ = scoring.rank(list(reversed(scoring.SAMPLE_CANDIDATES)), W)
        self.assertEqual([r.candidate.name for r in a], [r.candidate.name for r in b])

    def test_ties_are_broken_by_id(self):
        c = [Candidate(2, "B", {1: 5}), Candidate(1, "A", {1: 5})]
        table, _ = scoring.rank(c, {1: 1})
        self.assertEqual([r.candidate.name for r in table], ["A", "B"])

    def test_top_limits_the_number(self):
        table, _ = scoring.rank(scoring.SAMPLE_CANDIDATES, W, top=2)
        self.assertEqual(len(table), 2)


class HardConstraints(unittest.TestCase):
    """2002年版の課題: 「日程5日・予算15万まで」を満たさない候補が上位に来てしまう。"""

    CONSTRAINTS = [Constraint("days", "<=", 5), Constraint("cost", "<=", 150000)]

    def test_candidates_violating_constraints_are_excluded(self):
        table, excluded = scoring.rank(scoring.SAMPLE_CANDIDATES, W, self.CONSTRAINTS)
        self.assertNotIn("タヒチ", [r.candidate.name for r in table])
        self.assertIn("タヒチ", excluded)
        self.assertEqual(table[0].candidate.name, "沖縄")

    def test_reason_is_reported(self):
        _, excluded = scoring.rank(scoring.SAMPLE_CANDIDATES, W, self.CONSTRAINTS)
        self.assertIn("days<=5", excluded["タヒチ"])
        self.assertIn("cost<=150000", excluded["タヒチ"])

    def test_missing_attribute_is_excluded_safely(self):
        c = [Candidate(1, "X", {1: 1}, {})]
        table, excluded = scoring.rank(c, {1: 1}, [Constraint("days", "<=", 5)])
        self.assertEqual(table, [])
        self.assertIn("X", excluded)

    def test_unknown_operator_is_rejected(self):
        with self.assertRaises(ValueError):
            Constraint("days", "<", 5)


class ExplanationPrompt(unittest.TestCase):
    def test_prompt_fixes_the_ranking(self):
        table, _ = scoring.rank(scoring.SAMPLE_CANDIDATES, W, top=2)
        prompt = scoring.build_explanation_prompt(table, "海がきれいな所で短い旅行")
        self.assertIn("1位 沖縄", prompt)
        self.assertIn("2位 タヒチ", prompt)
        self.assertIn("変更せず", prompt)
        self.assertNotIn("江ノ島", prompt)


if __name__ == "__main__":
    unittest.main()
