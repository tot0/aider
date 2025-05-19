#!/usr/bin/env python

import os
import json
from typing import List, Tuple

import httpx

from aider.scrape import Scraper
from aider.dump import dump  # noqa: F401


class WebSearchAgent:
    """Search the web and summarize the results."""

    function_spec = {
        "name": "search_web",
        "description": "search the web and summarize the top results",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }

    def __init__(self, io=None, weak_model=None, verify_ssl=True, max_page_chars=None):
        self.io = io
        self.weak_model = weak_model
        self.scraper = Scraper(print_error=self._print_error, verify_ssl=verify_ssl)

        if max_page_chars is None:
            max_page_chars = 16000
            if weak_model and weak_model.info.get("max_input_tokens"):
                context_tokens = weak_model.info.get("max_input_tokens")
                max_page_chars = int(context_tokens * 0.8 * 4)
        self.max_page_chars = max_page_chars

    # ---------------------------------------------------------
    def _print_error(self, msg):
        if self.io:
            self.io.tool_error(str(msg))
        else:
            print(msg)

    # ---------------------------------------------------------
    def _search_serpapi(self, query: str, num: int) -> List[str]:
        key = os.environ.get("SERPAPI_API_KEY")
        if not key:
            self._print_error("SERPAPI_API_KEY not set")
            return []
        url = "https://serpapi.com/search.json"
        params = {"q": query, "api_key": key, "num": num}
        try:
            resp = httpx.get(url, params=params)
            data = resp.json()
            links = []
            for item in data.get("organic_results", [])[:num]:
                link = item.get("link")
                if link:
                    links.append(link)
            return links
        except Exception as err:
            self._print_error(f"SerpAPI error: {err}")
            return []

    # ---------------------------------------------------------
    def _search_bing(self, query: str, num: int) -> List[str]:
        key = os.environ.get("BING_API_KEY")
        if not key:
            self._print_error("BING_API_KEY not set")
            return []
        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": key}
        params = {"q": query, "count": num}
        try:
            resp = httpx.get(url, params=params, headers=headers)
            data = resp.json()
            links = []
            for item in data.get("webPages", {}).get("value", [])[:num]:
                link = item.get("url")
                if link:
                    links.append(link)
            return links
        except Exception as err:
            self._print_error(f"Bing search error: {err}")
            return []

    # ---------------------------------------------------------
    def search(self, query: str, num_results: int = 3) -> List[Tuple[str, str]]:
        links = self._search_serpapi(query, num_results)
        if not links:
            links = self._search_bing(query, num_results)
        if not links:
            self._print_error("No search engine API key configured.")
            return []

        results = []
        for link in links:
            page = self.scraper.scrape(link)
            if not page:
                self._print_error(f"Failed to scrape {link}")
                continue
            summary = self.summarize(page)
            if summary:
                results.append((link, summary))
        return results

    # ---------------------------------------------------------
    def summarize(self, text: str) -> str:
        if not self.weak_model:
            return text[:200]

        prompt = [
            dict(role="system", content="Summarize the following web page."),
            dict(role="user", content=text[: self.max_page_chars]),
        ]
        try:
            summary = self.weak_model.simple_send_with_retries(prompt)
        except Exception as err:
            self._print_error(f"Summary error: {err}")
            return ""
        return summary or ""


