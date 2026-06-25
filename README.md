# Blunt

**Management and operational productivity for developers who wish to do neither.**

> *"You can't run the sharp end of the business from the blunt end."*

`blunt` is a zero-dependency-by-default CLI toolkit for publishing data, managing calendars, and automating the boring administrative layer of engineering work.

---

## Installation

```bash
pip install blunt
```

Requires Python 3.10+.

---

## `syndicate` — publish data across destinations

`syndicate` mirrors content to external services idempotently: re-running the same command is always safe.

### `syndicate sheets` — publish CSV/TSV to Google Sheets

Push a single file or a whole directory of CSV/TSV files to a Google Spreadsheet. On re-run, existing sheets are updated in place — tabs are added, cleared, and rewritten; stale tabs are removed.

```bash
# Single file → one spreadsheet, one tab
syndicate sheets report.csv

# Directory → one spreadsheet, one tab per file
syndicate sheets data/

# Override the spreadsheet title
syndicate sheets data/ --name "Q2 Engineering Metrics"

# Prepend a prefix to the derived title
syndicate sheets data/ --name-prefix "[PROD] "

# Publish into a specific Drive folder
syndicate sheets data/ --folder 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE
```

**Options**

| Flag | Default | Description |
|---|---|---|
| `--name NAME` | *(derived from path)* | Override the spreadsheet title entirely |
| `--name-prefix PREFIX` | — | Prepend a prefix to the derived title |
| `--folder FOLDER_ID` | My Drive root | Drive folder ID to create/sync within |
| `--credentials PATH` | `$GOOGLE_CREDENTIALS` or `~/.gcloud/credentials.json` | OAuth client secrets file |
| `--token PATH` | next to `--credentials` | Where to cache the OAuth token |

**Authentication**

`syndicate sheets` uses the OAuth installed-app flow with the `drive.file` scope — it can only see spreadsheets it created, never your existing files.

1. Download a *Desktop* OAuth client from the [Google Cloud Console](https://console.cloud.google.com/apis/credentials) and save it as `credentials.json`.
2. On first run a browser tab opens for consent; subsequent runs refresh silently.

```bash
export GOOGLE_CREDENTIALS=~/.gcloud/credentials.json
syndicate sheets my_data.csv
```

---

## `meet` — calendar assistant

Query and display calendar events from the command line.

```bash
meet
```

---

## `blunt.cal` — calendar utilities

```bash
python -m blunt.cal
```

---

## `dossier` — profile/contact management

```bash
dossier
```

---

## `widget` — macOS menu bar status

Shows live GitHub PR status in the macOS menu bar next to the clock.

```bash
# Set credentials
export GITHUB_USER=your-username
export GITHUB_TOKEN=your-token

python -m widget
```

Requires `rumps` (macOS only, installed automatically on Darwin).

---

## Development

```bash
git clone https://github.com/trevorgrayson/blunt
cd blunt
pip install -e ".[dev]"
pytest
```

---

## License

Copyright (c) 2026 Trevor Grayson. All rights reserved.
