import requests, html
def call(url, prompt=""):
    try:
        r = requests.get(url, timeout=10)
        text = r.text
        text = html.unescape(text)
        snippet = text[:20000]
        return {"success": True, "output": snippet, "meta": {"url": url}}
    except Exception as e:
        return {"success": False, "output": f"Fetch error: {e}", "meta": {}}
