def total(price, qty, shipping):
    if qty <= 0:
        raise ValueError("qty must be positive")
    return price * qty + shipping
