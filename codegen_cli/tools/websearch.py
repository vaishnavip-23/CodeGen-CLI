# File Summary: Implementation of the WebSearch tool for external queries.

"""
Web Search Tool for CodeGen-CLI

This tool searches the web using DuckDuckGo and returns search results.
It includes error handling and result formatting.
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import WebSearchInput, WebSearchResult, WebSearchOutput

# Function declaration for Gemini function calling
FUNCTION_DECLARATION = {
    "name": "search_web",
    "description": "Search the web using DuckDuckGo for information, documentation, or examples.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (1-20, default: 5)"
            }
        },
        "required": ["query"]
    }
}

def get_function_declaration():
    """Get Gemini function declaration for this tool."""
    if types is None:
        return None
    
    return types.FunctionDeclaration(
        name=FUNCTION_DECLARATION["name"],
        description=FUNCTION_DECLARATION["description"],
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(type=types.Type.STRING, description="Search query"),
                "max_results": types.Schema(type=types.Type.INTEGER, description="Max results (1-20)")
            },
            required=["query"]
        )
    )

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
    try:
        input_data = WebSearchInput(
            query=query,
            allowed_domains=kwargs.get("allowed_domains"),
            blocked_domains=kwargs.get("blocked_domains")
        )
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")
    
    if not input_data.query.strip():
        raise ValueError("Search query cannot be empty")
    
    max_results = kwargs.get("max_results", 5)
    
    try:
        results = search_web(input_data.query.strip(), max_results)
        
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
        return output.model_dump()
        
    except Exception as e:
        raise IOError(f"Web search error: {e}")
