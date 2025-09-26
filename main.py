# main.py
import os
import re
import json
import platform as _platform
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from system_prompt import SYSTEM_PROMPT
from call_tools import dispatch_tool

load_dotenv()
MODEL = "gemini-2.5-flash"
WORKDIR = os.getcwd()

def load_behavior_md(path="behavior.md"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def build_prompt(system_prompt, behavior, history, user_message):
    hist = "\n".join(f"<{m['role']}>\n{m['content']}\n</{m['role']}>" for m in history[-12:])
    filled_system = (
        system_prompt
        .replace("{cwd}", WORKDIR)
        .replace("{date}", datetime.now().strftime("%Y-%m-%d"))
        .replace("{platform}", _platform.platform())
    )
    parts = [filled_system, "\n<behavior>\n" + behavior + "\n</behavior>\n"]
    if hist:
        parts.append("<recent_history>\n" + hist + "\n</recent_history>\n")
    parts.append("<user_request>\n" + user_message + "\n</user_request>")
    return "\n\n".join(parts)

def extract_text(response):
    for attr in ("text","content"):
        val = getattr(response, attr, None)
        if isinstance(val, str) and val.strip():
            return val
    candidates = getattr(response, "candidates", None)
    if candidates and isinstance(candidates, (list,tuple)):
        first = candidates[0]
        content = getattr(first, "content", None)
        if isinstance(content, str) and content.strip():
            return content
    return str(response)

def find_json_block(s):
    if not s:
        return None
    m = re.search(r"<tool_code>(.*?)</tool_code>", s, flags=re.S|re.I)
    if m: return m.group(1).strip()
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", s, flags=re.S|re.I)
    if m: return m.group(1).strip()
    m2 = re.search(r"(\{[\s\S]*\})", s)
    return m2.group(1).strip() if m2 else None

def parse_tool_call(text):
    j = find_json_block(text)
    if not j:
        return None
    try:
        obj = json.loads(j)
    except Exception:
        return None
    if isinstance(obj, dict) and "tool" in obj:
        obj["tool"] = str(obj["tool"]).lower()
        return obj
    return None

def _extract_filename_like(text: str) -> str:
    """Extracts a likely filename from free-form text.
    Heuristics: last occurrence of something like name.ext, allowing slashes.
    Trims trailing punctuation like ?!.,:)."""
    if not isinstance(text, str):
        return ""
    # Find all tokens that look like a path/filename with an extension
    matches = re.findall(r"[\w./-]+\.[A-Za-z0-9]+", text)
    if not matches:
        return ""
    candidate = matches[-1]
    # Strip trailing punctuation
    candidate = candidate.rstrip("?!.,:)")
    # Strip surrounding backticks if present
    candidate = candidate.strip("`")
    return candidate

def _infer_tool_from_text(user_text):
    """
    Fallback: infer a tool payload directly from the raw user text when LLM doesn't specify one.
    Supports:
      - list/ls/show files in/under <path>
      - read/open/show me/what's in <file>
      - combination of both in one sentence (returns todowrite with two steps)
    """
    if not isinstance(user_text, str) or not user_text.strip():
        return None
    text = user_text.strip()
    # If the user provided a URL, infer webfetch. If they also asked to summarize,
    # skip local inference so the LLM can summarize per the system policy.
    url_match = re.search(r"https?://\S+", text, flags=re.I)
    if url_match:
        if re.search(r"\bsummariz(e|ation|e\sit)\b", text, flags=re.I):
            return None
        return {"tool": "webfetch", "args": [url_match.group(0)], "kwargs": {}}

    # Detect chained fetch -> summarize -> write -> read pattern
    m_chain = re.search(
        r"fetch\s+(https?://\S+)\s+and\s+summariz(?:e|ation)?\s+to\s+(\d+)\s+(sentences|words|bullets?)\s+(?:then\s+)?write\s+to\s+`?([^`\s]+)`?\s+(?:and\s+)?(?:show|read)\b",
        text, flags=re.I)
    if m_chain:
        return {
            "plan": "fetch_summarize_write_read",
            "url": m_chain.group(1).strip(),
            "length": int(m_chain.group(2)),
            "length_type": m_chain.group(3).lower(),
            "target_path": m_chain.group(4).strip(),
        }

    # Detect simple multi-step: list files then write hello world code to a file
    m_list_write = re.search(r"\blist\s+(?:the\s+)?files\b.*\bthen\s+write\s+(?:a\s+)?file\s+called\s+`?([^`\s]+)`?.*hello\s+world", text, flags=re.I)
    if m_list_write:
        target = m_list_write.group(1).strip()
        content = "print('hello world')\n"
        steps = [
            {"tool": "ls", "args": ["."], "kwargs": {"names_only": True}},
            {"tool": "write", "args": [target, content], "kwargs": {}}
        ]
        return {"tool": "todowrite", "steps": steps}

    # Split on common conjunctions to reduce bleed across clauses
    clauses = re.split(r"\b(?:and then|and|;|\&)\b", text, flags=re.I)

    # detect list request (search first clause that mentions list)
    list_payload = None
    for c in clauses:
        if re.search(r"\b(list|ls|show files)\b", c, flags=re.I):
            # If the clause requests pattern-specific listing, defer to Glob logic
            if re.search(r"python files|files\s+matching|match\s+`?[^`\s]+`?", c, flags=re.I):
                continue
            # handle phrases like "in the directory", "in this directory" → default '.'
            if re.search(r"\bin\s+(the|this|current)\s+directory\b", c, flags=re.I):
                list_payload = {"tool": "ls", "args": ["."], "kwargs": {"names_only": True, "recursive": True, "files_only": True}}
                break
            m_in = re.search(r"(?:in|under)\s+`?([^`\s;,&]+)`?", c, flags=re.I)
            path = (m_in.group(1).strip() if m_in else None)
            # ignore ambiguous tokens
            if path and path.lower() in {"the","this","current","directory","repo","project"}:
                path = None
            # If the user says "all files" or similar, prefer recursive files-only listing
            wants_all = bool(re.search(r"\ball\s+files\b|\bfiles\b.*\b(any|all|every)\b|\bsubdir|subdirectories|recursively\b", c, flags=re.I))
            list_payload = {"tool": "ls", "args": [path or "."], "kwargs": {"names_only": True, "recursive": wants_all, "files_only": wants_all}}
            break

    # detect read request
    read_payload = None
    # Case A: "what's/whats in <file>" or "what is inside <file>" (tolerate minor typos like insie)
    m_what = re.search(r"what(?:'s|s|\s+is)?\s+(?:in|ins?ide)\s+`?([^`\s]+)`?", text, flags=re.I)
    if m_what:
        fname = m_what.group(1).strip()
        read_payload = {"tool": "read", "args": [fname], "kwargs": {}}
    else:
        # Case B: after verbs like read/open/show me/give me
        m_read = re.search(r"\b(read|open|show me|give me)\b", text, flags=re.I)
        if m_read:
            # Prefer any filename-like token anywhere after the verb
            fname = _extract_filename_like(text)
            if fname:
                read_payload = {"tool": "read", "args": [fname], "kwargs": {}}

    # detect find file requests → glob recursive
    find_payload = None
    m_find = re.search(r"\bfind\s+(?:file\s+)?`?([^`\s]+)`?", text, flags=re.I)
    if m_find:
        patt = m_find.group(1).strip()
        # If user included wildcards, use as-is; otherwise search anywhere for exact basename
        pattern = patt if any(ch in patt for ch in "*?[]") else f"**/{patt}"
        find_payload = {"tool": "glob", "args": [pattern], "kwargs": {"path": ".", "limit": 50}}

    # detect grep-style content search: "search for 'foo' in tools" or "search 'foo'"
    grep_payload = None
    m_search = re.search(r"\bsearch\s+(?:for\s+)?['\"]([^'\"]+)['\"](?:\s+in\s+`?([^`\n]+)`?)?", text, flags=re.I)
    if m_search:
        needle = m_search.group(1).strip()
        gpath = m_search.group(2).strip() if m_search.group(2) else "."
        grep_payload = {"tool": "grep", "args": [needle], "kwargs": {"path": gpath, "output_mode": "files_with_matches", "head_limit": 50}}

    # detect glob listing: "list python files" or "list files matching ..."
    glob_payload = None
    if re.search(r"\blist\b.*\bpython files\b", text, flags=re.I):
        glob_payload = {"tool": "glob", "args": ["**/*.py"], "kwargs": {"path": ".", "limit": 200}}
    else:
        m_match = re.search(r"\blist\b.*\bfiles\b.*\bmatching\b\s+`?([^`\s]+)`?", text, flags=re.I)
        if m_match:
            patt = m_match.group(1).strip()
            glob_payload = {"tool": "glob", "args": [patt], "kwargs": {"path": ".", "limit": 200}}

    # detect tail request: "show last N lines of <file>"
    tail_payload = None
    m_tail = re.search(r"\bshow\s+last\s+(\d+)\s+lines\s+of\s+`?([^`\s]+)`?", text, flags=re.I)
    if m_tail:
        num = int(m_tail.group(1))
        fname = m_tail.group(2).strip()
        tail_payload = {"tool": "read", "args": [fname], "kwargs": {"tail": num}}

    # detect write hello world code request → create db/hello.py
    write_hw_payload = None
    if re.search(r"\bwrite\b.*\bhello\s+world\b.*\bcode\b", text, flags=re.I):
        content = "print('hello world')\n"
        write_hw_payload = {"tool": "write", "args": ["db/hello.py", content], "kwargs": {}}

    # detect edit the file which has hello world code → edit db/hello.py
    edit_hw_payload = None
    if re.search(r"\bedit\b.*\bfile\b.*\bhello\s+world\b.*\bcode\b", text, flags=re.I):
        edit_hw_payload = {"tool": "edit", "args": ["db/hello.py", "hello world", "Hello, World!"], "kwargs": {"replace_all": False}}

    if list_payload and read_payload:
        # If list path missing but read has a directory component, default list to that dir
        list_arg = list_payload["args"][0]
        read_arg = read_payload["args"][0]
        if (not list_arg or list_arg == ".") and "/" in read_arg:
            list_payload = {**list_payload, "args": [os.path.dirname(read_arg) or "."]}
        # When combining, prefer recursive files-only to satisfy "files across workspace" intent
        list_payload["kwargs"].update({"recursive": True, "files_only": True})
        return {"tool": "todowrite", "steps": [list_payload, read_payload]}
    if list_payload:
        return list_payload
    if read_payload:
        return read_payload
    if grep_payload:
        return grep_payload
    if glob_payload:
        return glob_payload
    if find_payload:
        return find_payload
    if tail_payload:
        return tail_payload
    if write_hw_payload:
        return write_hw_payload
    if edit_hw_payload:
        return edit_hw_payload
    return None

def pretty_print(tool_name, text):
    # Structured, concise output similar to Claude Code
    if not tool_name or str(tool_name).lower() == "none":
        print(text + "\n"); return
    shown = text if isinstance(text, str) else str(text)
    max_chars = 1200
    is_truncated = len(shown) > max_chars
    if is_truncated:
        shown = shown[:max_chars].rstrip() + "\n... (truncated)"
    print(f"\nAgent : using tool : {tool_name}")
    print("──── Output ────")
    print(shown)
    print("───────────────\n")

def _normalize_todo_item(item):
    """
    Accepts string or dict and returns normalized dict: {'id', 'content', 'status'}.
    """
    if isinstance(item, dict):
        return {
            "id": item.get("id"),
            "content": str(item.get("content", "")).strip(),
            "status": item.get("status", "pending")
        }
    if isinstance(item, str):
        return {"id": None, "content": item.strip(), "status": "pending"}
    return {"id": None, "content": str(item), "status": "pending"}

def run_todos_flow(todos):
    """
    Accepts todos as list (of dicts or strings). Stores via todowrite, then executes sequentially.
    Returns list of tuples (normalized_todo_dict, tool_result_dict).
    """
    # Normalize incoming shape (may be list of strings, dicts, or already-normalized)
    normalized = [_normalize_todo_item(t) for t in (todos or [])]

    # Ask TodoWrite to persist / canonicalize (todowrite expects list of dicts with 'content')
    td_payload = {"tool":"todowrite","args":[normalized],"kwargs":{}}
    td_res = dispatch_tool(td_payload)
    if td_res.get("success"):
        # Use canonical todos from meta if available
        canonical = td_res.get("meta", {}).get("todos")
        if isinstance(canonical, list) and canonical:
            normalized = [_normalize_todo_item(t) for t in canonical]

    results = []
    for t in normalized:
        # mark in-progress then update via TodoWrite
        t["status"] = "in_progress"
        dispatch_tool({"tool":"todowrite","args":[normalized],"kwargs":{}})

        content = t.get("content","").strip()
        tool_payload = None

        # If content is raw JSON tool call - try to parse
        if content.startswith("{"):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "tool" in parsed:
                    parsed["tool"] = str(parsed["tool"]).lower()
                    tool_payload = parsed
            except Exception:
                tool_payload = None

        # Simple natural-language -> tool inference (fallback)
        if tool_payload is None:
            if re.search(r"\b(read|open|show me|what(?:'s| is) in)\b", content, flags=re.I):
                fname = _extract_filename_like(content)
                if fname:
                    tool_payload = {"tool":"read","args":[fname],"kwargs":{}}
            elif re.search(r"\b(list|ls|show files)\b", content, flags=re.I):
                m = re.search(r"(?:in|under)\s+`?([^`\n]+)`?", content, flags=re.I)
                path = m.group(1).strip() if m else "."
                tool_payload = {"tool":"ls","args":[path],"kwargs":{"names_only": True}}
            else:
                # If the content is short and looks like a filename, assume read
                if len(content.split()) == 1 and "." in content:
                    tool_payload = {"tool":"read","args":[content],"kwargs":{}}

        if not tool_payload:
            res = {"success": False, "output": "Could not convert todo to tool call", "meta": {}}
        else:
            # dispatch
            res = dispatch_tool(tool_payload)

        # mark completed/failed and persist
        t["status"] = "completed" if res.get("success") else "failed"
        dispatch_tool({"tool":"todowrite","args":[normalized],"kwargs":{}})
        results.append((t, res))

    return results

def repl():
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY",""))
    behavior = load_behavior_md()
    history = []
    print("Claude-Code-clone REPL — type 'exit' to quit, 'help' for commands.\n")
    while True:
        try:
            user = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting."); break
        if not user: continue
        if user.lower() in ("exit","quit"):
            print("Goodbye."); break
        if user.lower() == "help":
            print("Commands: exit, help, history"); continue
        if user.lower() == "history":
            for i,m in enumerate(history): print(f"{i+1}. {m['role']}: {m['content'][:200].replace(chr(10),' ')}"); continue

        history.append({"role":"user","content":user})

        # Prefer local inference for common repo ops, bypassing LLM when possible
        inferred = _infer_tool_from_text(user)
        if inferred:
            # Execute combined steps if provided
            if inferred.get("tool") == "todowrite" and isinstance(inferred.get("steps"), list):
                for step in inferred["steps"]:
                    res = dispatch_tool(step)
                    out = res.get("output","")
                    # Add meta header for webfetch
                    if step.get("tool") == "webfetch":
                        meta = res.get("meta", {}) if isinstance(res, dict) else {}
                        title = meta.get("title")
                        url = meta.get("url")
                        header = ((f"Title: {title}\n" if title else "") + (f"URL: {url}\n\n" if url else ""))
                        out = header + out
                    history.append({"role":"tool","content":f"{step.get('tool')}: {out}"})
                    pretty_print(step.get("tool"), out)
                continue
            # Execute special chain: fetch -> summarize -> write -> read
            if inferred.get("plan") == "fetch_summarize_write_read":
                # Step 1: fetch
                fetch_res = dispatch_tool({"tool": "webfetch", "args": [inferred.get("url")], "kwargs": {}})
                fetch_out = fetch_res.get("output", "")
                # Meta header
                fmeta = fetch_res.get("meta", {}) if isinstance(fetch_res, dict) else {}
                fheader = ((f"Title: {fmeta.get('title')}\n" if fmeta.get('title') else "") + (f"URL: {fmeta.get('url')}\n\n" if fmeta.get('url') else ""))
                fetch_display = fheader + fetch_out
                history.append({"role":"tool","content":f"webfetch: {fetch_out[:500]}"})
                pretty_print("webfetch", fetch_display)
                # Step 2: summarize via LLM using system policy
                try:
                    length = inferred.get("length") or 3
                    ltype = inferred.get("length_type") or "sentences"
                    summary_prompt = (
                        f"Summarize the following text to {length} {ltype}.\n"
                        f"Return plain text (no HTML).\n\n" + fetch_out
                    )
                    resp2 = client.models.generate_content(model=MODEL, contents=summary_prompt)
                    summary_text = extract_text(resp2)
                except Exception as e:
                    summary_text = f"Summarization failed: {e}"
                history.append({"role":"assistant","content":summary_text})
                pretty_print(None, summary_text)
                # Step 3: write
                target = inferred.get("target_path") or "db/summary.txt"
                write_res = dispatch_tool({"tool": "write", "args": [target, summary_text], "kwargs": {}})
                write_out = write_res.get("output", "")
                history.append({"role":"tool","content":f"write: {write_out}"})
                pretty_print("write", write_out)
                # Step 4: read
                read_res = dispatch_tool({"tool": "read", "args": [target], "kwargs": {}})
                read_out = read_res.get("output", "")
                history.append({"role":"tool","content":f"read: {read_out[:500]}"})
                pretty_print("read", read_out)
                continue
            # Single tool path
            res = dispatch_tool(inferred)
            out = res.get("output","")
            if inferred.get("tool") == "webfetch":
                meta = res.get("meta", {}) if isinstance(res, dict) else {}
                title = meta.get("title")
                url = meta.get("url")
                header = ((f"Title: {title}\n" if title else "") + (f"URL: {url}\n\n" if url else ""))
                out = header + out
            history.append({"role":"tool","content":f"{inferred.get('tool')}: {out}"})
            pretty_print(inferred.get("tool"), out)
            continue

        prompt = build_prompt(SYSTEM_PROMPT, behavior, history, user)
        try:
            resp = client.models.generate_content(model=MODEL, contents=prompt)
        except Exception as e:
            print("Error calling LLM:", e); continue

        text = extract_text(resp)
        tool_call = parse_tool_call(text)

        if not tool_call:
            # Fallback: infer from the user's raw text
            inferred = _infer_tool_from_text(user)
            if not inferred:
                history.append({"role":"assistant","content":text})
                pretty_print(None, text)
                continue
            tool_call = inferred

        # Handle todowrite specially (multi-step)
        if tool_call.get("tool") == "todowrite":
            td_res = dispatch_tool(tool_call)
            # accept meta.todos or args[0] as source
            todos = None
            if isinstance(td_res.get("meta",{}).get("todos"), list):
                todos = td_res["meta"]["todos"]
            else:
                # fall back to payload args (which may be a list or string)
                args0 = tool_call.get("args",[None])[0]
                todos = args0 if args0 is not None else []
            # Special-case: detect fetch+summarize+write+read in plain-English todos and run locally
            try:
                texts = [t.get("content","") if isinstance(t, dict) else str(t) for t in (todos or [])]
                joined = " \n".join(texts)
                url_m = re.search(r"https?://\S+", joined, flags=re.I)
                summarize_m = re.search(r"\bsummariz(e|ation)\b.+?(\d+)\s+(sentences|words|bullets?)", joined, flags=re.I)
                write_m = re.search(r"write\s+(?:it|the\s+summary)\s+to\s+`?([^`\s]+)`?", joined, flags=re.I)
                if url_m and summarize_m and write_m:
                    # Step 1: fetch
                    f_res = dispatch_tool({"tool":"webfetch","args":[url_m.group(0)],"kwargs":{}})
                    f_out = f_res.get("output","")
                    f_meta = f_res.get("meta",{})
                    f_header = ((f"Title: {f_meta.get('title')}\n" if f_meta.get('title') else "") + (f"URL: {f_meta.get('url')}\n\n" if f_meta.get('url') else ""))
                    pretty_print("webfetch", f_header + f_out)
                    # Step 2: summarize via LLM
                    n = int(summarize_m.group(2))
                    unit = summarize_m.group(3).lower()
                    prompt2 = f"Summarize the following text to {n} {unit}.\nReturn plain text (no HTML).\n\n" + f_out
                    try:
                        resp3 = client.models.generate_content(model=MODEL, contents=prompt2)
                        summary = extract_text(resp3)
                    except Exception as e:
                        summary = f"Summarization failed: {e}"
                    pretty_print(None, summary)
                    # Step 3: write
                    target = write_m.group(1)
                    w_res = dispatch_tool({"tool":"write","args":[target, summary],"kwargs":{}})
                    pretty_print("write", w_res.get("output",""))
                    # Step 4: read
                    r_res = dispatch_tool({"tool":"read","args":[target],"kwargs":{}})
                    pretty_print("read", r_res.get("output",""))
                    continue
            except Exception:
                pass
            # ensure list shape
            if not isinstance(todos, list):
                # try fallback inference
                inferred = _infer_tool_from_text(user)
                if inferred:
                    tool_call = inferred
                    # fall through to single tool handling below
                else:
                    pretty_print("todowrite", "failed to create todos (invalid shape)")
                    continue
            else:
                # Validate non-empty contents; if invalid, try fallback inference
                empty_or_invalid = any(not isinstance(t, dict) or not str(t.get("content","" )).strip() for t in todos)
                if empty_or_invalid:
                    inferred = _infer_tool_from_text(user)
                    if inferred:
                        tool_call = inferred
                    else:
                        pretty_print("todowrite", "failed to create todos (empty items)")
                        continue
                else:
                    results = run_todos_flow(todos)
                    for todo_dict, res in results:
                        content = todo_dict.get("content") if isinstance(todo_dict, dict) else str(todo_dict)
                        status = "OK" if res.get("success") else "ERROR"
                        print(f"Agent : todo '{content}' -> {status}")
                        if isinstance(res.get("output"), str) and res.get("output").strip():
                            print(res.get("output"))
                    continue
            results = run_todos_flow(todos)
            for todo_dict, res in results:
                content = todo_dict.get("content") if isinstance(todo_dict, dict) else str(todo_dict)
                status = "OK" if res.get("success") else "ERROR"
                print(f"Agent : todo '{content}' -> {status}")
                if isinstance(res.get("output"), str) and res.get("output").strip():
                    print(res.get("output"))
            continue

        # normal single tool (also reached via fallback from malformed todowrite)
        res = dispatch_tool(tool_call)
        out = res.get("output","")
        history.append({"role":"tool","content":f"{tool_call.get('tool')}: {out}"})
        pretty_print(tool_call.get("tool"), out)

if __name__ == "__main__":
    repl()
