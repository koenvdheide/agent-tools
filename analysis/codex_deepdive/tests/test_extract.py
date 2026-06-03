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

    def test_pairing_stops_at_next_codex_call(self):
        # two episodes reuse the same -o slug; the first must NOT grab the second's later Read
        events = [
            {"type": "assistant", "sessionId": "sx", "timestamp": "t1", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "c1", "name": "Bash", "input": {"command": "codex exec -o c:/tmp/codex-x.txt - \nMode: red-team"}}]}},
            {"type": "assistant", "sessionId": "sx", "timestamp": "t2", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "c2", "name": "Bash", "input": {"command": "codex exec -o c:/tmp/codex-x.txt - \nMode: red-team\nPreviously identified findings:\n- x"}}]}},
            {"type": "assistant", "sessionId": "sx", "timestamp": "t3", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "r1", "name": "Read", "input": {"file_path": "c:/tmp/codex-x.txt"}}]}},
            {"type": "user", "sessionId": "sx", "timestamp": "t4", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "r1", "content": "## Breakage\n- second only"}]}},
        ]
        eps = extract.extract_events(events)
        c1 = next(e for e in eps if e.tool_use_id == "c1")
        c2 = next(e for e in eps if e.tool_use_id == "c2")
        self.assertEqual(c1.audit, "no-output")
        self.assertIsNone(c1.output)
        self.assertIn("second only", c2.output)

    def test_unrelated_reviews_not_merged_into_one_chain(self):
        def codex(tid, ts, body):
            return {"type": "assistant", "sessionId": "sy", "timestamp": ts, "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": f"codex exec -o c:/tmp/codex-{tid}.txt - \n{body}"}}]}}
        events = [
            codex("a1", "t1", "Mode: red-team"),
            codex("a2", "t2", "Mode: red-team\nPreviously identified findings:\n- f"),
            codex("a3", "t3", "Mode: diff-review"),
        ]
        eps = [e for e in extract.extract_events(events) if e.audit != "excluded-mode"]
        chains = {e.chain_id for e in eps if e.chain_id}
        self.assertEqual(len(chains), 1)  # only a1+a2 form a chain
        a3 = next(e for e in eps if e.mode == "diff-review")
        self.assertIsNone(a3.chain_id)    # standalone review NOT absorbed
        self.assertEqual(a3.round_index, 0)

if __name__ == "__main__":
    unittest.main()
