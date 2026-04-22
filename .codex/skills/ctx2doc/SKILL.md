---
name: ctx2doc
description: Use this skill when the user wants to create, refresh, inspect, or reuse `ctx2doc` context snapshots for the current project in Codex. This skill routes requests like `ctx2doc snapshot`, `ctx2doc resume`, or `ctx2doc status` to the matching `ctx2doc` MCP tool instead of manually summarizing the session.
metadata:
  short-description: Create or load ctx2doc snapshots
---

# ctx2doc skill

This skill is a thin orchestration layer over the `ctx2doc` MCP server. Do not reimplement snapshot logic in the model. Use the matching MCP tool.

## Trigger mapping

- If the user asks for `ctx2doc snapshot`, call `ctx2doc.snapshot`.
- If the user asks for `ctx2doc resume`, call `ctx2doc.resume_context`.
- If the user asks for `ctx2doc status`, call `ctx2doc.status`.

## Rules

- Prefer the MCP tool over writing summaries manually.
- Do not fabricate snapshot content if the tool is unavailable or errors.
- If the MCP server is not connected, tell the user that `ctx2doc` MCP needs to be registered first.
- Use the current project root by default unless the user explicitly asks for another path.
- After a successful tool call, report only the relevant result:
  - for `snapshot`: the created file path and session ID
  - for `resume`: the returned bootstrap context
  - for `status`: the detected session and latest snapshot path
