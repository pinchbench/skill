def sum_n(n):
    total = 0
    for i in range(1, n):  # BUG: should include n
        total += i
    return total