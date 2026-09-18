from contracts.schemas import ActionType, Tier

TIERS: dict[ActionType, Tier] = {
    ActionType.READ_BALANCE: Tier.T0,
    ActionType.TRACE_TRANSFER: Tier.T0,
    ActionType.PRECHECK: Tier.T0,
    ActionType.GET_QUOTE: Tier.T0,
    ActionType.SET_REMINDER: Tier.T1,
    ActionType.CANCEL_STANDING_RUN: Tier.T1,
    ActionType.DEACTIVATE_STANDING_MANDATE: Tier.T1,
    ActionType.CREATE_STANDING_MANDATE: Tier.T2,
    ActionType.TRANSFER: Tier.T2,
    ActionType.ADD_PAYEE: Tier.T2,
    ActionType.FREEZE_CARD: Tier.T2,
    ActionType.CHANGE_LIMIT: Tier.T3,
    ActionType.CHANGE_MANDATE: Tier.T3,
    ActionType.EXPORT_CREDENTIALS: Tier.T3,
}
