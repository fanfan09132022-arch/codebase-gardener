def average(xs):
    if not xs:
        return 0
    xs = [x for x in xs if x is not None]
    if not xs:
        return 0
    return round(sum(xs) / len(xs), 2)
