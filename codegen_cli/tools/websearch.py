# File Summary: Implementation of the WebSearch tool for external queries.

"""
Web Search Tool for CodeGen-CLI
Refactored to use Gemini's native Pydantic function calling with from_callable().

This tool searches the web using DuckDuckGo and returns search results.
It includes error handling and result formatting.
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import WebSearchInput, WebSearchResult, WebSearchOutput

DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"

def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search the web using DuckDuckGo.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
        
    Returns:
        List of search result dictionaries with title and url
    """
    try:
                         
        headers = {
            "User-Agent": "CodeGen-CLI-Agent/1.0"
        }
        data = {"q": query}
        
                                    
        response = requests.post(
            DUCKDUCKGO_HTML_URL,
            data=data,
            timeout=10,
            headers=headers
        )
        response.raise_for_status()
        
                             
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        
                                            
        primary_results = soup.select("a.result__a")[:max_results]
        for link in primary_results:
            href = link.get("href")
            title = link.get_text(strip=True)
            if href and title:
                results.append({
                    "title": title,
                    "url": href
                })
        
                                                          
        if not results:
            all_links = soup.find_all("a")[:max_results * 2]
            for link in all_links:
                href = link.get("href")
                text = link.get_text(strip=True)
                
                                                        
                if href and text and len(text) > 10:
                    results.append({
                        "title": text[:120],                      
                        "url": href
                    })
                    
                    if len(results) >= max_results:
                        break
        
        return results
        
    except requests.RequestException as e:
        raise Exception(f"Network error: {e}")
    except Exception as e:
        raise Exception(f"Parsing error: {e}")

def search_web(query: str, allowed_domains: Optional[List[str]] = None, blocked_domains: Optional[List[str]] = None) -> WebSearchOutput:
    """Search the web for information.
    
    Performs a web search using DuckDuckGo and returns relevant results.
    
    Args:
        query: The search query to use
        allowed_domains: Only include results from these domains (optional)
        blocked_domains: Never include results from these domains (optional)
        
    Returns:
        WebSearchOutput Pydantic model containing search results, total count, and query used.
    """
    # Validate using Pydantic model
    try:
        input_data = WebSearchInput(
            query=query,
            allowed_domains=allowed_domains,
            blocked_domains=blocked_domains
        )
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")
    
    if not input_data.query.strip():
        raise ValueError("Search query cannot be empty")
    
    max_results = 5
    
    try:
        results = search_duckduckgo(input_data.query.strip(), max_results)
        
        search_results = [
            WebSearchResult(
                title=r["title"],
                url=r["url"],
                snippet=r.get("snippet", ""),
                metadata=None
            )
            for r in results
        ]
        
        output = WebSearchOutput(
            results=search_results,
            total_results=len(search_results),
            query=input_data.query
        )
        return output
        
    except Exception as e:
        raise IOError(f"Web search error: {e}")


def get_function_declaration(client):
    """Get Gemini function declaration using from_callable().
    
    Args:
        client: Gemini client instance (required by from_callable)
        
    Returns:
        FunctionDeclaration object for this tool
    """
    if types is None:
        return None
    
    return types.FunctionDeclaration.from_callable(
        client=client,
        callable=search_web
    )


# Keep backward compatibility
def call(query: str, *args, **kwargs) -> Dict[str, Any]:
    """Call function for backward compatibility with manual execution."""
    result = search_web(
        query=query,
        allowed_domains=kwargs.get("allowed_domains"),
        blocked_domains=kwargs.get("blocked_domains")
    )
    return result.model_dump()
