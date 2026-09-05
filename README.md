# Travel map

A self-updating world map of the destinations in my Notion **Destinations** database.
It is embedded at the top of my Notion *Travel Bucket List* page.

Nothing here needs to be rebuilt by hand. The map reads `data.json`, and `data.json`
is regenerated from Notion by a scheduled GitHub Action.

```
Notion database  ->  GitHub Action (every 5 min)  ->  data.json  ->  the map embedded in Notion
```

## Files

| File | What it is |
| --- | --- |
| `data.json` | Generated. Destination name, status, budget and ISO 3166-1 numeric country codes. |
| `codes.json` | Destination name -> country codes. Fallback for destinations with no codes set in Notion. |
| `scripts/build_data.py` | Queries the Notion API and writes `data.json`. Standard library only. |
| `.github/workflows/update-map.yml` | Runs the script on a schedule, on demand, and when the pipeline changes. Commits `data.json` only when it differs. |


## How a destination gets onto the map

Country shapes are keyed by ISO 3166-1 numeric codes, so each destination needs at least
one code. Codes come from, in order:

1. A **Map countries** text property on the Notion page, e.g. `276`, or `32, 152` for a trip
   spanning two countries. Preferred: a brand new destination maps itself with no change to
   this repository.
2. `codes.json`, keyed by exact destination name.

A destination with neither is listed in `data.json` under `unmapped` instead of quietly
vanishing.

Destinations with status **In Review** are deliberately excluded - they are drafts.
Approving one flips it to *Want to go*, which is when it appears on the map.

## Notes

- Country outlines are fetched from the public `world-atlas` package on a CDN, with two
  fallback hosts.
- The map keeps a baked-in copy of the last known data. If the network request fails it
  shows that instead of an empty map, and labels itself an offline copy.
- GitHub suspends scheduled workflows in a repository with no activity for 60 days. The
  bot's own commits count as activity.
- Scheduled runs on GitHub are best-effort and can lag a few minutes at busy times.
