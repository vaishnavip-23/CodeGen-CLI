"""
Web Search Tool for CodeGen2

This tool searches the web using DuckDuckGo and returns search results.
It includes error handling and result formatting.
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any

# DuckDuckGo HTML search endpoint
DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"

def search_web(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search the web using DuckDuckGo.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
        
    Returns:
        List of search result dictionaries with title and url
    """
    try:
        # Prepare request
        headers = {
            "User-Agent": "CodeGen2-CLI-Agent/1.0"
        }
        data = {"q": query}
        
        # Make request to DuckDuckGo
        response = requests.post(
            DUCKDUCKGO_HTML_URL,
            data=data,
            timeout=10,
            headers=headers
        )
        response.raise_for_status()
        
        # Parse HTML response
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        
        # Try to find primary search results
        primary_results = soup.select("a.result__a")[:max_results]
        for link in primary_results:
            href = link.get("href")
            title = link.get_text(strip=True)
            if href and title:
                results.append({
                    "title": title,
                    "url": href
                })
        
        # If no primary results found, try fallback method
        if not results:
            all_links = soup.find_all("a")[:max_results * 2]
            for link in all_links:
                href = link.get("href")
                text = link.get_text(strip=True)
                
                # Filter out empty or very short results
                if href and text and len(text) > 10:
                    results.append({
                        "title": text[:120],  # Limit title length
                        "url": href
                    })
                    
                    if len(results) >= max_results:
                        break
        
        return results
        
    except requests.RequestException as e:
        raise Exception(f"Network error: {e}")
    except Exception as e:
        raise Exception(f"Parsing error: {e}")

def call(query: str, *args, **kwargs) -> Dict[str, Any]:
    """
    Search the web for the given query.
    
    Args:
        query: Search query string
        *args: Additional positional arguments (ignored)
        **kwargs: Keyword arguments including:
            max_results: Maximum number of results to return (default: 5)
        
    Returns:
        Dictionary with success status and search results
    """
    # Extract max_results from kwargs
    max_results = kwargs.get("max_results", 5)
    # Validate inputs
    if not query or not query.strip():
        return {
            "tool": "websearch",
            "success": False,
            "output": "Search query cannot be empty."
        }
    
    if max_results < 1 or max_results > 20:
        return {
            "tool": "websearch",
            "success": False,
            "output": "Max results must be between 1 and 20."
        }
    
    try:
        # Perform search
        results = search_web(query.strip(), max_results)
        
        if not results:
            return {
                "tool": "websearch",
                "success": True,
                "output": f"No results found for '{query}'"
            }
        
        return {
            "tool": "websearch",
            "success": True,
            "output": results,
            "meta": {
                "query": query,
                "results_count": len(results),
                "max_results": max_results
            }
        }
        
    except Exception as e:
        return {
            "tool": "websearch",
            "success": False,
            "output": f"Web search error: {e}"
        }
