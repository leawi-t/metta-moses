import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stall_controller import StallController

class TestStallController(unittest.TestCase):
    def test_static_mode(self):
        ctrl = StallController(r_base=14.0, r_relax=100.0, mode="static")
        for g in range(10):
            ratio, switched, state = ctrl.step(10 - g, -3.0)
            self.assertEqual(ratio, 14.0)
            self.assertEqual(switched, 0)
            self.assertEqual(state, "STATIC")
        summary = ctrl.get_summary()
        self.assertEqual(summary["fraction_relaxed"], 0.0)

    def test_stall_trigger_and_grace_period(self):
        # K=3, M_min=3, Grace=2, Cooldown=2
        ctrl = StallController(r_base=14.0, r_relax=100.0, k_stall=3, m_min=3, grace=2, cooldown=2, mode="dynamic")
        
        # Gen 1: Raw -4.0 (initial discovery) -> BASE, stall=0
        r, sw, st = ctrl.step(15, -4.0)
        self.assertEqual(r, 14.0)
        self.assertEqual(sw, 0)
        self.assertEqual(st, "BASE")
        self.assertEqual(ctrl.stall_count, 0)
        
        # Gen 2: Raw -4.0 -> BASE, stall=1
        r, sw, st = ctrl.step(14, -4.0)
        self.assertEqual(r, 14.0)
        self.assertEqual(sw, 0)
        self.assertEqual(ctrl.stall_count, 1)
        
        # Gen 3: Raw -4.0 -> BASE, stall=2
        r, sw, st = ctrl.step(13, -4.0)
        self.assertEqual(r, 14.0)
        self.assertEqual(sw, 0)
        self.assertEqual(ctrl.stall_count, 2)
        
        # Gen 4: Raw -4.0 -> stall=3 >= K=3! Switches to RELAXED (r=100.0)
        r, sw, st = ctrl.step(12, -4.0)
        self.assertEqual(r, 100.0)
        self.assertEqual(sw, 1)
        self.assertEqual(st, "RELAXED")
        self.assertEqual(ctrl.relaxed_gens_remaining, 3)
        
        # Gen 5: in RELAXED, still -4.0. remaining becomes 2
        r, sw, st = ctrl.step(11, -4.0)
        self.assertEqual(r, 100.0)
        self.assertEqual(sw, 0)
        self.assertEqual(st, "RELAXED")
        self.assertEqual(ctrl.relaxed_gens_remaining, 2)
        
        # Gen 6: BREAKTHROUGH! Raw advances to -2.0! Grace period grants max(1, 2) = 2 remaining
        r, sw, st = ctrl.step(10, -2.0)
        self.assertEqual(r, 100.0)
        self.assertEqual(sw, 0)
        self.assertEqual(st, "RELAXED")
        self.assertEqual(ctrl.relaxed_gens_remaining, 2)
        
        # Gen 7: in RELAXED grace, still -2.0. remaining becomes 1
        r, sw, st = ctrl.step(9, -2.0)
        self.assertEqual(r, 100.0)
        self.assertEqual(ctrl.relaxed_gens_remaining, 1)
        
        # Gen 8: in RELAXED grace, still -2.0. remaining becomes 0 -> switches back to COOLDOWN (r=14.0)
        r, sw, st = ctrl.step(8, -2.0)
        self.assertEqual(r, 14.0)
        self.assertEqual(sw, 1)
        self.assertEqual(st, "COOLDOWN")
        self.assertEqual(ctrl.cooldown_gens_remaining, 2)
        
        # Gen 9: COOLDOWN 1
        r, sw, st = ctrl.step(7, -2.0)
        self.assertEqual(r, 14.0)
        self.assertEqual(sw, 0)
        self.assertEqual(st, "COOLDOWN")
        self.assertEqual(ctrl.cooldown_gens_remaining, 1)
        
        # Gen 10: COOLDOWN 0 -> transitions to BASE
        r, sw, st = ctrl.step(6, -2.0)
        self.assertEqual(r, 14.0)
        self.assertEqual(sw, 0)
        self.assertEqual(st, "BASE")

    def test_trigger_only_mode(self):
        # In trigger_only mode, ratio is always r_base, but switch events occur identically
        ctrl = StallController(r_base=14.0, r_relax=100.0, k_stall=2, m_min=2, grace=1, cooldown=1, mode="trigger_only")
        r1, sw1, st1 = ctrl.step(5, -3.0)
        r2, sw2, st2 = ctrl.step(4, -3.0)
        r3, sw3, st3 = ctrl.step(3, -3.0)
        self.assertEqual(sw3, 1)
        self.assertEqual(r3, 14.0)  # Ratio stayed at 14.0!
        self.assertEqual(st3, "RELAXED")

if __name__ == "__main__":
    unittest.main()
