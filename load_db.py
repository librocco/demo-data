#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pandas",
#   "numpy",
#   "sqlalchemy",
# ]
# ///

import pandas as pd
import numpy as np

SQLITE_FILE = "sqlite:///data/demo_db.sqlite3"


def drop_excess_cols(df, whitelist):
    cols = filter(lambda col: col not in whitelist, df.columns)
    df.drop(columns=cols, inplace=True)


df_books = pd.read_csv("data/books.csv")
drop_excess_cols(
    df_books,
    [
        "isbn",
        "title",
        "authors",
        "price",
        "year",
        "publisher",
        "edited_by",
        "out_of_print",
        "category",
        "updated_at",
    ],
)
df_books.to_sql("book", SQLITE_FILE, if_exists="append", index=False)

df_warehouses = pd.read_csv("data/warehouses.csv")
drop_excess_cols(
    df_warehouses,
    [
        "id",
        "display_name",
        "discount",
    ],
)
df_warehouses.to_sql("warehouse", SQLITE_FILE, if_exists="append", index=False)

df_notes = pd.read_csv("data/notes.csv")
drop_excess_cols(
    df_notes,
    [
        "id",
        "display_name",
        "warehouse_id",
        "is_reconciliation_note",
        "default_warehouse",
        "updated_at",
        "committed",
        "committed_at",
    ],
)

# NOTE: Make sure warehouse 0 = NULL in the DB (outbound notes)
df_notes.loc[df_notes["warehouse_id"] == 0, "warehouse_id"] = np.nan
df_notes.to_sql("note", SQLITE_FILE, if_exists="append", index=False)

df_book_transactions = pd.read_csv("data/book_transactions.csv")
drop_excess_cols(
    df_book_transactions,
    [
        "isbn",
        "quantity",
        "note_id",
        "warehouse_id",
        "updated_at",
        "committed_at",
    ],
)
df_book_transactions.to_sql(
    "book_transaction", SQLITE_FILE, if_exists="append", index=False
)
