import unittest
import sys
import os

# Ensure scripts dir is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logger_helper
import visited_tracker

class TestLoggerHelperInstrumentation(unittest.TestCase):
    def setUp(self):
        logger_helper.reset()

    def test_finalize_generation_stats(self):
        # Register two candidate trees from deme that have raw > topRaw, pen < topPen
        # Tree 1: (AND X1 X2)
        # Tree 2: (AND X2 X1) -> syntactic duplicate of Tree 1!
        # Tree 3: (OR X1 X2) -> distinct tree
        logger_helper.register_deme_candidate("(AND X1 X2)", -3.0, -9.0, 2)
        logger_helper.register_deme_candidate("(AND X2 X1)", -3.0, -9.0, 2)
        logger_helper.register_deme_candidate("(OR X1 X2)", -4.0, -8.5, 2)

        # Register metapop survivors: only (OR X1 X2) survived into metapop
        logger_helper.register_metapop_exemplar("(OR X1 X2)")

        # Finalize gen 1 stats
        logger_helper.finalize_generation_stats(1, -4.0, 2, -8.0)

        # (AND X1 X2) and (AND X2 X1) were culled.
        # Since they are syntactic permutations, they MUST collapse to 1 distinct canonical tree!
        self.assertEqual(logger_helper.get_distinct_culled_count(), 1)
        archive = logger_helper.get_culled_archive()
        self.assertEqual(len(archive), 1)

        # In Gen 2, suppose (AND X1 X2) is generated again and culled again:
        logger_helper.register_deme_candidate("(AND X1 X2)", -3.0, -9.0, 2)
        # Tree 4: (AND X3 X4) -> novel distinct tree
        logger_helper.register_deme_candidate("(AND X3 X4)", -2.0, -10.0, 2)
        # Survivor is still (OR X1 X2)
        logger_helper.register_metapop_exemplar("(OR X1 X2)")
        logger_helper.finalize_generation_stats(2, -4.0, 2, -8.0)

        # Total distinct culled count should now be 2 (AND of X1,X2 and AND of X3,X4)
        self.assertEqual(logger_helper.get_distinct_culled_count(), 2)
        self.assertEqual(len(logger_helper.get_culled_archive()), 2)

if __name__ == "__main__":
    unittest.main()
