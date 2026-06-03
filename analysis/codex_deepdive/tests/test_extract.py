import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import extract

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

class TestExtract(unittest.TestCase):
    def setUp(self):
        self.basic = extract.extract_file(os.path.join(FIX, "transcript_basic.jsonl"))
        self.chain = extract.extract_file(os.path.join(FIX, "transcript_chain.jsonl"))

    def review_eps(self, eps):
        return [e for e in eps if e.audit != "excluded-mode"]

    def test_detects_two_review_episodes(self):
        self.assertEqual(len(self.review_eps(self.basic)), 2)

    def test_excluded_mode_recorded_not_counted(self):
        excluded = [e for e in self.basic if e.audit == "excluded-mode"]
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0].mode, "debug")

    def test_paired_output_captured(self):
        rt = next(e for e in self.basic if e.mode == "red-team")
        self.assertEqual(rt.audit, "paired")
        self.assertIn("idempotency key", rt.output)

    def test_unpaired_output_bucketed(self):
        dr = next(e for e in self.basic if e.mode == "diff-review")
        self.assertEqual(dr.audit, "no-output")
        self.assertIsNone(dr.output)

    def test_follow_through_and_qa(self):
        rt = next(e for e in self.basic if e.mode == "red-team")
        files = {f["file"] for f in rt.follow_through}
        self.assertEqual(files, {"plan.md", "config.py"})
        self.assertTrue(rt.reviewer_qa)

    def test_follow_through_stops_at_next_human_turn(self):
        rt = next(e for e in self.basic if e.mode == "red-team")
        self.assertLessEqual(len(rt.follow_through), 2)

    def test_convergence_chain_tagged(self):
        eps = self.review_eps(self.chain)
        self.assertEqual(len({e.chain_id for e in eps}), 1)
        self.assertEqual(sorted(e.round_index for e in eps), [0, 1])

    def test_audit_table_one_bucket_per_invocation(self):
        table = extract.audit_table(self.basic)
        self.assertEqual(sum(table.values()), 3)

if __name__ == "__main__":
    unittest.main()
