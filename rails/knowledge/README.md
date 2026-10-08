# Knowledge base

This folder holds the facts Lifeline is allowed to state about money rules, limits, documents, and providers in each corridor. There is one YAML file per country, and each file is a list of entries. A fact about a provider that is not tied to one country, such as how Wise collects documents, goes in `providers.yaml`, with `country` set to `all`.

## Rules

1. The agent may only assert facts that exist as entries in this folder. When no entry covers a question, the agent says it has no sourced figure and does not guess.
2. Every entry needs two initials, one in `checked_by` and one in `second_check_by`, before it is used in a demo. An entry whose `second_check_by` is empty has been checked once and must not appear in a demo yet.
3. Every entry cites its source with an address that starts with `https://`, and `date_checked` must be no more than 30 days old. `tests/test_knowledge.py` enforces the fields, the address, and the age, so a stale entry fails the build until someone checks it again.

`CC` in `checked_by` means Claude Code checked the entry against the page it opened; a person replaces it with their initials once they have checked it too.

## Entry format

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | text | Stable identifier made of the country code, a short topic, and a number, such as `cn_fx_quota_001` |
| `statement` | text | The fact in plain sentences, worded exactly as the agent may state it |
| `country` | text | Country code the fact applies to, such as `CN`, or `all` for a provider fact in `providers.yaml` that holds wherever the provider operates |
| `rail` | text | The rail or channel the fact is about: `bank_fx`, `bank_remittance`, `card`, `wallet`, `wise`, `upi_paynow`, `pix`, or `all` for a rule that covers every rail |
| `kind` | text | What sort of fact it is: `quota`, `limit`, `rule`, or `documents` |
| `source_url` | text | Where the fact comes from |
| `source_type` | text | What kind of source it is: `regulator`, `government`, `bank`, `operator`, or `press` |
| `date_checked` | date | When the fact was last confirmed against its source, written as year, month, and day |
| `checked_by` | text | Initials of the first person who checked the entry |
| `second_check_by` | text | Initials of the second person who checked the entry, empty until then |
| `used_by` | list | Task ids, attack ids, and prechecks that rely on the entry, such as `T36`, `X28`, or `precheck.remit_from_china` |
| `note` | text, optional | Anything a checker still has to do, such as confirming a press report against the primary text |
| `values` | mapping, optional | The figures and lists in the statement, as data a rail or the router reads by entry id, such as `daily_cap: 60000` and `currency: INR`. Code never writes such a figure itself; it reads it here. Every number in `values` must also be written in the statement, which `tests/test_knowledge_values.py` checks |

## Example

```yaml
- id: cn_atm_cap_005
  statement: "Overseas cash withdrawals on all of an individual's Chinese bank cards, including supplementary cards, are capped at 100,000 yuan per calendar year and 10,000 yuan per card per day. Exceeding the annual cap bars overseas withdrawals for the rest of that year and the following year. The rule took effect on 1 January 2018."
  country: CN
  rail: card
  kind: limit
  source_url: "https://www.safe.gov.cn/en/2017/1230/1397.html"
  source_type: regulator
  date_checked: 2026-09-15
  checked_by: "S"
  second_check_by: ""
  used_by: [T37]
```

Every text value is in double quotes, because statements contain commas, colons, and apostrophes. `used_by` ties each fact to the tasks and attacks that depend on it, so when a source changes, it is clear which scenarios must be checked again.
