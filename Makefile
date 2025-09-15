DATA_DIR := data

.PHONY: all
all: submodules deps $(DATA_DIR)/books.csv $(DATA_DIR)/warehouses.csv $(DATA_DIR)/notes.csv $(DATA_DIR)/book_transactions.csv  $(DATA_DIR)/demo_db.sqlite3

.PHONY: clean
clean:
	rm -f $(DATA_DIR)/*

.PHONY: spotless
spotless: clean
	rm -rf $(dir.crsql)/core/dist

.PHONY: submodules
submodules: 
	git submodule update --init --recursive

.PHONY: deps
deps:
	pip install -r requirements.txt

$(DATA_DIR): 
	mkdir -p $@

$(DATA_DIR)/books.csv: | $(DATA_DIR)
	@if [ -z "$(BOOKS_CSV_URL)" ]; then \
		echo "Error: BOOKS_CSV_URL is not set"; \
		exit 1; \
	fi; \
  curl -L "$(BOOKS_CSV_URL)" -o $@

$(DATA_DIR)/warehouses.csv: | $(DATA_DIR)
	python generate_warehouse_data.py

$(DATA_DIR)/notes_prelim.csv: | $(DATA_DIR)
	python generate_note_data.py

$(DATA_DIR)/book_transactions.csv $(DATA_DIR)/notes.csv: $(DATA_DIR)/books.csv $(DATA_DIR)/warehouses.csv $(DATA_DIR)/notes_prelim.csv
	python generate_book_transactions.py

$(DATA_DIR)/demo_db.sqlite3: $(DATA_DIR)/book_transactions.csv $(DATA_DIR)/notes.csv $(DATA_DIR)/books.csv $(DATA_DIR)/warehouses.csv 
	sqlite3 $(DATA_DIR)/demo_db.sqlite3<schema.sql
	python load_db.py

