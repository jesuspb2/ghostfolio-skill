#!/usr/bin/env python3
"""
Ghostfolio CLI — read-only and mutating operations against a self-hosted Ghostfolio instance.

Usage:
    python3 ghostfolio.py <command> [options]

Commands:
    auth                              Verify connection and authentication
    performance [--range <range>]     Portfolio performance (default range: max)
    holdings                          Current holdings sorted by value
    details                           Portfolio details (accounts, allocations)
    activities [--account <name|id>]  List all activities, optionally filtered by account name or ID
    accounts                          List all accounts with balances
    create-account <name>             Create a new EUR account
    delete-activity <id>              Delete an activity (requires ALLOW_DELETE=true in .env)

Ranges for performance: 1d, 1w, 1m, 3m, 6m, ytd, 1y, 2y, 3y, 5y, max

Config: reads from .env in the same directory as this script.
Copy .env.example to .env and fill in your values.
Required keys: GHOSTFOLIO_URL, ACCESS_TOKEN
"""

import json
import os
import sys
import urllib.request
import urllib.error


# ── Helpers ────────────────────────────────────────────────────────────────────

def _die(msg: str):
    print(json.dumps({"error": msg}))
    sys.exit(1)


def _out(data):
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


# ── Config loading ─────────────────────────────────────────────────────────────

def _load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        _die(
            f".env not found at {env_path}. "
            "Copy .env.example to .env and fill in GHOSTFOLIO_URL and ACCESS_TOKEN."
        )
    env = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    return env


_ENV = _load_env()
GHOSTFOLIO_URL = _ENV.get("GHOSTFOLIO_URL", "").rstrip("/")
ACCESS_TOKEN = _ENV.get("ACCESS_TOKEN", "")
ALLOW_DELETE = _ENV.get("ALLOW_DELETE", "false").lower() == "true"

if not GHOSTFOLIO_URL or not ACCESS_TOKEN:
    _die("GHOSTFOLIO_URL and ACCESS_TOKEN must be set in .env")


# ── Auth ───────────────────────────────────────────────────────────────────────

def get_jwt() -> str:
    url = f"{GHOSTFOLIO_URL}/api/v1/auth/anonymous/{ACCESS_TOKEN}"
    try:
        with urllib.request.urlopen(url) as resp:
            return json.loads(resp.read())["authToken"]
    except urllib.error.HTTPError as e:
        _die(f"Auth failed HTTP {e.code}: {e.read().decode()}")
    except Exception as e:
        _die(f"Auth failed: {e}")


# ── HTTP ───────────────────────────────────────────────────────────────────────

def _request(method: str, path: str, auth_token: str, payload=None):
    url = f"{GHOSTFOLIO_URL}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Authorization": f"Bearer {auth_token}"}
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        _die(f"HTTP {e.code} {method} {path}: {e.read().decode()}")


# ── API ────────────────────────────────────────────────────────────────────────

def get_all_activities(auth_token: str) -> list:
    return _request("GET", "/api/v1/order", auth_token).get("activities", [])


def get_accounts(auth_token: str) -> list:
    return _request("GET", "/api/v1/account", auth_token).get("accounts", [])


def get_portfolio_performance(auth_token: str, range: str = "max") -> dict:
    return _request("GET", f"/api/v2/portfolio/performance?range={range}", auth_token)


def get_portfolio_holdings(auth_token: str) -> dict:
    return _request("GET", "/api/v1/portfolio/holdings", auth_token)


def get_portfolio_details(auth_token: str) -> dict:
    return _request("GET", "/api/v1/portfolio/details", auth_token)


def create_account(name: str, auth_token: str) -> dict:
    return _request("POST", "/api/v1/account", auth_token, {
        "balance": 0,
        "currency": "EUR",
        "isExcluded": False,
        "name": name,
        "platformId": None,
    })


def create_activity(activity: dict, auth_token: str) -> dict:
    return _request("POST", "/api/v1/activities", auth_token, activity)


def import_activities(activities: list, auth_token: str) -> dict:
    return _request("POST", "/api/v1/import", auth_token, {"activities": activities})


def delete_activity(activity_id: str, auth_token: str) -> dict:
    if not ALLOW_DELETE:
        _die("ALLOW_DELETE is not set to true in .env — refusing destructive operation")
    url = f"{GHOSTFOLIO_URL}/api/v1/order/{activity_id}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {auth_token}"},
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return {"status": resp.status, "deleted_id": activity_id}
    except urllib.error.HTTPError as e:
        _die(f"HTTP {e.code} DELETE /api/v1/order/{activity_id}: {e.read().decode()}")


# ── Formatters ────────────────────────────────────────────────────────────────

def _format_performance(raw: dict) -> dict:
    """Extract the most useful fields from a performance response."""
    perf = raw.get("performance", raw)
    return {
        "currentNetWorth": perf.get("currentNetWorth") or perf.get("currentValue") or perf.get("currentValueInBaseCurrency"),
        "totalInvestment": perf.get("totalInvestment") or perf.get("totalInvestmentValueWithCurrencyEffect"),
        "netPerformance": perf.get("netPerformanceWithCurrencyEffect") or perf.get("netPerformance"),
        "netPerformancePct": perf.get("netPerformancePercentageWithCurrencyEffect") or perf.get("netPerformancePercentage"),
        "grossPerformance": perf.get("grossPerformance") or perf.get("grossPerformanceWithCurrencyEffect"),
        "grossPerformancePct": perf.get("grossPerformancePercentage") or perf.get("grossPerformancePercent"),
        "dividends": perf.get("dividendInBaseCurrency") or perf.get("dividend"),
        "fees": perf.get("feesInBaseCurrency") or perf.get("fees"),
        "hasErrors": raw.get("hasErrors"),
        "firstOrderDate": raw.get("firstOrderDate"),
    }


def _format_holdings(raw) -> list:
    """Return a clean list of holdings sorted by current value desc."""
    if isinstance(raw, dict):
        raw = raw.get("holdings", list(raw.values()) if raw else [])
    if not isinstance(raw, list):
        return raw
    items = []
    for h in raw:
        ap = h.get("assetProfile", {})
        items.append({
            "symbol": h.get("symbol"),
            "name": h.get("name") or ap.get("name"),
            "dataSource": h.get("dataSource"),
            "assetClass": h.get("assetClass"),
            "assetSubClass": h.get("assetSubClass"),
            "currency": h.get("currency"),
            "quantity": h.get("quantity"),
            "currentPrice": h.get("marketPrice"),
            "currentValue": h.get("valueInBaseCurrency") or h.get("value"),
            "investment": h.get("investment"),
            "grossPerformance": h.get("grossPerformance"),
            "grossPerformancePct": h.get("grossPerformancePercent"),
            "netPerformance": h.get("netPerformance"),
            "netPerformancePct": h.get("netPerformancePercent"),
            "allocationPct": h.get("allocationInPercentage"),
            "countries": [c.get("name") for c in (h.get("countries") or [])],
            "sectors": [s.get("name") for s in (h.get("sectors") or [])],
        })
    return sorted(items, key=lambda x: (x.get("currentValue") or 0), reverse=True)


def _format_activities(activities: list) -> list:
    """Return a clean activity list with symbol resolved."""
    out = []
    for a in activities:
        sp = a.get("SymbolProfile", {})
        is_manual = sp.get("dataSource") == "MANUAL"
        out.append({
            "id": a.get("id"),
            "type": a.get("type"),
            "date": a.get("date", "")[:10],
            "symbol": sp.get("name") if is_manual else (sp.get("symbol") or a.get("symbol")),
            "dataSource": sp.get("dataSource"),
            "quantity": a.get("quantity"),
            "unitPrice": a.get("unitPrice"),
            "fee": a.get("fee"),
            "currency": a.get("currency"),
            "accountId": a.get("accountId"),
            "accountName": a.get("Account", {}).get("name") if a.get("Account") else None,
            "comment": a.get("comment"),
        })
    return sorted(out, key=lambda x: x.get("date", ""), reverse=True)


def _format_accounts(accounts: list) -> list:
    return [
        {
            "id": a.get("id"),
            "name": a.get("name"),
            "currency": a.get("currency"),
            "balance": a.get("balance"),
            "value": a.get("value"),
            "valueInBaseCurrency": a.get("valueInBaseCurrency"),
            "isExcluded": a.get("isExcluded"),
            "transactionCount": a.get("transactionCount"),
            "platform": a.get("Platform", {}).get("name") if a.get("Platform") else None,
        }
        for a in accounts
    ]


# ── Account resolution ────────────────────────────────────────────────────────

_UUID_PATTERN = frozenset("0123456789abcdef-")

def _resolve_account_id(name_or_id: str, auth_token: str) -> str:
    """Return the account UUID for name_or_id. Passes UUIDs through unchanged."""
    if set(name_or_id.lower()).issubset(_UUID_PATTERN) and len(name_or_id) == 36:
        return name_or_id
    accounts = get_accounts(auth_token)
    for acc in accounts:
        if acc.get("name", "").lower() == name_or_id.lower():
            return acc["id"]
    _die(f"Account not found: '{name_or_id}'. Run `accounts` to list available accounts.")


# ── CLI dispatch ───────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]
    token = get_jwt()

    if cmd == "performance":
        range_ = "max"
        if "--range" in args:
            idx = args.index("--range")
            range_ = args[idx + 1]
        raw = get_portfolio_performance(token, range_)
        _out({"range": range_, **_format_performance(raw)})

    elif cmd == "holdings":
        raw = get_portfolio_holdings(token)
        _out(_format_holdings(raw))

    elif cmd == "details":
        _out(get_portfolio_details(token))

    elif cmd == "activities":
        account_filter = None
        if "--account" in args:
            idx = args.index("--account")
            account_filter = args[idx + 1]
            account_filter = _resolve_account_id(account_filter, token)
        activities = get_all_activities(token)
        if account_filter:
            activities = [a for a in activities if a.get("accountId") == account_filter]
        formatted = _format_activities(activities)
        _out({"count": len(formatted), "activities": formatted})

    elif cmd == "accounts":
        raw = get_accounts(token)
        _out(_format_accounts(raw))

    elif cmd == "create-account":
        if len(args) < 2:
            _die("Usage: create-account <name>")
        name = args[1]
        result = create_account(name, token)
        _out(result)

    elif cmd == "delete-activity":
        if len(args) < 2:
            _die("Usage: delete-activity <id>")
        result = delete_activity(args[1], token)
        _out(result)

    elif cmd == "auth":
        _out({"status": "ok", "authToken": token[:20] + "..."})

    else:
        _die(f"Unknown command: {cmd}. Run without arguments to see usage.")


if __name__ == "__main__":
    main()
