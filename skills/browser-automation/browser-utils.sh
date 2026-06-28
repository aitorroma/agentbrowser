#!/usr/bin/env bash
# browser-utils.sh - Helper functions for browser automation
# Usage: source browser-utils.sh

CDP_URL="http://localhost:9222"
MCP_URL="http://127.0.0.1:8787"

# Get active page ID from cdp-cli
get_page_id() {
    local title="${1:-}"
    if [ -n "$title" ]; then
        cdp-cli tabs --cdp-url "$CDP_URL" 2>/dev/null | grep -i "$title" | head -1 | python3 -c "import sys,json; line=sys.stdin.readline().strip(); print(json.loads(line)['id'] if line else '')"
    else
        cdp-cli tabs --cdp-url "$CDP_URL" 2>/dev/null | head -1 | python3 -c "import sys,json; line=sys.stdin.readline().strip(); print(json.loads(line)['id'] if line else '')"
    fi
}

# Fill form field via CDP
fill_field() {
    local page_id="$1"
    local value="$2"
    local selector="$3"
    cdp-cli fill "$page_id" "$value" "$selector" --cdp-url "$CDP_URL"
}

# Click element via CDP
click_element() {
    local page_id="$1"
    local selector="$2"
    cdp-cli click "$page_id" "$selector" --cdp-url "$CDP_URL"
}

# Evaluate JavaScript via CDP
eval_js() {
    local page_id="$1"
    local js="$2"
    cdp-cli eval "$page_id" "$js" --cdp-url "$CDP_URL"
}

# Take screenshot via CDP
take_screenshot() {
    local page_id="$1"
    local output="${2:-/tmp/screenshot.png}"
    cdp-cli screenshot "$page_id" "$output" --cdp-url "$CDP_URL"
}

# Mouse click via desktop control
mouse_click() {
    local x="$1"
    local y="$2"
    curl -s -X POST "$MCP_URL/desktop/mouse/click" -H "Content-Type: application/json" -d "{\"x\":$x,\"y\":$y}"
}

# Type text via desktop control
type_text() {
    local text="$1"
    local delay="${2:-20}"
    curl -s -X POST "$MCP_URL/desktop/keyboard/type" -H "Content-Type: application/json" -d "{\"text\":\"$text\",\"delay_ms\":$delay}"
}

# Press key via desktop control
press_key() {
    local key="$1"
    curl -s -X POST "$MCP_URL/desktop/keyboard/press" -H "Content-Type: application/json" -d "{\"keys\":\"$key\"}"
}

# Focus window by name
focus_window() {
    local query="$1"
    curl -s -X POST "$MCP_URL/desktop/windows/focus" -H "Content-Type: application/json" -d "\"$query\""
}

# List windows
list_windows() {
    curl -s "$MCP_URL/desktop/windows"
}

# Take desktop screenshot
desktop_screenshot() {
    local path="${1:-/tmp/desktop-screenshot.png}"
    curl -s -X POST "$MCP_URL/desktop/screenshot" -H "Content-Type: application/json" -d "{\"path\":\"$path\"}"
    docker cp agentbrowser-browser:"$path" "$path" 2>/dev/null
    echo "Screenshot saved to: $path"
}

# Open Bitwarden popup
open_bitwarden() {
    local page_id="$1"
    eval_js "$page_id" 'window.open("chrome-extension://gfjamknononjpebljlkikhlebkhjngge/popup/index.html"); "opened"'
}

# Navigate to URL
navigate() {
    local page_id="$1"
    local url="$2"
    cdp-cli go "$page_id" "$url" --cdp-url "$CDP_URL"
}

# Get page snapshot (accessibility tree)
get_snapshot() {
    local page_id="$1"
    local format="${2:-ax}"
    cdp-cli snapshot "$page_id" --format "$format" --cdp-url "$CDP_URL"
}

echo "Browser automation functions loaded."
echo "Available: get_page_id, fill_field, click_element, eval_js, take_screenshot,"
echo "           mouse_click, type_text, press_key, focus_window, list_windows,"
echo "           desktop_screenshot, open_bitwarden, navigate, get_snapshot"
