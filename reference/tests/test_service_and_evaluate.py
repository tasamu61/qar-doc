import unittest

from qar_ref.evaluate import evaluate, format_report
from qar_ref.providers import FakeProvider, FlakyProvider, Registry, UnknownProvider
from qar_ref.service import ProviderError, QarService


class Allowlist(unittest.TestCase):
    def setUp(self):
        self.service = QarService(Registry([FakeProvider("a"), FakeProvider("b")]))

    def test_registered_provider_works(self):
        self.assertTrue(self.service.get_questions("a", "旅行")["questions"])

    def test_unregistered_names_are_rejected(self):
        for bad in ("os", "../x", "A", "", None, 1):
            with self.subTest(name=bad), self.assertRaises(UnknownProvider):
                self.service.get_questions(bad, "旅行")


class Service(unittest.TestCase):
    def test_fenced_answer_is_accepted(self):
        s = QarService(Registry([FakeProvider("f", fenced=True)]))
        self.assertTrue(s.get_result("f", "旅行", [])["result"])

    def test_error_is_classified(self):
        class NotJson(FakeProvider):
            def generate_result(self, *a, **k):
                return "うまく作れませんでした"

        class WrongShape(FakeProvider):
            def generate_result(self, *a, **k):
                return '{"result": [{"destination": "A", "score": 999, "description": "d", "url": "https://e.com"}]}'

        with self.assertRaises(ProviderError) as cm:
            QarService(Registry([NotJson("n")])).get_result("n", "t", [])
        self.assertEqual(cm.exception.category, "parse")
        with self.assertRaises(ProviderError) as cm:
            QarService(Registry([WrongShape("w")])).get_result("w", "t", [])
        self.assertEqual(cm.exception.category, "schema")

    def test_retry_recovers_from_a_transient_failure(self):
        class FailsOnce(FakeProvider):
            calls = 0

            def generate_questions(self, *a, **k):
                FailsOnce.calls += 1
                return "壊れた返事" if FailsOnce.calls == 1 else super().generate_questions(*a, **k)

        s = QarService(Registry([FailsOnce("x")]), max_retries=1)
        self.assertTrue(s.get_questions("x", "t")["questions"])
        self.assertEqual(FailsOnce.calls, 2)


class Evaluation(unittest.TestCase):
    def test_perfect_provider_has_full_success(self):
        report = evaluate(Registry([FakeProvider("ok")]), ["旅行", "ペット"], trials=5)
        for stage in report["ok"].values():
            self.assertEqual((stage.ok, stage.ng, stage.rate), (10, 0, 1.0))

    def test_flaky_provider_is_measured_and_reproducible(self):
        def run():
            return evaluate(Registry([FlakyProvider("flaky", 0.4, seed=7)]), ["旅行"], trials=50)

        a, b = run(), run()
        for stage in ("questions", "result"):
            self.assertEqual((a["flaky"][stage].ok, a["flaky"][stage].errors),
                             (b["flaky"][stage].ok, b["flaky"][stage].errors))
            self.assertTrue(0.3 < a["flaky"][stage].rate < 0.9)
            self.assertGreater(sum(a["flaky"][stage].errors.values()), 0)

    def test_retries_raise_the_success_rate(self):
        base = evaluate(Registry([FlakyProvider("f", 0.4, seed=1)]), ["t"], trials=100)
        retry = evaluate(Registry([FlakyProvider("f", 0.4, seed=1)]), ["t"], trials=100, max_retries=2)
        self.assertGreater(retry["f"]["result"].rate, base["f"]["result"].rate)

    def test_report_is_readable(self):
        text = format_report(evaluate(Registry([FakeProvider("ok")]), ["t"], trials=2))
        self.assertIn("ok", text)
        self.assertIn("100%", text)


if __name__ == "__main__":
    unittest.main()
