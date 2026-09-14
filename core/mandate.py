from contracts.schemas import Action, ActionType, Decision, Mandate


def check(action: Action, mandate: Mandate) -> Decision:
    reasons: list[str] = []
    rule_ids: list[str] = []

    if action.type is ActionType.TRANSFER:
        if action.currency != mandate.currency:
            rule_ids.append("R04")
            reasons.append(
                f"Currency {action.currency} does not match the mandate currency "
                f"{mandate.currency}."
            )

        if action.payee_id not in mandate.allowed_payees:
            rule_ids.append("R06")
            reasons.append(f"Payee {action.payee_id} is not in the allowed payees.")

        if action.corridor not in mandate.allowed_corridors:
            rule_ids.append("R05")
            reasons.append(f"Corridor {action.corridor} is not in the allowed corridors.")

        if action.purpose not in mandate.allowed_purposes:
            rule_ids.append("R07")
            reasons.append(f"Purpose {action.purpose} is not in the allowed purposes.")

        if action.amount is not None and action.amount > mandate.per_txn_limit:
            rule_ids.append("R08")
            reasons.append(
                f"Amount {action.amount} is above the per transaction limit "
                f"{mandate.per_txn_limit}."
            )

    return Decision(allowed=not rule_ids, reasons=reasons, rule_ids=rule_ids)
