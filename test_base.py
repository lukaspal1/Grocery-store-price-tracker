# test_base.py
from scrapers.base import CompliantScraper

def main():
    scraper = CompliantScraper("https://www.lidl.cz")

    # First, see what the site disallows
    print("--- robots.txt contents ---")
    print(scraper.robots)
    print()

    # Test a URL you know is allowed (homepage)
    print("--- Testing allowed URL ---")
    print(f"can_fetch(homepage): {scraper.can_fetch('https://www.lidl.cz/')}")
    print()

    # Try a few paths to find one that IS disallowed
    # Adjust these based on what you see in the robots.txt output
    test_paths = [
        "https://www.lidl.cz/search",
        "https://www.lidl.cz/api",
        "https://www.lidl.cz/c/",
    ]
    print("--- Testing various paths ---")
    for url in test_paths:
        print(f"{url} -> {scraper.can_fetch(url)}")

if __name__ == "__main__":
    main()