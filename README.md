# Demo Data Generator

Generates a demo SQLite database for librocco with realistic book inventory data.

## Architecture

This pipeline creates demo data by:

1. **Downloading book metadata** from a pre-generated CSV (originally fetched from Google Books API)
2. **Generating warehouse data** - 8 warehouses representing used/new books across years 2022-2025
3. **Generating notes** - ~15,000 inventory notes (inbound purchases and outbound sales)
4. **Generating transactions** - Book transactions with realistic statistical distributions
5. **Loading into SQLite** - Final database with schema pulled from main librocco repo

### Statistical Modeling

The data generation uses several statistical techniques for realism:

- **GEM distribution** (Griffiths, Engen, McCloskey): Creates Zipfian-like popularity distribution for the book catalog - a small number of books are very popular, most are rarely sold
- **Geometric distribution**: Models the number of books per note (mean ~8 for inbound, ~3 for outbound)
- **Exponential distribution**: Spreads timestamps across Jan-Aug 2025, weighted toward recent dates
- **Skorokhod reflection**: Mathematical technique to ensure stock never goes negative - automatically inserts reconciliation notes when needed

### Schema Sync

The database schema is downloaded directly from the main librocco repository at build time:
```
https://raw.githubusercontent.com/librocco/librocco/refs/heads/main/apps/sync-server/schemas/init
```

The `crsql_as_crr` calls are filtered out since plain SQLite doesn't have the CRSQLite extension.

This ensures the demo database always matches the current application schema.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) - Python package manager (scripts use inline deps)
- `curl` - For downloading files
- `sqlite3` - CLI tool for database creation
- `BOOKS_CSV_URL` environment variable - URL to pre-generated books.csv (for CI)

## Usage

### Build the demo database (CI/production)

```bash
BOOKS_CSV_URL=<url> make
```

Or set the env var in `.env` or export it.

### Build locally (fetch books from Google Books API)

```bash
./fetch_book_data.py  # Fetches ~600+ books (rate-limited without API key)
make                  # Skips books.csv download since it exists
```

Optionally set `GOOGLE_BOOKS_API_KEY` for higher rate limits.

Output: `data/demo_db.sqlite3`

### Clean generated files

```bash
make clean
```

### Individual targets

```bash
make data/warehouses.csv    # Generate warehouse data only
make data/notes.csv         # Generate notes and transactions
make data/demo_db.sqlite3   # Build final database
```

## Pipeline Overview

```
BOOKS_CSV_URL ─────────────────────────────────────────┐
                                                       │
GitHub (schema) ──────────────────────────────────────┐│
                                                      ││
                                                      ▼▼
┌─────────────────────────┐    ┌────────────────────────────────┐
│ generate_warehouse_data │    │         books.csv              │
│          .py            │    │    (downloaded from URL)       │
└───────────┬─────────────┘    └───────────────┬────────────────┘
            │                                  │
            ▼                                  │
    ┌───────────────┐                          │
    │warehouses.csv │                          │
    └───────┬───────┘                          │
            │                                  │
            ▼                                  │
┌───────────────────────┐                      │
│  generate_note_data   │                      │
│         .py           │                      │
└───────────┬───────────┘                      │
            │                                  │
            ▼                                  │
   ┌─────────────────┐                         │
   │notes_prelim.csv │                         │
   └────────┬────────┘                         │
            │                                  │
            └──────────────┬───────────────────┘
                           │
                           ▼
           ┌───────────────────────────┐
           │generate_book_transactions │
           │           .py             │
           └─────────────┬─────────────┘
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
   ┌─────────────────┐     ┌────────────────────┐
   │    notes.csv    │     │book_transactions.csv│
   └────────┬────────┘     └──────────┬─────────┘
            │                         │
            └────────────┬────────────┘
                         │
                         ▼
              ┌─────────────────┐
              │   load_db.py    │◄──── schema.sql (from GitHub)
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │demo_db.sqlite3  │
              └─────────────────┘
```

## Data Details

### Warehouses (8 total)

| ID | Name | Discount |
|----|------|----------|
| 1 | Used books (2022) | 20% |
| 2 | New books (2022) | 0% |
| 3 | Used books (2023) | 15% |
| 4 | New books (2023) | 0% |
| 5 | Used books (2024) | 10% |
| 6 | New books (2024) | 0% |
| 7 | Used books (2025) | 5% |
| 8 | New books (2025) | 0% |

### Notes (~15,000)

- ~1/3 inbound (purchases), ~2/3 outbound (sales)
- Each warehouse starts with one large inbound note
- Timestamps: Jan 1 - Aug 31, 2025
- Commitment probability increases with age

### Transactions

- ~160 ISBNs selected from full catalog using GEM distribution
- Multinomial sampling distributes books across notes
- Reconciliation notes automatically inserted to prevent negative stock

## GitHub Actions

The workflow in `.github/workflows/on-push.yml` builds the database on every push using the `BOOKS_CSV_URL` secret.
