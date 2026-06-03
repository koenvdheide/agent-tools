import os, sys, json, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def validate(obj, schema):
    """Minimal stdlib validator: checks required keys, types, and enums."""
    def check(node, sch, path="root"):
        t = sch.get("type")
        if t == "object":
            for req in sch.get("required", []):
                assert req in node, f"{path}: missing {req}"
            for k, sub in sch.get("properties", {}).items():
                if k in node:
                    check(node[k], sub, f"{path}.{k}")
        elif t == "array":
            for i, el in enumerate(node):
                check(el, sch["items"], f"{path}[{i}]")
        elif t == "string":
            assert isinstance(node, str), f"{path}: not str"
            if "enum" in sch:
                assert node in sch["enum"], f"{path}: {node} not in enum"
        elif t == "integer":
            assert isinstance(node, int), f"{path}: not int"
    check(obj, schema)
    return True

class TestSchema(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(HERE, "schema.json"), encoding="utf-8") as f:
            self.schema = json.load(f)

    def test_enums_present(self):
        finding = self.schema["properties"]["findings"]["items"]["properties"]
        self.assertEqual(set(finding["impact_tier"]["enum"]),
                         {"not-observed", "local-edit", "plan/direction-change", "scrapped"})
        self.assertEqual(set(finding["verdict"]["enum"]),
                         {"adopted", "partial", "rejected", "deferred"})

    def test_sample_object_validates(self):
        sample = {
            "episode_id": "tu_rt1", "project_slug": "proj-a", "mode": "red-team",
            "chain_id": None, "round_index": 0, "artifact_type": "plan",
            "findings": [{
                "heading": "Breakage", "category": "correctness", "validity": "valid",
                "verdict": "adopted", "impact_tier": "local-edit",
                "evidence_quote": "drops the idempotency key", "location": "codex output"
            }]
        }
        self.assertTrue(validate(sample, self.schema))

if __name__ == "__main__":
    unittest.main()
