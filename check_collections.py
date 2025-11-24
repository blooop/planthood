import requests
import json


def check_collections():
    url = "https://planthood.co.uk/collections.json"
    response = requests.get(url)
    data = response.json()

    print(f"Found {len(data['collections'])} collections")
    for c in data["collections"]:
        print(f"ID: {c['id']}, Handle: {c['handle']}, Title: {c['title']}")


if __name__ == "__main__":
    check_collections()
