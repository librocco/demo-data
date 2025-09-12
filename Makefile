.PHONY: all
all: deps data/books.csv data/warehouses.csv data/notes.csv data/book_transactions.csv

.PHONY: clean
clean:
	rm -f data/*

.PHONY: deps
deps:
	pip install -r requirements.txt

# NOTE: this currently doesn't work as we'd want it to (google API is severely rate-limited)
# We probably want to generate data using faker or fetch prefetched .csv from a bucket or smtn
data/books.csv: 
	python fetch_book_data.py

data/warehouses.csv: 
	python generate_warehouse_data.py

data/notes_prelim.csv: 
	python generate_note_data.py

data/book_transactions.csv data/notes.csv: data/books.csv data/warehouses.csv data/notes_prelim.csv
	python generate_book_transactions.py



