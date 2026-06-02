---
name: ghostfolio
description: Query and operate a self-hosted Ghostfolio portfolio tracker. Use when asked about portfolio performance, holdings, account balances, investment activities, or when the user wants to create accounts or manage transactions in Ghostfolio.
allowed-tools: Bash(python3:*)
---

# Ghostfolio Skill

## Purpose

Use this skill to answer questions about the user's Ghostfolio instance and to perform operations against it. Ghostfolio is a self-hosted portfolio tracker running on the local network.

## Config

All config is read from a `.env` file at:

```
~/.agents/skills/ghostfolio-skill/scripts/.env
```

Required keys:
- `GHOSTFOLIO_URL` — base URL, e.g. `http://ghostfolio.local:3333` or `http://192.168.1.x:3333`
- `ACCESS_TOKEN` — anonymous access token for auth

Optional keys:
- `ALLOW_DELETE` — set to `true` to enable delete operations (default: `false`)

## CLI

All operations go through the Python CLI:

```bash
python3 ~/.agents/skills/ghostfolio-skill/scripts/ghostfolio.py <command> [options]
```

## Commands

### Read operations

```bash
# Verify connection
python3 ~/.agents/skills/ghostfolio-skill/scripts/ghostfolio.py auth

# Portfolio performance (ranges: 1d 1w 1m 3m 6m ytd 1y 2y 3y 5y max)
python3 ~/.agents/skills/ghostfolio-skill/scripts/ghostfolio.py performance
python3 ~/.agents/skills/ghostfolio-skill/scripts/ghostfolio.py performance --range 1y

# Current holdings (sorted by value desc)
python3 ~/.agents/skills/ghostfolio-skill/scripts/ghostfolio.py holdings

# Accounts (balance, value, transaction count)
python3 ~/.agents/skills/ghostfolio-skill/scripts/ghostfolio.py accounts

# All activities (most recent first)
python3 ~/.agents/skills/ghostfolio-skill/scripts/ghostfolio.py activities

# Activities filtered by account name or UUID
python3 ~/.agents/skills/ghostfolio-skill/scripts/ghostfolio.py activities --account "Bitcoin"
python3 ~/.agents/skills/ghostfolio-skill/scripts/ghostfolio.py activities --account <account_uuid>
```

### Write operations

```bash
# Create a new EUR account
python3 ~/.agents/skills/ghostfolio-skill/scripts/ghostfolio.py create-account "Account Name"

# Delete an activity (requires ALLOW_DELETE=true in .env)
python3 ~/.agents/skills/ghostfolio-skill/scripts/ghostfolio.py delete-activity <activity_id>
```

## Output format

All commands print JSON. Parse it directly.

**performance** returns:
```json
{
  "range": "max",
  "currentValue": 12345.67,
  "totalInvestment": 10000.00,
  "grossPerformance": 2345.67,
  "grossPerformancePercentage": 0.2345,
  "netPerformance": 2300.00,
  "netPerformancePercentage": 0.23,
  "dividendInBaseCurrency": 50.00,
  "fees": 10.00
}
```

**holdings** returns an array sorted by currentValue desc:
```json
[
  {
    "symbol": "BTC-EUR",
    "name": "Bitcoin EUR",
    "quantity": 0.05,
    "currentPrice": 85000,
    "currentValue": 4250,
    "grossPerformancePercentage": 0.42,
    "investment": 3000,
    "allocationInPercentage": 0.34
  }
]
```

**accounts** returns:
```json
[
  {
    "id": "uuid",
    "name": "Bitcoin",
    "currency": "EUR",
    "balance": 0,
    "value": 4250,
    "transactionCount": 12
  }
]
```

**activities** returns:
```json
{
  "count": 45,
  "activities": [
    {
      "id": "uuid",
      "type": "BUY",
      "date": "2026-04-07",
      "symbol": "BTC-EUR",
      "quantity": 0.001,
      "unitPrice": 85000,
      "fee": 0,
      "accountName": "Bitcoin"
    }
  ]
}
```

## Answering user questions

| User asks | Command to run |
|-----------|---------------|
| "How is my portfolio doing?" | `performance` |
| "Performance this year" | `performance --range ytd` |
| "What do I hold?" | `holdings` |
| "Show my accounts" | `accounts` |
| "Show my Bitcoin transactions" | `activities --account Bitcoin` |
| "How much have I invested?" | `performance` → `totalInvestment` |
| "What's my biggest holding?" | `holdings` → first item |

## Formatting responses

- Convert raw EUR amounts to readable format: `12345.67` → `€12,345.67`
- Convert percentages: `0.2345` → `23.45%`
- Show gross and net performance together when relevant
- When showing holdings, include symbol, current value, and % allocation
- If the user asks a summary question, run `performance` + `holdings` together to give a full picture

## Error handling

- If the Ghostfolio instance is unreachable, the script prints `{"error": "..."}` and exits 1. Tell the user to check if Ghostfolio is running.
- If `ALLOW_DELETE` is not `true` in `.env`, delete operations are blocked by the script itself.
- Auth errors (wrong ACCESS_TOKEN) show HTTP 401.
