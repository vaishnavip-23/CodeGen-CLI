# File Summary: Implementation of the WebFetch tool for retrieving web pages.

"""
Web Fetch Tool for CodeGen-CLI

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

# Function declaration for Gemini function calling  
FUNCTION_DECLARATION = {
    "name": "fetch_url",
    "description": "Fetch and extract text content from a web URL. Use for documentation, articles, or web resources.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch content from"
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters to return (default: 20000)"
            }
        },
        "required": ["url"]
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
                "url": types.Schema(type=types.Type.STRING, description="URL to fetch"),
                "max_chars": types.Schema(type=types.Type.INTEGER, description="Max characters (default: 20000)")
            },
            required=["url"]
        )
    )

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

def call(url: str, *args, **kwargs) -> Dict[str, Any]:
    """
    Fetch content from a web URL.
    
    Args:
        url: URL to fetch content from
        *args: Additional positional arguments (ignored)
        **kwargs: Keyword arguments including:
            prompt: Optional prompt (not used, kept for compatibility)
            max_chars: Maximum number of characters to return (default: 20000)
        
    Returns:
        Dictionary with success status and content
    """
    try:
        input_data = WebFetchInput(
            url=url.strip() if url else "",
            prompt=kwargs.get("prompt", "")
        )
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")
    
    fetch_url = input_data.url
    if not (fetch_url.startswith("http://") or fetch_url.startswith("https://")):
        fetch_url = "https://" + fetch_url
    
    max_chars = kwargs.get("max_chars", 20000)
    
    try:
        content = fetch_web_content(fetch_url, max_chars)
        
        output = WebFetchOutput(
            response=content["text"],
            url=fetch_url,
            final_url=None,
            status_code=None
        )
        return output.model_dump()
        
    except Exception as e:
        raise IOError(f"Web fetch error: {e}")
