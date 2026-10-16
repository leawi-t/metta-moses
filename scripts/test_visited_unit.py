import visited_tracker

def test_canonicalization():
    cases = [
        # Associativity & flattening
        ('(AND (AND A B) C)', '(AND A B C)'),
        ('(OR A (OR B C))', '(OR A B C)'),
        # Commutativity & sorting
        ('(AND C B A)', '(AND A B C)'),
        ('(OR C A B)', '(OR A B C)'),
        # Deduplication
        ('(AND A B A)', '(AND A B)'),
        ('(OR A B B A)', '(OR A B)'),
        # Single child unwrapping
        ('(AND A)', 'A'),
        ('(OR B)', 'B'),
        # Double negation
        ('(NOT (NOT X))', 'X'),
        # Nested permutations
        ('(OR (AND B A) (AND A B))', '(AND A B)'),
        ('(AND (OR Y X) (OR X Y))', '(OR X Y)'),
        # Exact boolean constants
        ('true', 'TRUE'),
        ('True', 'TRUE'),
        ('TRUE', 'TRUE'),
        ('false', 'FALSE'),
        ('False', 'FALSE'),
        ('FALSE', 'FALSE'),
        # Feature names T / t must NOT become TRUE
        ('T', 'T'),
        ('t', 't'),
        ('(AND T X)', '(AND T X)'),
        ('(AND TRUE X)', '(AND TRUE X)'),
        # Numeric labels 0 / 1 must NOT become FALSE / TRUE
        ('0', '0'),
        ('1', '1'),
        ('(AND 1 X)', '(AND 1 X)'),
        # Python list/tuple input
        (['AND', 'C', ['OR', 'B', 'A']], '(AND (OR A B) C)'),
        (('AND', ('NOT', ('NOT', 'X')), 'A'), '(AND A X)'),
    ]

    for inp, expected in cases:
        actual = visited_tracker.get_canonical_key(inp)
        assert actual == expected, f"Failed for {inp}: expected {expected}, got {actual}"
        print(f"PASS: {inp} -> {actual}")

    # Explicit check that (AND T X) and (AND TRUE X) do NOT collide
    assert visited_tracker.get_canonical_key('(AND T X)') != visited_tracker.get_canonical_key('(AND TRUE X)')
    print("PASS: (AND T X) != (AND TRUE X) (no collision on feature T)")

    print("\nAll canonicalization unit tests passed!")

    # Test visit tracking, fallback, and eligibility
    visited_tracker.reset()
    assert visited_tracker.is_eligible('(AND A B)', max_revisits=1) == 1
    visited_tracker.record_visit('(AND B A)') # record permutation
    assert visited_tracker.get_visit_count('(AND A B)') == 1
    assert visited_tracker.is_eligible('(AND A B)', max_revisits=1) == 0
    assert visited_tracker.is_eligible('(AND B A)', max_revisits=1) == 0
    assert visited_tracker.is_eligible('(AND A B)', max_revisits=2) == 1

    # Fallback test
    assert visited_tracker.get_fallback_count() == 0
    visited_tracker.record_fallback()
    assert visited_tracker.get_fallback_count() == 1
    visited_tracker.record_fallback()
    assert visited_tracker.get_fallback_count() == 2

    # Reset test
    visited_tracker.reset()
    assert visited_tracker.get_visit_count('(AND A B)') == 0
    assert visited_tracker.get_fallback_count() == 0
    assert visited_tracker.is_eligible('(AND A B)', max_revisits=1) == 1
    print("All visit tracking and fallback tests passed!")

if __name__ == '__main__':
    test_canonicalization()
