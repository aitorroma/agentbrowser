---
name: agentbrowser-desktop-mcp
description: >
  Use the local AgentBrowser MCP server to control the browser and full virtual desktop.
  Trigger: When the AI needs to operate the browser appliance, use Firefox via desktop control, use Chromium via CDP/browser tools, or drive the desktop autonomously from OpenCode or another MCP client.
license: Apache-2.0
metadata:
  author: aitorroma
  version: "1.0"
---

## When to Use

- When the task requires controlling the local browser appliance through MCP
- When the agent must operate Firefox without CDP
- When the agent must use mouse, keyboard, clipboard, or windows on the virtual desktop
- When OpenCode or another MCP client needs a ready-to-use config for this project

## Critical Patterns

- MCP endpoint: `http://127.0.0.1:8787/mcp`
- Use **browser tools** for Chromium/CDP workflows:
  - `goto`, `fill`, `click`, `eval`, `screenshot`, `get_markdown`
- Use **desktop tools** for Firefox or whole-desktop workflows:
  - `screen_shot`, `mouse_move`, `mouse_click`, `mouse_drag`, `mouse_scroll`
  - `key_type`, `key_press`
  - `clipboard_get`, `clipboard_set`
  - `window_list`, `window_focus`
  - `app_list`, `app_launch`, `app_status`
- Prefer Firefox + desktop tools for “human-like” browsing
- Prefer Chromium + browser tools when deterministic DOM control or CDP is needed
- Before typing, usually do:
  1. `app_launch()` if needed
  2. `window_list()`
  3. `window_focus()`
  4. `key_press("ctrl+l")` or click target
  5. `key_type(...)`
- For desktop validation, always finish with `screen_shot()`

## Decision Table

| Goal | Preferred toolset |
|------|-------------------|
| Navigate browser reliably by DOM | Browser MCP tools |
| Extract rendered markdown | `get_markdown(url)` |
| Use Firefox | Desktop MCP tools |
| Handle popups, file pickers, dialogs, downloads | Desktop MCP tools |
| Operate full GUI like a human | Desktop MCP tools |

## Code Examples

### Example MCP flow for Firefox

1. `app_launch("firefox")`
2. `window_list()`
3. `window_focus("Firefox")`
4. `key_press("ctrl+l")`
5. `key_type("https://example.com")`
6. `key_press("Return")`
7. `screen_shot()`

### Example MCP flow for Chromium/CDP

1. `goto("https://example.com")`
2. `click("text=Login")`
3. `fill("#email", "tu-correo@example.com")`
4. `screenshot()`

## Commands

```bash
# Rebuild and restart the appliance after image or launcher changes
docker compose up -d --build

# Quick health check
curl http://127.0.0.1:8787/healthz

# List desktop apps
curl http://127.0.0.1:8787/desktop/apps

# OpenCode: guided MCP setup
opencode mcp add
```

## OpenCode Configuration

OpenCode supports MCP under the `mcp` key in `opencode.json`, and also provides `opencode mcp add` for guided setup.

Minimal remote MCP entry:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "agentbrowser": {
      "type": "remote",
      "url": "http://127.0.0.1:8787/mcp"
    }
  }
}
```

## Resources

- **Templates**: See [assets/](assets/) for OpenCode config snippets
