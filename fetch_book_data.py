#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pandas",
#   "requests",
# ]
# ///

from random import randint
import requests
import os
import pandas as pd
import time

# API key is optional - without it, requests are rate-limited but still work
API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY")

BOOKS_API_URL = "https://www.googleapis.com/books/v1/volumes"


def get_books_page(pageIx: int, query: str = "intitle:the", res_per_page: int = 40):
    offset = pageIx * res_per_page

    fields = ",".join([
        "items/volumeInfo/industryIdentifiers",
        "items/volumeInfo/title",
        "items/volumeInfo/authors",
        "items/volumeInfo/publisher",
        "items/volumeInfo/publishedDate",
        "items/volumeInfo/categories",
    ])

    params = {
        "q": query,
        "fields": fields,
        "maxResults": 40,
        "startIndex": offset,
    }
    if API_KEY:
        params["key"] = API_KEY

    response = requests.get(BOOKS_API_URL, params=params)
    response.raise_for_status()
    return response.json()


def get_isbn10(industry_identifiers: list[dict[str, str]]):
    if len(industry_identifiers) == 0:
        return None
    for identifier in industry_identifiers:
        if identifier["type"] == "ISBN_10":
            return identifier["identifier"]
    return None


def process_volume(volume: dict) -> dict[str, str | int | float | None] | None:
    isbn = get_isbn10(volume.get("industryIdentifiers", []))
    if isbn is None:
        return None

    title = volume.get("title")

    authors = ",".join(volume.get("authors", []))

    price = 0  # TODO

    published_date = volume.get("publishedDate")
    year = published_date.split("-")[0] if published_date else None

    publisher = volume.get("publisher")
    edited_by = None
    out_of_print = 1 if randint(0, 20) == 0 else 0

    categories = volume.get("categories", [])
    category = categories[0] if len(categories) > 0 else None

    updated_at = "2024-06-01T00:00:00Z"  # Completely arbitrary date

    return {
        "isbn": isbn,
        "title": title,
        "authors": authors,
        "price": price,
        "year": year,
        "publisher": publisher,
        "edited_by": edited_by,
        "out_of_print": out_of_print,
        "category": category,
        "updated_at": updated_at,
    }


def process_items(items: list):
    for item in items:
        volume = process_volume(item["volumeInfo"])
        if volume is not None:
            yield volume


def fetch_with_retry(page_ix: int, query: str = "intitle:the", max_retries: int = 3, base_delay: float = 1.0):
    """Fetch a page with exponential backoff on failure."""
    for attempt in range(max_retries):
        try:
            return get_books_page(page_ix, query=query)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in (429, 503) and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"    Rate limited, waiting {delay}s...")
                time.sleep(delay)
            else:
                raise


def main():
    start = time.time()

    # Google Books API has a pagination limit (~1000 results max per query)
    # Use multiple search queries to get more diverse results
    queries = [
        "intitle:the",
        "intitle:and",
        "intitle:of",
        "intitle:to",
        "intitle:a",
        "subject:fiction",
        "subject:science",
        "subject:history",
        "subject:biography",
        "subject:philosophy",
    ]
    pages_per_query = 10  # 10 pages * 40 results = 400 per query
    results = []

    os.makedirs("data", exist_ok=True)

    for query in queries:
        print(f"\nFetching: {query}")
        for i in range(pages_per_query):
            try:
                res = fetch_with_retry(i, query=query)
                results.append(res)
                print(f"  page {i + 1}/{pages_per_query}")
                time.sleep(0.1)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 400:
                    print(f"  Hit pagination limit at page {i}")
                    break
                raise

    df = pd.DataFrame((item for res in results for item in process_items(res.get("items", []))))
    # Remove duplicates by ISBN
    df = df.drop_duplicates(subset=["isbn"])

    df.to_csv("data/books.csv", index=False)

    print(f"\ntook: {time.time() - start:.2f} seconds")
    print(f"fetched {len(df)} unique books")


if __name__ == "__main__":
    main()
