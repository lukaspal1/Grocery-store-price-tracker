# test_albert_api.py
import httpx
import json

url = "https://www.albert.cz/api/v1/"

params = {
    "operationName": "GetLeaflets",
    "variables": json.dumps({"onlyDefault": True}),
    "extensions": json.dumps({
        "persistedQuery": {
            "version": 1,
            "sha256Hash": "c38d69777119edc8aa05c8916efb299f129b4a8f74442c29de8c1b32423393d4a",
        }
    }),
}

headers = {
    "User-Agent": "PortfolioPriceTracker/1.0 (+https://github.com/lukaspal1)",
    "Referer": "https://www.albert.cz/",
    "Accept": "application/json",
    "apollo-require-preflight": "true",   # ← the fix
}

r = httpx.get(url, params=params, headers=headers, timeout=20)
print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('content-type')}")
print(r.text[:2000])