import requests

def _extract_snippet(data: dict) -> str:
    # Prefer explicit abstract text
    abstract = data.get("AbstractText")
    if isinstance(abstract, str) and abstract.strip():
        return abstract.strip()

    # Fallback: scan RelatedTopics for first available Text
    related = data.get("RelatedTopics")
    if isinstance(related, list):
        for item in related:
            if isinstance(item, dict):
                text = item.get("Text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
                # Some entries nest under "Topics"
                topics = item.get("Topics")
                if isinstance(topics, list):
                    for t in topics:
                        if isinstance(t, dict):
                            t_text = t.get("Text")
                            if isinstance(t_text, str) and t_text.strip():
                                return t_text.strip()
    return ""

def call(query, allowed_domains=None, blocked_domains=None):
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()
        snippet = _extract_snippet(data)
        return {"success": True, "output": snippet or "No summary", "meta": {"raw": data}}
    except Exception as e:
        return {"success": False, "output": f"Search error: {e}", "meta": {}}
