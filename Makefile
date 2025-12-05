DATA_DIR := data
SCHEMA_URL := https://raw.githubusercontent.com/librocco/librocco/refs/heads/main/apps/sync-server/schemas/init

.PHONY: all
all: submodules $(DATA_DIR)/books.csv $(DATA_DIR)/warehouses.csv $(DATA_DIR)/notes.csv $(DATA_DIR)/book_transactions.csv $(DATA_DIR)/demo_db.sqlite3

.PHONY: clean
clean:
	rm -f $(DATA_DIR)/*

.PHONY: spotless
spotless: clean

.PHONY: submodules
submodules:
	git submodule update --init --recursive

$(DATA_DIR):
	mkdir -p $@

$(DATA_DIR)/schema.sql: | $(DATA_DIR)
	curl -sL $(SCHEMA_URL) | grep -v 'crsql_as_crr\|crsql_finalize' > $@

$(DATA_DIR)/books.csv: | $(DATA_DIR)
	@if [ -z $(BOOKS_CSV_URL) ]; then \
		echo "Error: BOOKS_CSV_URL is not set"; \
		exit 1; \
	fi; \
	curl -L $(BOOKS_CSV_URL) -o $@

$(DATA_DIR)/warehouses.csv: | $(DATA_DIR)
	./generate_warehouse_data.py

$(DATA_DIR)/notes_prelim.csv: | $(DATA_DIR)
	./generate_note_data.py

$(DATA_DIR)/book_transactions.csv $(DATA_DIR)/notes.csv: $(DATA_DIR)/books.csv $(DATA_DIR)/warehouses.csv $(DATA_DIR)/notes_prelim.csv
	./generate_book_transactions.py

$(DATA_DIR)/demo_db.sqlite3: $(DATA_DIR)/schema.sql $(DATA_DIR)/book_transactions.csv $(DATA_DIR)/notes.csv $(DATA_DIR)/books.csv $(DATA_DIR)/warehouses.csv
	sqlite3 $(DATA_DIR)/demo_db.sqlite3 < $(DATA_DIR)/schema.sql
	./load_db.py
