# File Summary: Implementation of the WebFetch tool for retrieving web pages.

"""
Web Fetch Tool for CodeGen-CLI
Refactored to use Gemini's native Pydantic function calling with from_callable().

This tool fetches content from web URLs and extracts text.
It includes content length limits and error handling.
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, Any

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import WebFetchInput, WebFetchOutput

def fetch_web_content(url: str, max_chars: int = 20000) -> Dict[str, str]:
    """
    Fetch and extract content from a web URL.
    
    Args:
        url: URL to fetch content from
        max_chars: Maximum number of characters to return
        
    Returns:
        Dictionary with title, text, and url
    """
    try:
                                 
        headers = {
            "User-Agent": "CodeGen-CLI-Agent/1.0"
        }
        
                      
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        
                            
        soup = BeautifulSoup(response.text, "html.parser")
        
                       
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        
                                              
        paragraphs = []
        for p in soup.find_all("p"):
            text = p.get_text(separator=" ", strip=True)
            if text:                                 
                paragraphs.append(text)
        
                                                  
        if paragraphs:
            text = "\n\n".join(paragraphs)
        else:
            text = soup.get_text(separator=" ", strip=True)
        
                              
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[Content truncated]"
        
        return {
            "title": title,
            "text": text,
            "url": url
        }
        
    except requests.RequestException as e:
        raise Exception(f"Network error: {e}")
    except Exception as e:
        raise Exception(f"Content extraction error: {e}")


def fetch_url(url: str, prompt: str = "") -> WebFetchOutput:
    """Fetch content from a URL and run a prompt on it.
    
    Fetches web content and uses AI to process it based on the provided prompt.
    For now, prompt is not used but kept for API compatibility.
    
    Args:
        url: The URL to fetch content from
        prompt: The prompt to run on the fetched content (currently not used)
        
    Returns:
        WebFetchOutput Pydantic model containing response text, URL, final URL, and status code.
    """
    # Validate using Pydantic model
    try:
        input_data = WebFetchInput(
            url=url.strip() if url else "",
            prompt=prompt
        )
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")
    
    fetch_url_str = input_data.url
    if not (fetch_url_str.startswith("http://") or fetch_url_str.startswith("https://")):
        fetch_url_str = "https://" + fetch_url_str
    
    max_chars = 20000
    
    try:
        content = fetch_web_content(fetch_url_str, max_chars)
        
        output = WebFetchOutput(
            response=content["text"],
            url=fetch_url_str,
            final_url=None,
            status_code=None
        )
        return output
        
    except Exception as e:
        raise IOError(f"Web fetch error: {e}")


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
        callable=fetch_url
    )


# Keep backward compatibility
def call(url: str, *args, **kwargs) -> Dict[str, Any]:
    """Call function for backward compatibility with manual execution."""
    result = fetch_url(
        url=url,
        prompt=kwargs.get("prompt", "")
    )
    return result.model_dump()
