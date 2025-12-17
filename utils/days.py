def dias_360_excel(current_date, prev_date) -> int:
    """Replica la lógica que compartiste en Excel."""
    if current_date.day == 31:
        return 0

    # Feb 28 -> Mar 1
    if prev_date.month == 2 and prev_date.day == 28 and current_date.month == 3 and current_date.day == 1:
        return 3

    # Feb 29 -> Mar 1
    if prev_date.month == 2 and prev_date.day == 29 and current_date.month == 3 and current_date.day == 1:
        return 2

    return 1
