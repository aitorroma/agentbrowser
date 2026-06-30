# MCP Tools Reference

Complete inventory of tools exposed by the AgentBrowser MCP server at `http://127.0.0.1:18787/mcp`.

## Browser / Chrome

| Tool | Description |
|------|-------------|
| `browser_cdp_launch` | Launch Chrome with CDP enabled |
| `browser_cdp_status` | Check CDP browser status |
| `chrome_maximize` | Maximize Chrome window |

## Page Interaction

| Tool | Description |
|------|-------------|
| `click` | Click element by CSS selector |
| `fill` | Fill input field by selector |
| `key_press` | Press key or keyboard shortcut |
| `key_type` | Typewriter-style text input with delay |
| `mouse_click` | Click at coordinates (x, y) |
| `mouse_double_click` | Double click at coordinates |
| `mouse_drag` | Drag from (x1,y1) to (x2,y2) |
| `mouse_move` | Move mouse cursor |
| `mouse_scroll` | Scroll mouse wheel |
| `goto` | Navigate to URL |
| `eval` | Execute JavaScript in page context |
| `screenshot` | Capture full page screenshot |
| `screenshot_window` | Screenshot specific window |
| `get_markdown` | Extract page content as Markdown |

## Desktop Applications

| Tool | Description |
|------|-------------|
| `app_launch` | Launch application by name |
| `app_list` | List available applications |
| `app_open` | Open application |
| `app_status` | Check application status |
| `open_app` | Launch known desktop app (launcher, terminal, firefox, thunar, chromium) |
| `open_terminal` | Open foot terminal |
| `open_firefox` | Open Firefox browser |
| `open_launcher` | Open fuzzel application launcher |
| `open_files` | Open default file manager (Dolphin) |
| `open_dolphin` | Open Dolphin file manager |

## Niri Compositor (Wayland)

| Tool | Description |
|------|-------------|
| `niri_start` | Start niri compositor |
| `niri_status` | Check niri status |
| `niri_msg` | Execute `niri msg` subcommand |
| `niri_spawn` | Spawn command in Wayland session |
| `niri_windows` | List windows |
| `niri_workspaces` | List workspaces |
| `niri_outputs` | List outputs/monitors |
| `niri_focused_window` | Get focused window info |
| `niri_action` | Execute niri action (focus, move, workspace, fullscreen, etc.) |
| `niri_click_in_window` | Click at (x,y) in a Wayland window |
| `niri_type_in_window` | Type text into a Wayland window |

## Thunar File Manager

| Tool | Description |
|------|-------------|
| `thunar_action` | Execute Thunar action |
| `thunar_go` | Navigate to path |
| `thunar_open` | Open path in Thunar |
| `thunar_tree` | Get directory tree |
| `thunar_maximize` | Maximize Thunar window |

## Window Management

| Tool | Description |
|------|-------------|
| `window_list` | List all windows |
| `window_focus` | Focus window by query |
| `window_maximize` | Maximize window |
| `window_minimize` | Minimize window |
| `window_restore` | Restore window |

## Workspace Navigation

| Tool | Description |
|------|-------------|
| `workspace_goto` | Switch to workspace by index or name |
| `workspace_next` | Switch to next workspace |
| `workspace_prev` | Switch to previous workspace |
| `workspace_set_name` | Name the focused workspace |

## Security / Bitwarden

| Tool | Description |
|------|-------------|
| `configure_bitwarden` | Configure Bitwarden connection |
| `secure_login` | Perform secure site login (credentials never exposed to agent) |
| `get_totp` | Get TOTP code for site |
| `list_accounts` | List Bitwarden accounts |
| `logout_bitwarden` | Logout from Bitwarden |

## WebAuthn / Passkeys

| Tool | Description |
|------|-------------|
| `webauthn_enable` | Attach virtual authenticator for passkeys |
| `webauthn_disable` | Detach virtual authenticator |
| `webauthn_list_credentials` | List passkey metadata |
| `webauthn_save` | Persist passkeys to profile |
| `webauthn_status` | Check authenticator status |

## Clipboard

| Tool | Description |
|------|-------------|
| `clipboard_get` | Get clipboard content |
| `clipboard_set` | Set clipboard content |

## Screenshots

| Tool | Description |
|------|-------------|
| `screen_shot` | Capture screen (full or region) |
| `screenshot` | Capture page screenshot |
| `screenshot_window` | Capture specific window |

## wdotool (Wayland Input)

| Tool | Description |
|------|-------------|
| `wdotool_click` | Click mouse button via wdotool |
| `wdotool_getactivewindow` | Get active window ID |
| `wdotool_info` | Get wdotool backend info |
| `wdotool_key` | Press key combination |
| `wdotool_mousemove` | Move mouse to position |
| `wdotool_scroll` | Scroll mouse wheel |
| `wdotool_search` | Search for windows |
| `wdotool_type` | Type text via wdotool |
| `wdotool_windowactivate` | Activate/focus window |
| `wdotool_windowclose` | Close window |

## Input Monitoring

| Tool | Description |
|------|-------------|
| `wev_monitor` | Monitor Wayland keyboard events for debugging |

---

**Total: ~70 tools**

All tools are available through the MCP endpoint at `http://127.0.0.1:18787/mcp` when the AgentBrowser container is running.
