import pandas as pd
import numpy as np

# NOTE: overriding 'int' to a chosen np.int type, we explicitly state it wherever applicable,
# but can manage it here, at the top of the file
int = np.int64


def gem_weights(alpha: float, trunc_n=1_000, trunc_beta: float | None = None):
    """
    Draw a sample from the GEM (Griffiths, Engen, McCloskey) distribution.
    This distribution is explained using stick breaking analogy, where for each element, we
    break off a portion of the unit stick:
        - first part is the probability mass assigned to the element
        - the remaining part is used for subsequent elements
    NOTE: the process (in methematical terms) goes into infinity, so (in practice) we truncate:
        - after `trunc_n`: fixed result vector length (default 1000)
        - after `trunc_beta`: truncates when the remaining weight is smaller than `trunc_beta`
        - the last item gets the remaining weights (ensuring the vector sums to 1)
    """

    proportions = np.random.beta(1, alpha, size=trunc_n)
    # betas (GEM conventional notation) = weights
    betas = proportions * np.concatenate([[1], np.cumprod(1 - proportions[:-1])])

    if trunc_beta is not None:
        betas = betas[betas.cumsum() < (1 - trunc_beta)]

    # Leave the remaining weight with the last bin (ensuring the weights sum to 1)
    betas[-1] += 1 - betas[:-1].sum()
    return betas


df_books = pd.read_csv("./data/books.csv")
df_warehouses = pd.read_csv("./data/warehouses.csv")
df_notes = pd.read_csv("./data/notes.csv")

n_books = len(df_books)
n_notes = len(df_notes)
n_warehouses = len(df_warehouses)

# Draw a random book catalog (a subset of fool list of ISBNs)
#
# Draw weights -- this setup draws approx 160 non-zero probability masses
weights = gem_weights(30, 300, 1 / 200)
catalogue_size = len(weights)
# Draw "atoms" from the full ISBN list -- assigning a particular weight (probability mass) to each
catalogue_index = np.random.randint(0, n_books, size=catalogue_size, dtype=int)

K = n_warehouses
"""Number of warehouses"""
M = n_notes
"""Number of notes (excluding reconciliation notes)"""
N = catalogue_size
"""Catalogue size - the number of ISBNs we're tracking (randomly drawn from the full list of ISBNs)"""

# Preallocate a matrix to fill with book counts for each note:
# - a single row represents a single note
# - each row represents a quantity "mask" (not in the strictest sense, as it can be > 1)
# - each column in a row represents quantity for a particular book (from the drawn catalog)
txn_matrix = np.zeros((M, N), dtype=int)

# When drawing from multinomial, we can draw multiple vectors (1 vector = 1 row in transaction matrix).
# However, we need to specify the total quantity we're drawing for each vector, therefore, we:
# - categorise notes by their n_books (total quantity) value
# - iterate over each category
# - use df_notes[n_books == count] as a mask to store each draw as appropriate note
for count, freq in df_notes["n_books"].value_counts().items():
    quantities = np.random.multinomial(count, weights, size=freq)
    # Casting to int8 as we'll be dealing with huge arrays (value is clipped at 127,
    # although the probability of a single quantity being greater than that is astronomical)
    txn_matrix[df_notes["n_books"] == count] = quantities.astype(int)


warehouse_id = np.repeat(df_notes["warehouse_id"].to_numpy(int), N).reshape(
    txn_matrix.shape
)

# Assign random warehouse id to every outbound note txn
# NOTE: we're doing this for non-zero quantities only (representing actual transaction quantity and not just an ISBN placeholder for a note)
outbound_mask = (warehouse_id == 0) & (txn_matrix != 0)
n_outbound_txns = len(warehouse_id[outbound_mask])
# Randomise the index and sample from the list of warehouse ids
warehouse_id[outbound_mask] = df_warehouses["id"][
    np.random.randint(0, n_warehouses, size=n_outbound_txns, dtype=int)
]

# Allocate a new txn_matrix, adding additional dimension for warehouses
# We're doing the following dimensions: K x M*2 x N
# - K - number of warehouses
# - M - number of notes * 2 -- 2 as we're reindexing existing inbound/outbound notes
#       to every other place, leaving room for, would be, insertion of reconciliation notes)
# - N - catalogue size - a vector of quantities, matching ISBN (catalogue) index for every (warehouse x note)
# NOTE: each warehouse's note x catalogue matrix is flattened for index compatibility with existing txns quantities
w_txn_tnsr = np.zeros((K, M, N), dtype=int)
"""
3D tensor to hold transaction quantities across notes and warehouses, shape: (K, M, N):
    - K: Number of warehouses
    - M: Number of notes 
    - N: Catalogue size (number of tracked ISBNs)
    - each [k, m, n] represents the quantity of the n-th book in m-th note for k-th warehouse
"""

# NOTE: Using for loop here (instead of a hige mask) as K (number of warehouses) will generally be small (heuristically this will be more efficient)
for w_ix, w_id in enumerate(df_warehouses["id"].values):
    # Index - used to index into the new txn_matrix
    # Id - used for filtering quantities by warehouse id
    mask = warehouse_id == w_id
    # Index explained:
    # - [w_ix] - trivial - access the first "item" at the first dimension (warehouse's note x catalogue)
    # - [1::2] - index transactions 1, 3, 5, etc... (remember we're leaving 0, 2, 4, ... for reconciliation notes)
    # - w_txn_tnsr[w_ix][1::2] has the same shape as txn_matrix and warehouse_id (M x N)
    # - apply mask to both in order to filter only transactions relevant to the current warehouse
    w_txn_tnsr[w_ix][mask] = txn_matrix[mask]


# Calculate stock for each warehouse, at (after) every note

note_index = np.tile(np.repeat(np.arange(M, dtype=int), N), K)

# A pseudo-mask:
# - mask out quantities belonging to non-committed notes (multiply by 0)
# - negate the quantities belonging to outbound notes (reducing stock)
stock_mask = np.ones(len(note_index), dtype=int)
stock_mask *= df_notes["committed"].to_numpy(int)[note_index]
# Producing negative factor for outbound notes:
# - clip at 1: all non-zero values (inbound notes) become 1
# - multiply by 2:
#    - inbound become 1
#    - outbound remain 0
# - subtract 1:
#    - inbound become 1
#    - outbound become -1
stock_mask *= (df_notes["warehouse_id"].to_numpy(int).clip(max=1) * 2 - 1)[note_index]
stock_mask = stock_mask.reshape((K, M, N))

stock_tnsr = (w_txn_tnsr * stock_mask).cumsum(axis=1)
"""
3D tensor of same shape as w_txn_tnsr (K, M, N), holding preliminary stock counts for each book in each warehouse after each note.
"""

# Using Skorokhod reflection to solve the problem of negative stock (thanks ChatGPT):
# In plain english:
# - we use cumsum to get stock (for each book in a particular warehouse) at each point in time (at each note)
# - the first time we observe negative stock (e.g. -2), we need to fix that (1st fix we'll apply)
# - after applying the first fix, all subsequent cumsum >= -2 is >= 0 (with 1st fix applied)
# - if the cumsum becomes more negative (than -2 in this case, e.g. -3), with 1st fix applied,
#   we need to add additional 1 (2nd fix) to make the cumsum go back up to 0
# - rinse and repeat
#
# Regulator keeps track of the most negative stock we've seen up to each note
# Taking the diff of the regulator gives us the exact amount we need to add (reconcile) at each note
regulator = np.maximum(0, -np.minimum.accumulate(stock_tnsr, axis=1))

recon_tnsr = np.zeros((K, M, N), dtype=int)
"""
3D tensor of same shape as w_txn_tnsr (K, M, N), holding reconciliation counts for a particular book in a particular warehouse at each note
"""
recon_tnsr[:, 0] = regulator[:, 0]
recon_tnsr[:, 1:] = regulator[:, 1:] - regulator[:, :-1]

w_txn_tnsr = w_txn_tnsr.transpose(1, 0, 2).reshape((M, K * N))
recon_tnsr = recon_tnsr.transpose(1, 0, 2).reshape((M, K * N))

# Insert a (would-be) reconciliation note before each note (0 total quantity "notes" will get removed later)
txns = np.hstack([recon_tnsr, w_txn_tnsr]).reshape((M * 2, K * N))

# Get non-empty reconciliation note transactions and create corresponding notes
note_ttls = txns.sum(axis=1)
note_ttls_index = np.arange(len(note_ttls))
# Reconciliation note is inserted before each existing note (indexes 0, 2, 4, ...). However, some reconciliation notes
# might not include any non-zero transactions and get filtered out.
non_empty_recon_mask = (note_ttls != 0) & (note_ttls_index % 2 == 0)

recon_note_ttls = note_ttls[non_empty_recon_mask]
recon_note_index = note_ttls_index[non_empty_recon_mask]

# In order to index a reconciliatin notes to the correct note (which note will this reconciliation note precede)
# we need to reindex the note with respect to notes existing in prelimitary df
recon_note_ts = df_notes["committed_at"][recon_note_index / 2]

df_recon_notes = pd.DataFrame({
    "id": 0,  # Not important here, we're reindexing later anyway
    # TODO: update this after the note generating script is updated to store ms values (not ts)
    "display_name": "Reconciliation note: " + recon_note_ts,
    "warehouse_id": 0,
    "is_reconciliation_note": 1,
    "default_warehouse": 0,
    "updated_at": recon_note_ts,
    "committed": 1,
    "committed_at": recon_note_ts,
    "n_books": recon_note_ttls,
})

# Move notes in df_notes to make room for reconciliation notes
# - recon notes 0, 2, 4, ...
# - non-recon notes 1, 3, 5, ...
df_notes.index *= 2
df_notes.index += 1
df_recon_notes.index = recon_note_index

# Combine the two dataframes
df_notes = pd.concat([df_notes, df_recon_notes]).sort_index().reset_index(drop=True)
# Reindex ids (1 base)
df_notes["id"] = np.arange(1, len(df_notes) + 1, dtype=int)

# Clear empty notes from txns
txns = txns.reshape((M * 2, K * N))[note_ttls != 0]

if len(df_notes) != len(txns):
    raise ValueError(
        "Error: number of notes in the data frame and number of non-empty notes (based on transactions) do not match"
    )


# Check that note totals match in both the (updated) input data frame and the generated transactions
if len(df_notes) != (df_notes["n_books"] == note_ttls[note_ttls != 0]).sum():
    raise ValueError(
        "Error: total books in notes and generated transactions do not match"
    )


# Create indices to keep track of note/warehouse/isbn data as we filter out zeros

# Current shape of txns is M_ x (K * N) so we can calculate the number of notes like this
M_ = len(txns)
"""Number of non-empty notes"""

# Flatten the transaction tensor to 1-D array for filtering
txns = txns.reshape(-1)

note_index = np.repeat(np.arange(M_), K * N)
warehouse_index = np.tile(np.repeat(np.arange(K), N), M_)
isbn_index = np.tile(np.arange(N), M_ * K)

# Filter 0-quantity transactions -- even though we've filtered empty notes,
# there are still (a lot of) 0-quantity transactions
mask = txns != 0

isbn_index = catalogue_index[isbn_index[mask]]
isbn = df_books["isbn"].to_numpy()[isbn_index]

quantity = txns[mask]

# Notes have been reindexed (filtering out empties), so we need to recreate note_index
# NOTE: While warehouse ids and isbns are indexed on the entire M*2 x K x N tensor
note_index = note_index[mask]
note_id = df_notes["id"].to_numpy()[note_index]

warehouse_index = warehouse_index[mask]
warehouse_id = df_warehouses["id"].to_numpy()[warehouse_index]

updated_at = df_notes["updated_at"].to_numpy()[note_index]
committed_at = df_notes["committed_at"].to_numpy()[note_index]

# book_transaction (
# 	isbn TEXT NOT NULL,
# 	quantity INTEGER NOT NULL DEFAULT 0,
# 	note_id INTEGER NOT NULL,
# 	warehouse_id INTEGER NOT NULL DEFAULT 0,
# 	updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000),
# 	committed_at INTEGER,
# );

np.array([
    len(isbn),
    len(quantity),
    len(note_id),
    len(warehouse_id),
    len(updated_at),
    len(committed_at),
]).min()


df_transactions = pd.DataFrame({
    "isbn": isbn,
    "quantity": quantity,
    "note_id": note_id,
    "warehouse_id": warehouse_id,
    "updated_at": updated_at,
    "committed_at": committed_at,
})
df_transactions.to_csv("./data/book_transactions.csv", index=False)

# note (
# 	id INTEGER NOT NULL,
# 	display_name TEXT,
# 	warehouse_id INTEGER,
# 	is_reconciliation_note INTEGER DEFAULT 0,
# 	default_warehouse INTEGER,
# 	updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
# 	committed INTEGER NOT NULL DEFAULT 0,
# 	committed_at INTEGER,
# );

df_notes = df_notes[
    [
        "id",
        "display_name",
        "warehouse_id",
        "is_reconciliation_note",
        "default_warehouse",
        "updated_at",
        "committed",
        "committed_at",
        "n_books",
    ]
]
df_notes.to_csv("./data/notes-final.csv", index=False)
