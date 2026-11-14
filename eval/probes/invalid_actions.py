def invalid_actions(observation: dict) -> list[dict]:
    # Impossible identifiers avoid accidentally treating anyone on a held-out seed.
    invalid = [
        {},
        {"type": "unknown"},
        {"type": "admit", "patient": "__absent__", "zone": "resus"},
        {"type": "assign", "staff": "__absent__", "to": "rest"},
        {"type": "agency", "role": "invalid"},
    ]
    return [dict(invalid[index % len(invalid)]) for index in range(50)]
