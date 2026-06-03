import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import extract

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


class TestSlugStem(unittest.TestCase):
    def test_strips_round_and_version_suffixes(self):
        self.assertEqual(extract.slug_stem("codex-spec-r2.txt"), "codex-spec")
        self.assertEqual(extract.slug_stem("codex-redteam-repos-v3.txt"), "codex-redteam-repos")
        self.assertEqual(extract.slug_stem("codex-essay-review7.txt"), "codex-essay-review")
        self.assertEqual(extract.slug_stem("codex-plan.txt"), "codex-plan")
        self.assertIsNone(extract.slug_stem(None))


class TestClassify(unittest.TestCase):
    def test_heredoc_review_modes(self):
        self.assertEqual(extract.classify({"heredoc_mode": "red-team"}), ("review", "red-team"))
        self.assertEqual(extract.classify({"heredoc_mode": "diff-review"}), ("review", "diff-review"))

    def test_review_subcommand(self):
        self.assertEqual(extract.classify({"heredoc_mode": None, "is_review_subcmd": True}),
                         ("review", "review-subcmd"))

    def test_piped_file_with_breakage_output(self):
        # the case the OLD extractor missed: prompt is in the cat'd file, no Mode: in command
        r = {"heredoc_mode": None, "is_review_subcmd": False, "piped_artifact": "plan.md",
             "has_output": True, "output_excerpt": "## Breakage\n- drops the key", "narration_excerpt": ""}
        self.assertEqual(extract.classify(r), ("review", "red-team"))

    def test_non_review_debug(self):
        r = {"heredoc_mode": "debug", "is_review_subcmd": False, "piped_artifact": None,
             "has_output": False, "output_excerpt": None, "narration_excerpt": ""}
        self.assertEqual(extract.classify(r)[0], "non-review")


class TestIsInvocation(unittest.TestCase):
    def test_piped_codex_exec_is_invocation(self):
        self.assertTrue(extract.is_invocation({"cmd_excerpt": "cat x | codex exec -", "out_slug": None}))

    def test_cat_of_codex_file_is_not_invocation(self):
        self.assertFalse(extract.is_invocation({"cmd_excerpt": "cat codex-out.txt", "out_slug": None,
                                                "piped_artifact": None, "has_output": False,
                                                "is_review_subcmd": False}))


class TestExtractReviews(unittest.TestCase):
    def setUp(self):
        self.reviews, self.audit = extract.extract_reviews(FIX)

    def test_counts_reviews_across_fixtures(self):
        # basic: red-team + diff-review; chain: 2 red-team; debug excluded
        self.assertEqual(len(self.reviews), 4)
        modes = [r["mode"] for r in self.reviews]
        self.assertEqual(modes.count("red-team"), 3)
        self.assertEqual(modes.count("diff-review"), 1)

    def test_convergence_chain_by_slug_stem(self):
        chains = {r["chain_id"] for r in self.reviews if r["chain_id"] and r["chain_id"] != "retry"}
        self.assertEqual(len(chains), 1)  # codex-spec-r1 + codex-spec-r2 -> one chain
        rounds = sorted(r["round_index"] for r in self.reviews
                        if r["chain_id"] and r["chain_id"] != "retry")
        self.assertEqual(rounds, [0, 1])

    def test_summary_shape(self):
        s = extract.summarize(self.reviews)
        self.assertEqual(s["reviews_total"], 4)
        self.assertEqual(s["convergence_chains"], 1)


if __name__ == "__main__":
    unittest.main()
