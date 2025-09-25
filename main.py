import os
import sys
from dotenv import load_dotenv
from google import genai
from system_prompt import SYSTEM_PROMPT

def load_behavior_md(path="behavior.md"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def build_prompt(system_prompt, behavior, user_prompt):
    parts = [
        system_prompt,
        "\n<behavior>\n" + behavior + "\n</behavior>\n",
        "<user_request>\n" + user_prompt + "\n</user_request>"
    ]
    return "\n\n".join([p for p in parts if p])

def main() -> None:
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY not set in environment")
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python main.py '<prompt text>'")
    prompt = sys.argv[1]
    behavior = load_behavior_md()
    full_prompt = build_prompt(SYSTEM_PROMPT, behavior, prompt)
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model="gemini-2.5-flash", contents=full_prompt)
    output = getattr(response, "text", None) or getattr(response, "content", None) or str(response)
    print(output)

if __name__ == "__main__":
    main()
