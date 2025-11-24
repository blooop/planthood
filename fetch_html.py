import requests


def fetch_html():
    url = "https://planthood.co.uk/collections/cooking-instructions"
    response = requests.get(url)
    with open("page.html", "w") as f:
        f.write(response.text)
    print("Saved page.html")


if __name__ == "__main__":
    fetch_html()
