"""The monthly note: what one student's ledger says about one calendar month, and nothing else.

It reads ledger entries only, calls no model, and names the entry sequence behind every figure, so a
note can be checked line by line against the ledger. Months are calendar months in UTC.
Source: docs/decisions.md, 8 October 2026.
"""

import re
from collections.abc import Iterable
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from contracts.schemas import LedgerEntry
from core.format import fill, format_amount, format_date
from core.reminders import reminders_of
from core.standing import next_occurrence

# ASCII digits only: a year in fullwidth or other digits would match no entry and read as an empty month.
MONTH = re.compile(r"^(?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2])$")
# The receipt statuses a note lists as not having arrived. A cancel the rail carried out is listed too.
PROBLEM_STATUSES = ("failed", "returned")
# The rail a transfer's saving is measured against, by the name the router quotes it under.
BANK_WIRE = "bank_wire"
# A schedule next_occurrence can read: monthly on a day from 1 to 28, as StandingSchedule allows.
SCHEDULE = re.compile(r"monthly:([1-9]|1[0-9]|2[0-8])")
# The notes the note counts as unusual, by their kind, and the entry kind for a suspected injection.
UNUSUAL_NOTES = {"payee_added": "payees_added", "rescue_started": "rescues_started"}
INJECTION = "injection_suspected"

TEXTS = {
    "en": {
        "note": "Lifeline's note for {month}, from your ledger. Transfers: {transfers}. Exchange cost paid: {spread}. {taxes} Routes used: {routes}. Against the bank wire: {savings}. Standing runs that ran: {standing}. Failed, returned or cancelled: {problems}. Unusual: {unusual}. Coming in {next_month}: {coming}.",
        "group": "{count} sent on {corridor}, total {total}, fees {fees}",
        "spread": "{spread} on {corridor}",
        "no_taxes": "Taxes: no tax figure is on file, because no route or entry carries one.",
        "taxes": "Taxes: tax lines are on file in entries {seqs}, and Lifeline does not total them.",
        "route": "{count} over {rail}",
        "saved": "{rail} for {amount} cost {saving} less than the bank wire quoted in the same turn",
        "dearer": "{rail} for {amount} cost {saving} more than the bank wire quoted in the same turn",
        "not_compared": "no comparison is on file for {rail} for {amount}",
        "unusual": "refused requests {refused}, payees added {payees}, rescues started {rescues}, suspected injections {injections}",
        "standing_due": "a standing run of {amount} to {payee} due {due}",
        "reminder_due": "a reminder due {due}",
        "nothing": "nothing on file",
        "no_transfers": "no transfers were sent",
        "none": "none",
        "cancelled": "cancelled",
        "failed": "failed",
        "returned": "returned",
        "refused_by_rail": "refused",
    },
    "pt": {
        "note": "Nota do Lifeline para {month}, a partir do seu registro. Transferências: {transfers}. Custo de câmbio pago: {spread}. {taxes} Rotas usadas: {routes}. Em comparação com a transferência bancária: {savings}. Execuções de ordens permanentes: {standing}. Falhas, devoluções ou cancelamentos: {problems}. Fora do comum: {unusual}. Previsto para {next_month}: {coming}.",
        "group": "{count} enviada(s) em {corridor}, total de {total}, taxas de {fees}",
        "spread": "{spread} em {corridor}",
        "no_taxes": "Impostos: nenhum valor de imposto está registrado, porque nenhuma rota ou entrada traz um.",
        "taxes": "Impostos: há linhas de imposto registradas nas entradas {seqs}, e o Lifeline não as soma.",
        "route": "{count} via {rail}",
        "saved": "{rail} para {amount} custou {saving} a menos que a transferência bancária cotada na mesma mensagem",
        "dearer": "{rail} para {amount} custou {saving} a mais que a transferência bancária cotada na mesma mensagem",
        "not_compared": "não há comparação registrada para {rail} com {amount}",
        "unusual": "pedidos recusados {refused}, destinatários adicionados {payees}, resgates iniciados {rescues}, suspeitas de injeção {injections}",
        "standing_due": "uma execução de ordem permanente de {amount} para {payee} prevista para {due}",
        "reminder_due": "um lembrete em {due}",
        "nothing": "nada registrado",
        "no_transfers": "nenhuma transferência foi enviada",
        "none": "nenhum registro",
        "cancelled": "cancelada",
        "failed": "falhou",
        "returned": "devolvida",
        "refused_by_rail": "recusou",
    },
    "zh": {
        "note": "Lifeline 的 {month} 月度记录，来自您的账本。转账：{transfers}。已付汇率成本：{spread}。{taxes}使用的路线：{routes}。与银行电汇相比：{savings}。已执行的定期付款：{standing}。失败、退回或取消：{problems}。异常情况：{unusual}。下月（{next_month}）安排：{coming}。",
        "group": "在 {corridor} 上发出 {count} 笔，共 {total}，手续费 {fees}",
        "spread": "{corridor} 上 {spread}",
        "no_taxes": "税费：没有记录任何税费数字，因为没有任何路线或记录包含税费。",
        "taxes": "税费：第 {seqs} 条记录中有税费明细，Lifeline 不对其求和。",
        "route": "{rail} {count} 笔",
        "saved": "{rail} 发送 {amount}，比同一轮对话中报价的银行电汇少花 {saving}",
        "dearer": "{rail} 发送 {amount}，比同一轮对话中报价的银行电汇多花 {saving}",
        "not_compared": "{rail} 发送 {amount} 没有可比较的记录",
        "unusual": "被拒绝的请求 {refused} 次，新增收款人 {payees} 个，启动救援 {rescues} 次，疑似注入 {injections} 次",
        "standing_due": "{due} 到期的定期付款 {amount}（收款人 {payee}）",
        "reminder_due": "{due} 到期的提醒",
        "nothing": "没有记录",
        "no_transfers": "没有发出转账",
        "none": "无",
        "cancelled": "已取消",
        "failed": "失败",
        "returned": "已退回",
        "refused_by_rail": "已拒绝",
    },
}


def month_of(moment: datetime) -> str:
    """The calendar month of a moment, in UTC, written YYYY-MM."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m")


def previous_month(month: str) -> str:
    year, number = (int(part) for part in month.split("-"))
    return f"{year - 1}-12" if number == 1 else f"{year}-{number - 1:02d}"


def next_month(month: str) -> str:
    year, number = (int(part) for part in month.split("-"))
    return f"{year + 1}-01" if number == 12 else f"{year}-{number + 1:02d}"


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
    # A trace the student ran that the rail answered failed or returned outranks the receipt's first status.
    # Source: the Stage 9 attacker brief.
    traced = {
        entry.payload["result"]["trace"].get("receipt_id"): (entry.payload["result"]["trace"].get("status"), entry)
        for entry in entries
        if entry.kind == "execution"
        and entry.payload.get("user_id") == user_id
        and isinstance((entry.payload.get("result") or {}).get("trace"), dict)
        and entry.payload["result"]["trace"].get("receipt_id") in keys
        and entry.payload["result"]["trace"].get("status") in PROBLEM_STATUSES
    }
    not_sent |= {keys[receipt_id] for receipt_id in traced}
    # A transfer every rail refused at execution leaves a rail error note and no receipt; one that failed on
    # one rail and was then paid on another has a receipt, and is not a problem. Source: the attacker brief.
    receipted = {key for key in keys.values()}
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    standing: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    refusals: list[int] = []
    sent: list[LedgerEntry] = []
    unusual: dict[str, list[int]] = {name: [] for name in (*UNUSUAL_NOTES.values(), INJECTION)}
    for entry in entries:
        payload = entry.payload
        if payload.get("user_id") != user_id or month_of(entry.ts) != month:
            continue
        action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
        if (
            entry.kind == "execution"
            and action.get("type") == "transfer"
            and isinstance(payload.get("route"), dict)
            and action.get("idempotency_key") not in not_sent
        ):
            key = (str(action.get("currency")), str(action.get("corridor")))
            group = groups.setdefault(
                key,
                {"currency": key[0], "corridor": key[1], "count": 0, "total": Decimal(0), "fees": Decimal(0),
                 "spread": Decimal(0), "seqs": []},
            )
            group["count"] += 1
            group["total"] += _decimal(action.get("amount"))
            group["fees"] += _decimal(payload["route"].get("fee"))
            group["spread"] += _decimal(payload["route"].get("spread_cost"))
            group["seqs"].append(entry.seq)
            sent.append(entry)
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
        elif entry.kind == "note" and payload.get("kind") in UNUSUAL_NOTES:
            unusual[UNUSUAL_NOTES[payload["kind"]]].append(entry.seq)
        elif entry.kind == INJECTION:
            unusual[INJECTION].append(entry.seq)
    listed = {item["receipt_id"] for item in problems}
    for receipt_id, (status, entry) in traced.items():
        if receipt_id not in listed and month_of(entry.ts) == month:
            problems.append({"receipt_id": receipt_id, "outcome": status, "seq": entry.seq})
    transfers = [
        {**group, **{name: format(group[name], "f") for name in ("total", "fees", "spread")}} for group in groups.values()
    ]
    routes: dict[str, dict[str, Any]] = {}
    for entry in sent:
        rail = str(entry.payload["route"].get("rail"))
        route = routes.setdefault(rail, {"rail": rail, "count": 0, "seqs": []})
        route["count"] += 1
        route["seqs"].append(entry.seq)
    taxed = [entry.seq for entry in sent if entry.payload["route"].get("tax_lines")]
    return {
        "month": month,
        "transfers": transfers,
        "standing_runs": standing,
        "problems": problems,
        "refusals": {"count": len(refusals), "seqs": refusals},
        "taxes": {"on_file": bool(taxed), "seqs": taxed},
        "routes": list(routes.values()),
        "comparisons": [_comparison(entries, user_id, entry) for entry in sent],
        "unusual": {name: {"count": len(seqs), "seqs": seqs} for name, seqs in unusual.items()},
        "coming": _coming(entries, user_id, next_month(month)),
    }


def _cost(route: dict[str, Any]) -> Decimal:
    return _decimal(route.get("fee")) + _decimal(route.get("spread_cost"))


def _comparison(entries: list[LedgerEntry], user_id: str, execution: LedgerEntry) -> dict[str, Any]:
    """The saving of one sent transfer against the bank wire, only from a quote the ledger holds for the same
    transfer in the same turn: the same corridor and amount, written before the transfer's execution."""
    action = execution.payload["action"]
    route = execution.payload["route"]
    amount = _decimal(action.get("amount"))
    found = {"seq": execution.seq, "rail": route.get("rail"), "amount": format(amount, "f"), "currency": action.get("currency")}
    quote: tuple[int, dict[str, Any]] | None = None
    for entry in entries:
        if entry.seq >= execution.seq:
            break
        payload = entry.payload
        quoted = payload.get("action") if isinstance(payload.get("action"), dict) else {}
        if (
            entry.kind != "execution"
            or quoted.get("type") != "get_quote"
            or payload.get("user_id") != user_id
            or payload.get("turn") != execution.payload.get("turn")
            or quoted.get("corridor") != action.get("corridor")
            or _decimal(quoted.get("amount")) != amount
        ):
            continue
        for candidate in (payload.get("result") or {}).get("routes") or []:
            if (
                isinstance(candidate, dict)
                and candidate.get("rail") == BANK_WIRE
                and candidate.get("corridor") == action.get("corridor")
                and _decimal(candidate.get("amount")) == amount
            ):
                quote = (entry.seq, candidate)
    if quote is None:
        return {**found, "compared": False}
    wire, paid = _cost(quote[1]), _cost(route)
    return {
        **found,
        "compared": True,
        "quote_seq": quote[0],
        "bank_wire_cost": format(wire, "f"),
        "route_cost": format(paid, "f"),
        "saving": format(wire - paid, "f"),
    }


def _coming(entries: list[LedgerEntry], user_id: str, following: str) -> dict[str, Any]:
    """The standing runs and reminders that fall due in the following month, from the ledger alone.

    A standing mandate is coming when its standing_created note holds it active, no execution has stopped
    it, and no execution has cancelled its run for that month. Its due date comes from next_occurrence.
    """
    own = [entry for entry in entries if entry.payload.get("user_id") == user_id]
    stopped = {
        (entry.payload.get("result") or {}).get("deactivated", {}).get("standing_mandate_id")
        for entry in own
        if entry.kind == "execution"
    }
    cancelled = {
        ((entry.payload.get("result") or {}).get("cancelled", {}).get("standing_mandate_id"),
         (entry.payload.get("result") or {}).get("cancelled", {}).get("period"))
        for entry in own
        if entry.kind == "execution"
    }
    start = datetime.fromisoformat(f"{following}-01T00:00:00+00:00")
    runs = []
    for entry in own:
        mandate = entry.payload.get("standing_mandate")
        if entry.kind != "note" or entry.payload.get("kind") != "standing_created" or not isinstance(mandate, dict):
            continue
        schedule = str(mandate.get("schedule", ""))
        if not mandate.get("active") or mandate.get("id") in stopped or not SCHEDULE.fullmatch(schedule):
            continue
        period, due = next_occurrence(schedule, start)
        if period != following or (mandate.get("id"), period) in cancelled:
            continue
        runs.append(
            {
                "standing_mandate_id": mandate.get("id"),
                "due": due.date().isoformat(),
                "amount": format(_decimal(mandate.get("amount")), "f"),
                "currency": (entry.payload.get("action") or {}).get("currency"),
                "payee_id": mandate.get("payee_id"),
                "seq": entry.seq,
            }
        )
    reminders = [item for item in reminders_of(own, user_id) if item["due"] and item["due"].startswith(following)]
    return {"month": following, "standing_runs": runs, "reminders": reminders}


def seqs_of(summary: dict[str, Any]) -> list[int]:
    """Every entry sequence behind a figure of the note, once each and in order."""
    seqs: set[int] = set()
    for group in summary["transfers"]:
        seqs.update(group["seqs"])
    seqs.update(item["seq"] for item in summary["standing_runs"])
    seqs.update(item["seq"] for item in summary["problems"])
    seqs.update(summary["refusals"]["seqs"])
    seqs.update(summary["taxes"]["seqs"])
    for route in summary["routes"]:
        seqs.update(route["seqs"])
    for comparison in summary["comparisons"]:
        seqs.add(comparison["seq"])
        if comparison["compared"]:
            seqs.add(comparison["quote_seq"])
    for counted in summary["unusual"].values():
        seqs.update(counted["seqs"])
    seqs.update(item["seq"] for item in summary["coming"]["standing_runs"])
    seqs.update(item["seq"] for item in summary["coming"]["reminders"])
    return sorted(seqs)


def _saving(texts: dict[str, str], comparison: dict[str, Any], lang: str) -> str:
    currency = comparison["currency"]
    values = {"rail": comparison["rail"], "amount": format_amount(comparison["amount"], currency, lang)}
    if not comparison["compared"]:
        return fill(texts["not_compared"], **values)
    saving = Decimal(comparison["saving"])
    name = "saved" if saving >= 0 else "dearer"
    return fill(texts[name], saving=format_amount(abs(saving), currency, lang), **values)


def render(summary: dict[str, Any], lang: str) -> str:
    """The note in the student's language, from the summary's figures and nothing else.

    A reminder is named by its due date only: its text is the student's own words, which may hold figures
    no entry backs as a figure, so the note never repeats it.
    """
    texts = TEXTS.get(lang, TEXTS["en"])
    transfers = "; ".join(
        fill(
            texts["group"],
            count=group["count"],
            corridor=group["corridor"],
            total=format_amount(group["total"], group["currency"], lang),
            fees=format_amount(group["fees"], group["currency"], lang),
        )
        for group in summary["transfers"]
    ) or texts["no_transfers"]
    spread = "; ".join(
        fill(texts["spread"], spread=format_amount(group["spread"], group["currency"], lang), corridor=group["corridor"])
        for group in summary["transfers"]
    ) or texts["none"]
    taxes = summary["taxes"]
    taxed = fill(texts["taxes"], seqs=", ".join(str(seq) for seq in taxes["seqs"])) if taxes["on_file"] else texts["no_taxes"]
    routes = ", ".join(fill(texts["route"], count=route["count"], rail=route["rail"]) for route in summary["routes"]) or texts["none"]
    savings = "; ".join(_saving(texts, comparison, lang) for comparison in summary["comparisons"]) or texts["none"]
    problems = ", ".join(
        f"{item['receipt_id'] or item.get('rail')} {texts[item['outcome']]}" for item in summary["problems"]
    ) or texts["none"]
    unusual = summary["unusual"]
    coming = summary["coming"]
    upcoming = [
        fill(
            texts["standing_due"],
            amount=format_amount(run["amount"], run["currency"], lang),
            payee=run["payee_id"],
            due=format_date(date.fromisoformat(run["due"]), lang),
        )
        for run in coming["standing_runs"]
    ] + [
        fill(texts["reminder_due"], due=format_date(datetime.fromisoformat(item["due"]).date(), lang))
        for item in coming["reminders"]
    ]
    return fill(
        texts["note"],
        month=summary["month"],
        transfers=transfers,
        spread=spread,
        taxes=taxed,
        routes=routes,
        savings=savings,
        standing=len(summary["standing_runs"]),
        problems=problems,
        unusual=fill(
            texts["unusual"],
            refused=summary["refusals"]["count"],
            payees=unusual["payees_added"]["count"],
            rescues=unusual["rescues_started"]["count"],
            injections=unusual[INJECTION]["count"],
        ),
        next_month=coming["month"],
        coming=", ".join(upcoming) or texts["nothing"],
    )
