from sum import sum_n

def test_sum():
    assert sum_n(1) == 1
    assert sum_n(3) == 6
    assert sum_n(5) == 15
    assert sum_n(10) == 55