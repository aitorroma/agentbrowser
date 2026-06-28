#!/usr/bin/env bash
# example-form-fill.sh - Example: Fill a form using CDP + Desktop + Bitwarden
set -euo pipefail

source "$(dirname "$0")/browser-utils.sh"

echo "=== Browser Automation Example ==="

# 1. Get active page
echo "1. Getting active page..."
PAGE_ID=$(get_page_id "Bitwarden")
echo "   Page ID: $PAGE_ID"

# 2. Navigate to form
echo "2. Navigating to form..."
navigate "$PAGE_ID" "https://comunidad-n8n.com/presupuesto"
sleep 3

# 3. Get page snapshot to understand structure
echo "3. Getting page snapshot..."
get_snapshot "$PAGE_ID" > /tmp/snapshot.json

# 4. Fill form fields via CDP
echo "4. Filling form fields..."
eval_js "$PAGE_ID" '
function setVal(sel, val) {
    var el = document.querySelector(sel);
    if (!el) return null;
    var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    setter.call(el, val);
    el.dispatchEvent(new Event("input", {bubbles: true}));
    el.dispatchEvent(new Event("change", {bubbles: true}));
    return el.value;
}
function setTA(sel, val) {
    var el = document.querySelector(sel);
    if (!el) return null;
    var setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
    setter.call(el, val);
    el.dispatchEvent(new Event("input", {bubbles: true}));
    el.dispatchEvent(new Event("change", {bubbles: true}));
    return el.value;
}
JSON.stringify({
    n: setVal("#text-1732725514549", "Aitor Roma"),
    e: setVal("#email", "aitor@nimbox360.com"),
    p: setVal("#text-1732725568763", "612 345 678"),
    c: setVal("#text-1732725614982", "Nimbox360"),
    j: setVal("#text-1732725666655", "CEO & Founder"),
    q: setTA("#textarea-1732726102533", "Automatización de procesos internos"),
    h: setTA("#textarea-1732726501330", "Slack, Gmail, HubSpot")
})'

# 5. Set select dropdown
echo "5. Setting dropdown..."
eval_js "$PAGE_ID" '
var s = document.querySelector("#select-1732726123126");
s.value = "option-2";
s.dispatchEvent(new Event("change", {bubbles: true}));
"done"'

# 6. Click radio buttons
echo "6. Clicking radio buttons..."
eval_js "$PAGE_ID" '
document.querySelector("#radio_radio-group-1732726387064_1").click();
document.querySelector("#radio_radio-group-1732726581819_1").click();
"done"'

# 7. Take screenshot
echo "7. Taking screenshot..."
take_screenshot "$PAGE_ID" "/tmp/form-filled.png"

echo "=== Done! ==="
echo "Screenshot saved to /tmp/form-filled.png"
