import requests, html, re

def _strip_html(doc: str) -> str:
    doc = re.sub(r"<script[\s\S]*?</script>", " ", doc, flags=re.I|re.S)
    doc = re.sub(r"<style[\s\S]*?</style>", " ", doc, flags=re.I|re.S)
    doc = re.sub(r"<[^>]+>", " ", doc)
    doc = html.unescape(doc)
    doc = re.sub(r"\s+", " ", doc).strip()
    return doc

def _extract_between(raw: str, start_tag_regex: str, end_tag: str) -> str:
    m = re.search(start_tag_regex, raw, flags=re.I)
    if not m:
        return ""
    start = m.end()
    end = raw.find(end_tag, start)
    if end == -1:
        end = len(raw)
    return raw[start:end]

def _extract_main_text(raw: str) -> tuple[str, str]:
    # Prefer <main>, then <article>, then role="main"
    main_html = _extract_between(raw, r"<main\b[^>]*>", "</main>")
    if main_html:
        return _strip_html(main_html), "main"
    art_html = _extract_between(raw, r"<article\b[^>]*>", "</article>")
    if art_html:
        return _strip_html(art_html), "article"
    role_main = _extract_between(raw, r"<div\b[^>]*role=\"main\"[^>]*>", "</div>")
    if role_main:
        return _strip_html(role_main), "role=main"
    # Fallback: aggregate first N <p> tags
    paras = re.findall(r"<p\b[^>]*>([\s\S]*?)</p>", raw, flags=re.I)
    if paras:
        text = _strip_html("\n".join(paras[:20]))
        return text, "p-aggregate"
    return "", "none"

def call(url, prompt: str = ""):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; CodeGen2/1.0; +https://example.local)"
        }
        r = requests.get(url, timeout=12, headers=headers, allow_redirects=True)
        r.raise_for_status()
        # Respect apparent encoding if server didn't set one
        if not r.encoding and hasattr(r, "apparent_encoding") and r.apparent_encoding:
            r.encoding = r.apparent_encoding
        raw = r.text[:300000]
        # Try to extract helpful metadata for JS-heavy pages
        title_m = re.search(r"<title[^>]*>([\s\S]*?)</title>", raw, flags=re.I)
        title = html.unescape(title_m.group(1)).strip() if title_m else ""
        desc = ""
        for meta_name in ("description", "og:description", "twitter:description"):
            pattern = r'<meta[^>]+(?:name|property)="' + re.escape(meta_name) + r'"[^>]+content="([^"]+)"'
            m = re.search(pattern, raw, flags=re.I)
            if m:
                desc = html.unescape(m.group(1)).strip()
                break

        main_text, source = _extract_main_text(raw)
        if main_text:
            return {"success": True, "output": main_text[:20000], "meta": {"url": url, "source": source, "title": title}}

        plain = _strip_html(raw)
        # If body text is too short (likely JS-rendered), fall back to title + description
        if len(plain) < 500 and (title or desc):
            combined = (title + ": " + desc).strip(": ")
            return {"success": True, "output": combined[:2000], "meta": {"url": url, "source": "meta", "title": title}}

        snippet = plain[:20000]
        return {"success": True, "output": snippet, "meta": {"url": url, "source": "plain", "title": title}}
    except Exception as e:
        return {"success": False, "output": f"Fetch error: {e}", "meta": {}}
