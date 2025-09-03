from random import randint
from googleapiclient.discovery import build
from dotenv import load_dotenv
import os
import asyncio
import pandas as pd
import time


load_dotenv()
API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY")
if API_KEY is None:
    raise ValueError("GOOGLE_BOOKS_API_KEY environment variable not set")

svc = build("books", "v1", developerKey=API_KEY)


def get_books_page(pageIx: int, res_per_page: int = 40):
    offset = pageIx * res_per_page

    fields = ",".join([
        "volumeInfo/industryIdentifiers",
        "volumeInfo/title",
        "volumeInfo/authors",
        "volumeInfo/publisher",
        "volumeInfo/publishedDate",
        "volumeInfo/categories",
    ])

    return (
        svc.volumes()
        # Using 'the' hack:
        # - Google books API doesn't allow for empty queries (there has to be a non-empty search string)
        # - using the most common word in English (especially in book titles): 'the' achieves the similar effect
        .list(
            q="intitle:the", fields=f"items({fields})", maxResults=40, startIndex=offset
        )
        .execute()
    )


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


async def main():
    start = time.time()

    # books_to_fetch = 20_000
    # num_pages = books_to_fetch // 40

    # if books_to_fetch % 40 != 0:
    #     num_pages += 1

    num_pages = 100

    lock = asyncio.Lock()
    counter = 0

    def fetch_page(page_ix: int, total_pages: int):
        nonlocal counter

        res = get_books_page(page_ix)

        counter += 1
        print(f"progress: {counter}/{total_pages}")

        return res

    tasks = [asyncio.create_task(fetch_page(i, num_pages)) for i in range(num_pages)]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

    for task in done:
        if task.exception():
            for p in pending:
                p.cancel()
            raise task.exception()

    results = (t.result() for t in done)

    # results = await asyncio.gather(
    #     *(fetch_page(i, num_pages) for i in range(num_pages))
    # )

    df = pd.DataFrame((item for res in results for item in process_items(res["items"])))

    os.makedirs("data", exist_ok=True)
    df.to_csv("data/books.csv", index=False)

    print(f"took: {time.time() - start:.2f} seconds")


asyncio.run(main())
