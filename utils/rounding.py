from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 40

def D(x) -> Decimal:
    if x is None:
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    s = str(x).strip()
    if s == "" or s.lower() == "nan" or s == "None":
        return Decimal("0")
    s = s.replace(",", "")
    return Decimal(s)

def r2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def r6(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
