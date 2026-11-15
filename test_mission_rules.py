import unittest

from mission_rules import initialize, plan, readiness, step


class MissionRulesTests(unittest.TestCase):
    def setUp(self):
        satellite = dict(components={"body": "compact"}, total_cost=4000, budget=10000,
                         specs={"Data Accuracy": 40, "Data Capacity": 25, "Power": 45})
        self.resources = plan(satellite, {}, {"duration": 3, "orbit": "LEO"}, None)
        self.state = initialize({}, self.resources)

    def test_success_and_reward_only_once(self):
        scanned = step(self.state, "scan")
        final = step(step(scanned, "scan"), "transmit")
        self.assertEqual(final["outcome"], "Mission Success")
        self.assertEqual(final["credits"], self.state["credits"] - 20 + 140 + 250)
        self.assertEqual(step(final, "transmit"), final)
        self.assertEqual(self.state["stored"], 0)

    def test_deadline(self):
        current = self.state
        for _ in range(3):
            current = step(current, "conserve")
        self.assertEqual(current["outcome"], "Mission Failure")

    def test_partial(self):
        resources = {**self.resources, "goal": 4}
        current = initialize({}, resources)
        for action in ("scan", "transmit", "conserve"):
            current = step(current, action)
        self.assertEqual(current["outcome"], "Partial Success")

    def test_storage_and_budget(self):
        with self.assertRaises(ValueError):
            step({**self.state, "stored": 12}, "scan")
        self.assertEqual(readiness({**self.resources, "credits": 10})[0], "Configuration Invalid")