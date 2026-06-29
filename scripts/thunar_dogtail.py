#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dogtail.tree import root


ACTION_TO_BUTTON = {
    "back": "Back",
    "forward": "Forward",
    "up": "Open Parent",
    "home": "Home",
    "reload": "Reload",
    "icon_view": "Icon View",
    "list_view": "List View",
    "compact_view": "Compact View",
    "split_view": "Split View",
    "search": "Search for Files...",
    "open_terminal": "Open Terminal Here",
}


def _safe_name(node: Any) -> str:
    try:
        return str(getattr(node, "name", "") or "")
    except Exception:
        return ""


def _safe_role(node: Any) -> str:
    for attr in ("roleName", "getRoleName"):
        value = getattr(node, attr, None)
        try:
            if callable(value):
                return str(value())
            if value is not None:
                return str(value)
        except Exception:
            pass
    return ""


def _iter_children(node: Any) -> list[Any]:
    children = getattr(node, "children", None)
    if children is not None:
        try:
            return list(children)
        except Exception:
            pass
    return []


def _find_thunar_app() -> Any:
    for app in _iter_children(root):
        if _safe_role(app) == "application" and _safe_name(app) == "Thunar":
            return app
    raise RuntimeError("Thunar is not exposed through AT-SPI")


def _find_frame(app: Any) -> Any:
    frames = [child for child in _iter_children(app) if _safe_role(child) == "frame"]
    if not frames:
        raise RuntimeError("Thunar frame not found")
    return frames[0]


def _dump_node(node: Any, depth: int, max_depth: int, max_children: int) -> dict[str, Any]:
    children = _iter_children(node)
    payload: dict[str, Any] = {
        "name": _safe_name(node),
        "role": _safe_role(node),
        "child_count": len(children),
        "children": [],
    }
    if depth >= max_depth:
        if len(children) > max_children:
            payload["truncated_children"] = len(children) - max_children
        return payload
    for child in children[:max_children]:
        payload["children"].append(_dump_node(child, depth + 1, max_depth, max_children))
    if len(children) > max_children:
        payload["truncated_children"] = len(children) - max_children
    return payload


def _find_named_control(node: Any, name: str, roles: set[str] | None = None, max_depth: int = 8) -> Any | None:
    current_name = _safe_name(node)
    current_role = _safe_role(node)
    if current_name == name and (roles is None or current_role in roles):
        return node
    if max_depth <= 0:
        return None
    for child in _iter_children(node):
        found = _find_named_control(child, name, roles=roles, max_depth=max_depth - 1)
        if found is not None:
            return found
    return None


def _perform_click(node: Any) -> None:
    click_method = getattr(node, "click", None)
    if callable(click_method):
        click_method()
        return

    action_iface = getattr(node, "actions", None)
    if action_iface:
        for action in action_iface:
            action_name = str(getattr(action, "name", "") or "").lower()
            if action_name in {"click", "press", "activate"}:
                action.do()
                return

    do_action_named = getattr(node, "doActionNamed", None)
    if callable(do_action_named):
        for action_name in ("click", "press", "activate"):
            try:
                do_action_named(action_name)
                return
            except Exception:
                pass

    raise RuntimeError(f"Could not click control '{_safe_name(node)}'")


def cmd_tree(args: argparse.Namespace) -> int:
    app = _find_thunar_app()
    frame = _find_frame(app)
    payload = {
        "application": _dump_node(app, 0, args.max_depth, args.max_children),
        "frame": _dump_node(frame, 0, args.max_depth, args.max_children),
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def cmd_action(args: argparse.Namespace) -> int:
    app = _find_thunar_app()
    frame = _find_frame(app)
    button_name = ACTION_TO_BUTTON[args.action]
    control = _find_named_control(frame, button_name, roles={"push button", "toggle button"})
    if control is None:
        raise RuntimeError(f"Control not found: {button_name}")
    _perform_click(control)
    time.sleep(args.delay)
    json.dump(
        {
            "ok": True,
            "action": args.action,
            "control": button_name,
            "frame_name": _safe_name(frame),
        },
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")
    return 0


def main() -> int:
    os.environ.setdefault("DISPLAY", ":20")

    parser = argparse.ArgumentParser(description="Control Thunar through Dogtail/AT-SPI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    tree_parser = subparsers.add_parser("tree", help="Dump Thunar accessibility tree")
    tree_parser.add_argument("--max-depth", type=int, default=5)
    tree_parser.add_argument("--max-children", type=int, default=40)
    tree_parser.set_defaults(func=cmd_tree)

    action_parser = subparsers.add_parser("action", help="Click a named Thunar control")
    action_parser.add_argument("action", choices=sorted(ACTION_TO_BUTTON))
    action_parser.add_argument("--delay", type=float, default=0.4)
    action_parser.set_defaults(func=cmd_action)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
