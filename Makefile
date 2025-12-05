DATA_DIR := data
SCHEMA_URL := https://raw.githubusercontent.com/librocco/librocco/main/apps/sync-server/schemas/init

.PHONY: all
all: $(DATA_DIR)/books.csv $(DATA_DIR)/warehouses.csv $(DATA_DIR)/notes.csv $(DATA_DIR)/book_transactions.csv $(DATA_DIR)/demo_db.sqlite3

.PHONY: clean
clean:
	find $(DATA_DIR) -type f ! -name 'books.csv' -delete

$(DATA_DIR):
	mkdir -p $@

$(DATA_DIR)/schema.sql: | $(DATA_DIR)
	curl -sL $(SCHEMA_URL) | grep -v 'crsql_as_crr\|crsql_finalize' > $@

# books.csv is checked into git - regenerate with: ./fetch_book_data.py

$(DATA_DIR)/warehouses.csv: | $(DATA_DIR)
	./generate_warehouse_data.py

$(DATA_DIR)/notes_prelim.csv: $(DATA_DIR)/warehouses.csv | $(DATA_DIR)
	./generate_note_data.py

$(DATA_DIR)/book_transactions.csv $(DATA_DIR)/notes.csv: $(DATA_DIR)/books.csv $(DATA_DIR)/warehouses.csv $(DATA_DIR)/notes_prelim.csv
	./generate_book_transactions.py

$(DATA_DIR)/demo_db.sqlite3: $(DATA_DIR)/schema.sql $(DATA_DIR)/book_transactions.csv $(DATA_DIR)/notes.csv $(DATA_DIR)/books.csv $(DATA_DIR)/warehouses.csv
	sqlite3 $(DATA_DIR)/demo_db.sqlite3 < $(DATA_DIR)/schema.sql
	./load_db.py
