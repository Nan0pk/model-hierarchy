from hierarchy.aggregate import benjamini_hochberg


def test_bh_adjustment_is_monotone_and_bounds_values():
    models = ["a", "b", "c", "d"]
    probs = {
        ("a", "b"): .999, ("b", "a"): .001,
        ("a", "c"): .97, ("c", "a"): .03,
        ("a", "d"): .6, ("d", "a"): .4,
        ("b", "c"): .8, ("c", "b"): .2,
        ("b", "d"): .5, ("d", "b"): .5,
        ("c", "d"): .7, ("d", "c"): .3,
    }
    q = benjamini_hochberg(probs, models)
    assert q[("a", "b")] <= q[("a", "c")] <= 1
    assert all(0 <= value <= 1 for value in q.values())
    assert len(q) == 6


def test_bh_empty_and_single_model():
    assert benjamini_hochberg({}, []) == {}
    assert benjamini_hochberg({}, ["alone"]) == {}
