import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import validate

EPS = [{"episode_id": f"e{i}", "mode": "red-team" if i % 2 else "diff-review",
        "findings": [{"verdict": "adopted", "impact_tier": "local-edit"}]} for i in range(20)]

class TestValidate(unittest.TestCase):
    def test_seed_reproducible(self):
        a = validate.stratified_sample(EPS, seed=42, per_stratum=3)
        b = validate.stratified_sample(EPS, seed=42, per_stratum=3)
        self.assertEqual([e["episode_id"] for e in a], [e["episode_id"] for e in b])

    def test_draws_across_strata(self):
        s = validate.stratified_sample(EPS, seed=1, per_stratum=2)
        modes = {e["mode"] for e in s}
        self.assertEqual(modes, {"red-team", "diff-review"})

    def test_agreement(self):
        human = {"verdict": "adopted", "validity": "valid"}
        machine = {"verdict": "adopted", "validity": "invalid"}
        ag = validate.agreement([(human, machine)])
        self.assertEqual(ag["verdict"], 1.0)
        self.assertEqual(ag["validity"], 0.0)

    def test_support_gate(self):
        self.assertFalse(validate.supported(n_validated=2, threshold=5))
        self.assertTrue(validate.supported(n_validated=6, threshold=5))

if __name__ == "__main__":
    unittest.main()
