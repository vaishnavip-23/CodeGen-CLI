"""
Web Fetch Tool for CodeGen2

This tool fetches content from web URLs and extracts text.
It includes content length limits and error handling.
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional

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
        # Prepare request headers
        headers = {
            "User-Agent": "CodeGen2-CLI-Agent/1.0"
        }
        
        # Make request
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        
        # Parse HTML content
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Extract title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        
        # Extract text content from paragraphs
        paragraphs = []
        for p in soup.find_all("p"):
            text = p.get_text(separator=" ", strip=True)
            if text:  # Only add non-empty paragraphs
                paragraphs.append(text)
        
        # Join paragraphs or fall back to all text
        if paragraphs:
            text = "\n\n".join(paragraphs)
        else:
            text = soup.get_text(separator=" ", strip=True)
        
        # Truncate if too long
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
    # Extract parameters from kwargs
    max_chars = kwargs.get("max_chars", 20000)
    # Validate inputs
    if not url or not url.strip():
        return {
            "tool": "webfetch",
            "success": False,
            "output": "URL cannot be empty."
        }
    
    if max_chars < 100 or max_chars > 100000:
        return {
            "tool": "webfetch",
            "success": False,
            "output": "Max characters must be between 100 and 100000."
        }
    
    # Validate URL format
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url
    
    try:
        # Fetch content
        content = fetch_web_content(url, max_chars)
        
        return {
            "tool": "webfetch",
            "success": True,
            "output": content,
            "meta": {
                "url": url,
                "content_length": len(content["text"]),
                "max_chars": max_chars
            }
        }
        
    except Exception as e:
        return {
            "tool": "webfetch",
            "success": False,
            "output": f"Web fetch error: {e}"
        }
