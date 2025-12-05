#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pandas",
#   "numpy",
# ]
# ///

import pandas as pd
import numpy as np

# warehouse (
#     id INTEGER NOT NULL CHECK (id <> 0),
#     display_name TEXT,
#     discount DECIMAL DEFAULT 0,
# );

warehouses = np.array([
    "Used books (2022)",
    "New books (2022)",
    "Used books (2023)",
    "New books (2023)",
    "Used books (2024)",
    "New books (2024)",
    "Used books (2025)",
    "New books (2025)",
])
discounts = np.array([20, 0, 15, 0, 10, 0, 5, 0])
n_warehouses = len(warehouses)
df = pd.DataFrame({
    "id": np.arange(1, n_warehouses + 1),
    "display_name": warehouses,
    "discount": discounts,
})

df.to_csv("./data/warehouses.csv", index=False)
