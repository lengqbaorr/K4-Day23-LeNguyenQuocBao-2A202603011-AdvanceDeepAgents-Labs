"""Offline tests (no network, no LLM):   python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools  # noqa: E402
from check_citations import check  # noqa: E402
from research import slugify  # noqa: E402
from tools import RetryableError, with_retry  # noqa: E402

S = [{"n": 1, "id": "a", "url": "https://arxiv.org/abs/2501.00001", "title": "A", "date": "2025-01-01", "source": "arxiv"},
     {"n": 2, "id": "b", "url": "https://huggingface.co/papers/2501.00002", "title": "B", "date": "", "source": "hf-search"}]
REF = ("\n## References\n[1] A. arxiv. https://arxiv.org/abs/2501.00001 (2025-01-01)\n"
       "[2] B. hf-search. https://huggingface.co/papers/2501.00002\n")


class CheckCitations(unittest.TestCase):
    def test_valid_and_grouped(self):
        for body in ["X [1]. Y [2].", "X [1, 2].", "X [1-2].", "X [1][2].\n```\n[9]\n```"]:
            self.assertEqual(check(f"# T\n{body}\n{REF}", S), [], body)

    def test_problems(self):
        bad = {
            "no sources": ("# T\n## References\n", []),
            "no references": ("# T\nX [1][2].", S),
            "unknown citation": ("# T\nX [1][2][3]." + REF, S),
            "uncited source": ("# T\nX [1]." + REF, S),
            "bundled line": ("# T\nX [1][2].\n## References\n[1] A https://arxiv.org/abs/2501.00001 "
                             "https://huggingface.co/papers/2501.00002\n[2] B https://huggingface.co/papers/2501.00002\n", S),
            "wrong url": ("# T\nX [1][2].\n## References\n[1] A https://x.org\n[2] B https://huggingface.co/papers/2501.00002\n", S),
            "duplicate url": ("# T\nX [1][2]." + REF, [S[0], {**S[1], "url": S[0]["url"]}]),
        }
        for name, (report, sources) in bad.items():
            self.assertTrue(check(report, sources), name)


class Retry(unittest.TestCase):
    @mock.patch("tools.time.sleep")
    def test_backoff(self, sleep):
        fn = mock.Mock(side_effect=[RetryableError("x"), RetryableError("x", retry_after=7), "ok"])
        self.assertEqual(with_retry(fn, attempts=5, cap=30), "ok")
        self.assertEqual(sleep.call_args_list[1][0][0], 7)            # Retry-After honoured

    @mock.patch("tools.time.sleep")
    def test_gives_up_without_final_sleep_and_caps(self, sleep):
        with self.assertRaises(RetryableError):
            with_retry(mock.Mock(side_effect=RetryableError("x")), attempts=6, base=1, cap=4)
        self.assertEqual(sleep.call_count, 5)
        self.assertLessEqual(max(c[0][0] for c in sleep.call_args_list), 4.25)

    @mock.patch("tools.time.sleep")
    def test_other_errors_not_retried(self, sleep):
        with self.assertRaises(ZeroDivisionError):
            with_retry(lambda: 1 / 0)
        sleep.assert_not_called()


class Tools(unittest.TestCase):
    def test_empty_arxiv_query_skips_network(self):
        with mock.patch("tools.httpx.get") as get:
            self.assertEqual(tools.arxiv_search.invoke({"query": ' :: "" AND '}), "NO RESULTS")
            get.assert_not_called()

    @mock.patch("tools.time.sleep")
    def test_exa_key_redacted(self, _):
        err = tools.httpx.ConnectError("fail https://mcp.exa.ai/mcp?exaApiKey=SECRET123")
        with mock.patch.dict("os.environ", {"EXA_API_KEY": "SECRET123"}), mock.patch("tools.httpx.post", side_effect=err):
            out = tools.web_search.invoke({"query": "x"})
        self.assertTrue(out.startswith("ERROR:"))
        self.assertNotIn("SECRET123", out)


class Slug(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("survey about world model"), "survey-about-world-model")
        self.assertEqual(slugify("../../x"), "x")
        self.assertEqual(slugify(""), "topic")
        self.assertLessEqual(len(slugify("x" * 200)), 60)


if __name__ == "__main__":
    unittest.main()
