#!/usr/bin/env python3
"""Regenerate data.json from the Notion Destinations database.

Runs in GitHub Actions. Needs two environment variables:

  NOTION_TOKEN        internal integration secret (repository secret)
  NOTION_DATABASE_ID  the Destinations database id

Country shapes are keyed by ISO 3166-1 numeric codes. A destination gets its
codes from either:

  1. a "Map countries" text property on the Notion page, e.g. "276" or "32, 152"
     (preferred - a new destination maps itself with no code change), or
  2. codes.json in this repository, keyed by destination name (fallback).

Destinations with no codes are reported in data.json under "unmapped" rather
than silently disappearing.
"""

import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

TOKEN = os.environ.get("NOTION_TOKEN", "").strip()
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "").strip()

if not TOKEN or not DATABASE_ID:
    sys.exit("NOTION_TOKEN and NOTION_DATABASE_ID must both be set")


def post(path, payload):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": "Bearer " + TOKEN,
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:600]
        if e.code in (401, 403):
            sys.exit(
                "Notion rejected the request (%s). Check that the integration token is "
                "correct and that the Destinations database is shared with the "
                "integration.\n%s" % (e.code, body)
            )
        if e.code == 404:
            sys.exit(
                "Notion could not find database %s (404). The integration probably "
                "does not have access to it yet.\n%s" % (DATABASE_ID, body)
            )
        sys.exit("Notion API error %s: %s" % (e.code, body))


def plain(prop):
    """Best-effort readable value for any Notion property type."""
    if not prop:
        return ""
    t = prop.get("type")
    v = prop.get(t)
    if t in ("title", "rich_text"):
        return "".join(part.get("plain_text", "") for part in (v or [])).strip()
    if t in ("select", "status"):
        return (v or {}).get("name", "") or ""
    if t == "multi_select":
        return ", ".join(o.get("name", "") for o in (v or []))
    if t == "number":
        return "" if v is None else str(v)
    if t == "formula":
        inner = v or {}
        return str(inner.get(inner.get("type"), "") or "")
    return "" if v is None else str(v)


def find(props, *names):
    """Case-insensitive property lookup, tolerant of renames."""
    lowered = {k.lower(): k for k in props}
    for n in names:
        key = lowered.get(n.lower())
        if key:
            return props[key]
    return None


codes_path = ROOT / "codes.json"
NAME_CODES = json.loads(codes_path.read_text(encoding="utf-8")) if codes_path.exists() else {}

rows = []
unmapped = []
cursor = None

while True:
    payload = {"page_size": 100}
    if cursor:
        payload["start_cursor"] = cursor
    res = post("/databases/%s/query" % DATABASE_ID, payload)

    for page in res.get("results", []):
        props = page.get("properties", {})
        name = plain(find(props, "Name", "Title", "Destination"))
        if not name:
            continue
        status = plain(find(props, "Status"))
        budget = plain(find(props, "Budget"))
        continent = plain(find(props, "Continent"))

        declared = plain(find(props, "Map countries", "Map codes", "Country codes"))
        codes = [int(x) for x in re.findall(r"\d{1,3}", declared)] if declared else []
        if not codes:
            codes = list(NAME_CODES.get(name, []))

        row = {"name": name, "status": status, "budget": budget, "c": codes}
        if continent:
            row["continent"] = continent

        if not codes and status != "In Review":
            unmapped.append(name)
        rows.append(row)

    if not res.get("has_more"):
        break
    cursor = res.get("next_cursor")

rows.sort(key=lambda r: r["name"].lower())

data = {
    "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "source": "notion",
    "unmapped": sorted(unmapped),
    "destinations": rows,
}

(ROOT / "data.json").write_text(
    json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
)

print("destinations: %d" % len(rows))
if unmapped:
    print("no country codes yet (not drawn): " + ", ".join(sorted(unmapped)))
