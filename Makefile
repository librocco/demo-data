dir.crsql := $(CURDIR)/cr-sqlite

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
	SQLITE_FILE_EXT := dylib
else 
	SQLITE_FILE_EXT := so
endif
CRSQL_LOADABLE := $(dir.crsql)/core/dist/crsqlite.$(SQLITE_FILE_EXT)

.PHONY: all
all: submodules deps data/books.csv data/warehouses.csv data/notes.csv data/book_transactions.csv

.PHONY: clean
clean:
	rm -f data/*

.PHONY: spotless
spotless: clean
	rm -rf $(dir.crsql)/core/dist

.PHONY: submodules
submodules: 
	git submodule update --init --recursive

.PHONY: deps
deps:
	pip install -r requirements.txt

# NOTE: this currently doesn't work as we'd want it to (google API is severely rate-limited)
# We probably want to generate data using faker or fetch prefetched .csv from a bucket or smtn
data/books.csv: 
	python buf.py

data/warehouses.csv: 
	python generate_warehouse_data.py

data/notes_prelim.csv: 
	python generate_note_data.py

data/book_transactions.csv data/notes.csv: data/books.csv data/warehouses.csv data/notes_prelim.csv
	python generate_book_transactions.py

data/demo_db.sqlite3: $(CRSQL_LOADABLE) data/book_transactions.csv data/notes.csv data/books.csv data/warehouses.csv 
	sqlite3 data/demo_db.sqlite3<init.sql
	python load_db.py

$(CRSQL_LOADABLE): 
	cd $(dir.crsql) && make



