#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pandas",
#   "numpy",
# ]
# ///

import pandas as pd
import numpy as np

w_df = pd.read_csv("./data/warehouses.csv")
n_warehouses = len(w_df)

# note (
# 	id INTEGER NOT NULL,
# 	display_name TEXT,
# 	warehouse_id INTEGER,
# 	is_reconciliation_note INTEGER DEFAULT 0,
# 	default_warehouse INTEGER,
# 	updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
# 	committed INTEGER NOT NULL DEFAULT 0,
# 	committed_at INTEGER,
# )

# Empirically, using production data
p_inbound = 1 / 3  # Probability of a note being inbound
total_notes = 15_000

# The empirical distributions resemble geometric distributions
max_n_books_inbound = 300  # Empirical max = 271
n_book_prob_inbound = 1 / 8  # Emprical mean = 8
n_book_prob_outbound = 1 / 3  # Emprical mean = 3


ids = np.arange(1, total_notes + 1)

# A flag whether or not a note is inbound: 1s will will be replaced with warehouse_id
inbound = np.random.binomial(1, p_inbound, total_notes)
# Ensure we start with 1 inbound note per each warehouse
inbound[:n_warehouses] = 1

# Our book store is open 24-7 ;)
start_date = pd.Timestamp("2025-01-01").timestamp()
end_date = pd.Timestamp("2025-08-31").timestamp()
second_range = end_date - start_date
updated_at_sec = np.random.exponential(scale=1, size=total_notes).astype(int).cumsum()
scaler = second_range / updated_at_sec[-1]
updated_at_sec = np.round(updated_at_sec * scaler + start_date)
updated_at = pd.to_datetime(updated_at_sec, unit="s")

df = pd.DataFrame({
    "id": ids,
    "display_name": "",
    "warehouse_id": np.zeros(total_notes, dtype=int),
    "is_reconciliation_note": np.zeros(total_notes, dtype=int),
    "default_warehouse": np.zeros(total_notes, dtype=int),
    "updated_at": updated_at,
    "committed": np.zeros(total_notes, dtype=int),
    "committed_at": pd.NaT,
    "_inbound": inbound,
})

# Warehouse ids - assigned only to inbound notes
n_inbound = len(df[df["_inbound"] == 1])
n_outbound = len(df[df["_inbound"] == 0])

# Display names are generated based on enumeration, e.g. Purchase, Purchase (1), Purchase (2), etc.
df["display_name"] = ""
df.loc[df["_inbound"] == 1, "display_name"] = (
    "Purchase (" + np.arange(1, n_inbound + 1).astype(str) + ")"
)
df.loc[df["_inbound"] == 0, "display_name"] = (
    "Sale (" + np.arange(1, n_outbound + 1).astype(str) + ")"
)

df.loc[df["_inbound"] == 1, "warehouse_id"] = np.random.randint(
    1, n_warehouses + 1, size=n_inbound
)
# Make sure we start with 1 inbound note per each warehouse
df.loc[: n_warehouses - 1, "warehouse_id"] = np.arange(1, n_warehouses + 1)


# n_books
df.loc[df["_inbound"] == 1, "n_books"] = np.random.geometric(
    n_book_prob_inbound, size=n_inbound
)
df.loc[df["_inbound"] == 0, "n_books"] = np.random.geometric(
    n_book_prob_outbound, size=n_outbound
)
# Initial inbound notes contain max inbound number of books
df.loc[: n_warehouses - 1, "n_books"] = max_n_books_inbound

# 	committed INTEGER NOT NULL DEFAULT 0,
df["_committed_rand"] = np.random.uniform(0, 1, size=total_notes)
df["_days_to_last"] = ((pd.Timestamp("2025-08-31") - df["updated_at"]).dt.days) + 1
# P(not committed) = 0.5^(days_to_last + 1)
df["_committed_threshold"] = np.exp(df["_days_to_last"] * np.log(0.5))
df["committed"] = (df["_committed_rand"] > df["_committed_threshold"]).astype(int)

# Committed at (if committed) 10mins after updated at
df.loc[df["committed"] == 1, "committed_at"] = df["updated_at"] + pd.to_timedelta(
    "10 min"
)

df.drop(
    columns=["_inbound", "_committed_rand", "_days_to_last", "_committed_threshold"],
    inplace=True,
)

df["updated_at"] = df["updated_at"].astype(np.int64) // 10**6
df["committed_at"] = df["committed_at"].astype(np.int64) // 10**6
# Negative timestamp is a consequence of pd.NaT, we convert those to pd.NA (corresponding to NULL when it gets to SQLite)
df.loc[df["committed_at"] < 0, "committed_at"] = pd.NA

df.to_csv("./data/notes_prelim.csv", index=False)
