# School HQ Sync
This automation reads the private Canvas calendar feed, upserts Canvas deadlines into
the existing Notion **Master To-Do List**, and creates small study sessions that answer
“what should I do today?” without encouraging cramming.

## Planning rules

- Maximum planned study time: **60 minutes per day**.
- Normal study days: **Sunday through Thursday**.
- Friday and Saturday are optional overflow days only.
- Each upcoming assignment receives one to three 30-minute sessions, based on how far
  away it is. The closest due dates get capacity first.
- **Career Development is excluded**.
- The plan looks ahead 14 days and is rebuilt every morning, so a changed Canvas due
  date automatically changes the next plan.
- Stable Canvas and study-session source IDs make reruns safe; items are updated rather
  than duplicated.

## Required Notion properties

The database must have these two properties:

| Property | Type |
|---|---|
| `Name` | Title |
| `Due Date` | Date |

The stable ID field is also required so reruns cannot create duplicates:

| Property | Type |
|---|---|
| `Source ID` | Text |

These properties are optional but recommended. The sync detects their actual type and
uses them when compatible:

| Property | Supported type |
|---|---|
| `Status` | Status or Select |
| `Course` | Select, Multi-select, or Text |
| `Type` | Select, Multi-select, or Text |
| `Notes` | Text |

Property names can be overridden with the variables shown in `.env.example`.

## GitHub setup

Add these repository secrets under **Settings → Secrets and variables → Actions**:

1. `CANVAS_ICS_URL` — Canvas → Calendar → Calendar Feed; copy the private `.ics` URL.
2. `NOTION_TOKEN` — the token for the integration already connected to School HQ.
3. `NOTION_DATABASE_ID` — the 32-character ID from the Master To-Do List URL.

Then open **Actions → Sync Canvas to School HQ → Run workflow** for the first test.
After that, GitHub Actions runs it every morning. Canvas calendar-feed URLs and Notion
tokens are secrets and must never be committed.

## Local test

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

To perform a real local sync, export the values from `.env.example` and run:

```bash
python -m school_hq.cli
```
