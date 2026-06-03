import os, sys, json, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import aggregate
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

class TestAggregate(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(FIX, "classified_sample.json"), encoding="utf-8") as f:
            self.eps = json.load(f)
        self.agg = aggregate.aggregate(self.eps)

    def test_episode_headline(self):
        self.assertAlmostEqual(self.agg["episode"]["pct_with_valid_adopted"], 75.0)

    def test_chain_vs_single_shot_separated(self):
        self.assertEqual(self.agg["chain"]["n_chains"], 1)
        self.assertEqual(self.agg["episode"]["n_single_shot"], 2)

    def test_invalid_burden_reported(self):
        self.assertEqual(self.agg["findings"]["n_invalid"], 1)

    def test_projects_and_range_derived(self):
        self.assertEqual(self.agg["corpus"]["n_projects"], 2)
        self.assertEqual(self.agg["corpus"]["date_range"][0], "2026-01-10T10:00:00Z")

    def test_anonymized(self):
        self.assertNotIn("p1", json.dumps(self.agg))

    def test_single_shot_pct_present(self):
        # single-shot episodes e1 (valid+adopted) and e2 (invalid+rejected) -> 1/2
        self.assertEqual(self.agg["episode"]["pct_single_shot_with_valid_adopted"], 50.0)

    def test_debatable_excluded_from_headline(self):
        eps = [{"episode_id": "d1", "project_slug": "p", "mode": "red-team", "chain_id": None,
                "round_index": 0, "artifact_type": "plan", "ts": "2026-03-01T00:00:00Z",
                "findings": [{"heading": "Breakage", "category": "correctness", "validity": "debatable",
                              "verdict": "adopted", "impact_tier": "local-edit", "evidence_quote": "x", "location": "y"}]}]
        agg = aggregate.aggregate(eps)
        self.assertEqual(agg["episode"]["pct_with_valid_adopted"], 0.0)
        self.assertEqual(agg["findings"]["n_debatable"], 1)

if __name__ == "__main__":
    unittest.main()
