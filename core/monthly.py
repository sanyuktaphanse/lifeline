"""The monthly note: what one student's ledger says about one calendar month, and nothing else.

It reads ledger entries only, calls no model, and names the entry sequence behind every figure, so a
note can be checked line by line against the ledger. Months are calendar months in UTC.
Source: docs/decisions.md, 8 October 2026.
"""

import re
from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from contracts.schemas import LedgerEntry

# ASCII digits only: a year in fullwidth or other digits would match no entry and read as an empty month.
MONTH = re.compile(r"^(?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2])$")
# The receipt statuses a note lists as not having arrived. A cancel the rail carried out is listed too.
PROBLEM_STATUSES = ("failed", "returned")

TEXTS = {
    "en": {
        "note": "Lifeline's note for {month}, from your ledger. Transfers: {transfers}. Standing runs that ran: {standing}. Failed, returned or cancelled: {problems}. Refused requests: {refusals}.",
        "group": "{count} sent on {corridor}, total {total} {currency}, fees {fees} {currency}",
        "no_transfers": "no transfers were sent",
        "none": "none",
        "cancelled": "cancelled",
        "failed": "failed",
        "returned": "returned",
        "refused_by_rail": "refused",
    },
    "pt": {
        "note": "Nota do Lifeline para {month}, a partir do seu registro. Transferências: {transfers}. Ordens permanentes executadas: {standing}. Falhas, devoluções ou cancelamentos: {problems}. Pedidos recusados: {refusals}.",
        "group": "{count} enviadas em {corridor}, total de {total} {currency}, taxas de {fees} {currency}",
        "no_transfers": "nenhuma transferência foi enviada",
        "none": "nenhum",
        "cancelled": "cancelada",
        "failed": "falhou",
        "returned": "devolvida",
        "refused_by_rail": "recusou",
    },
    "zh": {
        "note": "Lifeline 的 {month} 月度记录，来自你的账本。转账：{transfers}。已执行的定期付款：{standing}。失败、退回或取消：{problems}。被拒绝的请求：{refusals}。",
        "group": "在 {corridor} 上发出 {count} 笔，共 {total} {currency}，手续费 {fees} {currency}",
        "no_transfers": "没有发出转账",
        "none": "无",
        "cancelled": "已取消",
        "failed": "失败",
        "returned": "已退回",
        "refused_by_rail": "拒绝",
    },
}


def month_of(moment: datetime) -> str:
    """The calendar month of a moment, in UTC, written YYYY-MM."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m")


def previous_month(month: str) -> str:
    year, number = (int(part) for part in month.split("-"))
    return f"{year - 1}-12" if number == 1 else f"{year}-{number - 1:02d}"


def is_month(text: str) -> bool:
    return MONTH.fullmatch(text) is not None


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value)) if value not in (None, "") else Decimal(0)


def summarize(entries: Iterable[LedgerEntry], user_id: str, month: str) -> dict[str, Any]:
    """Every figure of the note for one student and one month, each with the entries it came from."""
    entries = list(entries)
    # A transfer is counted as sent only when it was not cancelled, failed or returned, in any month, as a
    # reply says money was sent only when it was; those are listed with their outcome instead.
    # Source: the attacker brief of 8 October.
    keys = {
        entry.payload.get("receipt", {}).get("receipt_id"): entry.payload.get("receipt", {}).get("idempotency_key")
        for entry in entries
        if entry.kind == "receipt" and entry.payload.get("user_id") == user_id
    }
    not_sent = {
        entry.payload["receipt"].get("idempotency_key")
        for entry in entries
        if entry.kind == "receipt"
        and entry.payload.get("user_id") == user_id
        and entry.payload.get("receipt", {}).get("status") in PROBLEM_STATUSES
    } | {
        keys.get(entry.payload.get("receipt_id"))
        for entry in entries
        if entry.kind == "note"
        and entry.payload.get("user_id") == user_id
        and entry.payload.get("kind") == "cancel_result"
        and entry.payload.get("status") == "done"
    }
    # A transfer every rail refused at execution leaves a rail error note and no receipt; one that failed on
    # one rail and was then paid on another has a receipt, and is not a problem. Source: the attacker brief.
    receipted = {key for key in keys.values()}
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    standing: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    refusals: list[int] = []
    for entry in entries:
        payload = entry.payload
        if payload.get("user_id") != user_id or month_of(entry.ts) != month:
            continue
        action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
        if (
            entry.kind == "execution"
            and action.get("type") == "transfer"
            and "route" in payload
            and action.get("idempotency_key") not in not_sent
        ):
            key = (str(action.get("currency")), str(action.get("corridor")))
            group = groups.setdefault(
                key, {"currency": key[0], "corridor": key[1], "count": 0, "total": Decimal(0), "fees": Decimal(0), "seqs": []}
            )
            group["count"] += 1
            group["total"] += _decimal(action.get("amount"))
            group["fees"] += _decimal(payload["route"].get("fee"))
            group["seqs"].append(entry.seq)
            if payload.get("standing_mandate_id"):
                standing.append({"standing_mandate_id": payload["standing_mandate_id"], "seq": entry.seq})
        elif entry.kind == "receipt" and payload.get("receipt", {}).get("status") in PROBLEM_STATUSES:
            receipt = payload["receipt"]
            problems.append({"receipt_id": receipt.get("receipt_id"), "outcome": receipt["status"], "seq": entry.seq})
        elif entry.kind == "note" and payload.get("kind") == "cancel_result" and payload.get("status") == "done":
            problems.append({"receipt_id": payload.get("receipt_id"), "outcome": "cancelled", "seq": entry.seq})
        elif (
            entry.kind == "note"
            and "rail_error" in payload
            and payload.get("executed") is False
            and payload.get("idempotency_key") not in receipted
        ):
            problems.append({"receipt_id": None, "rail": payload.get("rail"), "outcome": "refused_by_rail", "seq": entry.seq})
        elif entry.kind == "decision" and not payload.get("decision", {}).get("allowed", True):
            refusals.append(entry.seq)
    transfers = [
        {**group, "total": format(group["total"], "f"), "fees": format(group["fees"], "f")} for group in groups.values()
    ]
    return {
        "month": month,
        "transfers": transfers,
        "standing_runs": standing,
        "problems": problems,
        "refusals": {"count": len(refusals), "seqs": refusals},
    }


def render(summary: dict[str, Any], lang: str) -> str:
    """The note in the student's language, from the summary's figures and nothing else."""
    texts = TEXTS.get(lang, TEXTS["en"])
    transfers = "; ".join(texts["group"].format(**group) for group in summary["transfers"]) or texts["no_transfers"]
    problems = ", ".join(
        f"{item['receipt_id'] or item.get('rail')} {texts[item['outcome']]}" for item in summary["problems"]
    ) or texts["none"]
    return texts["note"].format(
        month=summary["month"],
        transfers=transfers,
        standing=len(summary["standing_runs"]),
        problems=problems,
        refusals=summary["refusals"]["count"],
    )
