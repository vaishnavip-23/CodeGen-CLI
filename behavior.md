# behavior.md — Agent behavior, heuristics and examples

This document explains the agent's preferred workflow, why each decision is made, and provides examples. Keep this file concise, useful, and human-readable. The system prompt enforces hard rules; this file is guidance and examples.

## Core principle: discovery first

Always find and inspect before changing. That means:

1. Use `Glob` and `LS` to discover candidate files.
2. Use `Grep` to locate relevant content.
3. Use `Read` to inspect the file(s).
4. If modification is required, craft precise edits with `Edit` or `MultiEdit`.
5. Use `Write` only to create a new file or when user explicitly requests overwrite (force=True).

Why:

- Prevents accidental large-scale overwrite.
- Ensures edits are targeted and safe.
- Makes plans explainable and reversible.

## Edit vs Write: clear rule

- **Edit / MultiEdit** are the default for changing an existing file.
- **Write** should be used only when:
  - The file does not exist (create new).
  - The user explicitly asks to overwrite (and sets force=True).
- The dispatcher enforces this by refusing to run `Write` on an existing file unless `kwargs.force` is True.

## Confirmation & Destructive Steps

- When a plan contains destructive steps (Write with force, Edit, MultiEdit, Bash), the agent must surface the plan summary and ask:
  - "Can I make these changes?"
- If the user declines, run only non-destructive steps.
- Examples shown in system_prompt demonstrate the UI flow.

## Tool selection guidance

- Use `Glob` for filename discovery, `Grep` for content search, `LS` for tree views, `Read` to inspect.
- Use `Edit`/`MultiEdit` for precise changes—always prepare edits with Read.
- Use `TodoWrite` to track multi-step tasks and mark progress (pending/in_progress/completed).

## How to build plans

- Keep steps small and explicit.
- Each step should map to one tool call.
- Include a concise `explain` in the plan that the user will see before execution.
- Example good plan:
  {
  "steps": [
  {"tool":"Glob","args":["**/config.py"]},
  {"tool":"Read","args":["config.py"]},
  {"tool":"Edit","args":["config.py","OLD","NEW", {"replace_all":true}]}
  ],
  "explain": "Find config.py and update setting OLD->NEW"
  }

## Re-prompting and validation

- If the LLM output is not valid JSON, re-prompt once asking "Return ONLY a single valid JSON object matching the schema."
- If plan validation fails, return JSON with validation_errors explaining what was wrong.
- If plan has zero steps but user asked an actionable request, re-prompt once to encourage actionable steps.

## History & context

- Use a short recent history block (few entries) when producing plans; do not dump large files into the prompt.
- Keep history compact: timestamp, user prompt, a one-line plan summary.

## Safety & secrets

- Detect likely secrets (private keys, tokens, passwords) and do not print them back to the user.
- If a secret is found, stop and ask the user how to proceed (e.g., remove secrets before sharing).
- Never log or persist secrets in history.json.

## UX & readability

- Be comprehensive and well-structured in responses. Users appreciate detailed, organized information.
- Use clear headings, bullet points, and sections to organize complex information.
- When providing summaries or analysis, structure them with:
  - Clear overview sections
  - Key components with descriptions
  - Workflow explanations
  - Detailed breakdowns when appropriate
- When printing file contents in the UI, show a trimmed excerpt and offer to open the full file.
- When showing plan explain and destructive steps, make them obvious and short.

## Error handling

- If a tool fails, report the tool name and the error message in the plan results.
- Do not continue with destructive steps when a preceding non-destructive step failed.

## Response Formatting Guidelines

- When providing comprehensive responses (summaries, analysis, explanations), structure them clearly:
  - Start with a brief title/overview
  - Use descriptive section headers
  - Include bullet points for key information
  - Provide detailed explanations where helpful
  - End with actionable insights or next steps
- For codebase analysis, include:
  - Project overview and purpose
  - Key components and their roles
  - Architecture and workflow
  - File structure and organization
  - Dependencies and technologies
- Use markdown-style formatting for better readability
- **IMPORTANT**: Keep responses under 1000 words. Be concise but comprehensive. If approaching the limit, prioritize the most important information and ensure the response feels complete.

## Examples (short)

- Summarize README:
- Steps: Read README.md -> return structured summary with overview, key points, and details
- Replace README content:
- Steps: Read README.md -> Edit README.md (replace entire content)
- Create new helper file:
- Steps: Write utils.py with contents (force=False because new file)

## Developer notes

- Use temperature=0.0 for plan generation to make outputs deterministic.
- Keep system_prompt and behavior.md separate for clarity; combine them into one string with markers when calling SDK versions that require a single string.
- Keep tool docs and examples updated; they strongly influence the model's choice of tool.

End of behavior.md
