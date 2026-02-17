def level_to_band(selected_level: str) -> str:
    s = str(selected_level).strip().lower()

    # Confirmation band
    if s in ("confirmation", "confirm", "c"):
        return "confirmation"

    level = int(s)

    if 1 <= level <= 4:
        return "l1-4"
    if 5 <= level <= 7:
        return "l5-7"
    if 8 <= level <= 10:
        return "l8-10"
    if 11 <= level <= 14:
        return "l12-14"
    if 15 <= level <= 16:
        return "l15-16"
    if level >= 17:
        return "l17"

    raise ValueError("Invalid difficulty level")
