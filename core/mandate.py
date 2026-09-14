from contracts.schemas import Action, ActionType, Decision, Mandate


def check(action: Action, mandate: Mandate) -> Decision:
    reasons: list[str] = []
    rule_ids: list[str] = []

    if action.type is ActionType.TRANSFER:
        if action.payee_id not in mandate.allowed_payees:
            rule_ids.append("R06")
            reasons.append(f"Payee {action.payee_id} is not in the allowed payees.")

        if action.amount is not None and action.amount > mandate.per_txn_limit:
            rule_ids.append("R08")
            reasons.append(
                f"Amount {action.amount} is above the per transaction limit "
                f"{mandate.per_txn_limit}."
            )

    return Decision(allowed=not rule_ids, reasons=reasons, rule_ids=rule_ids)
