#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any


def _safe_role_name(node: Any) -> str:
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


def _safe_name(node: Any) -> str:
    try:
        return str(getattr(node, "name", "") or "")
    except Exception:
        return ""


def _iter_children(node: Any) -> list[Any]:
    children = getattr(node, "children", None)
    if children is not None:
        try:
            return list(children)
        except Exception:
            pass

    child_count = getattr(node, "childCount", None)
    if isinstance(child_count, int):
        collected: list[Any] = []
        for index in range(child_count):
            try:
                if hasattr(node, "getChildAtIndex"):
                    child = node.getChildAtIndex(index)
                else:
                    child = node[index]
            except Exception:
                continue
            if child is not None:
                collected.append(child)
        return collected

    try:
        return list(node)
    except Exception:
        return []


def _dump_node(node: Any, depth: int, max_depth: int, max_children: int) -> dict[str, Any]:
    children = _iter_children(node)
    payload: dict[str, Any] = {
        "name": _safe_name(node),
        "role": _safe_role_name(node),
        "children": [],
        "child_count": len(children),
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


def _find_apps(root_node: Any, app_query: str | None) -> list[Any]:
    apps = _iter_children(root_node)
    if not app_query:
        return apps
    lowered = app_query.lower()
    return [app for app in apps if lowered in _safe_name(app).lower()]


def _load_root() -> tuple[str, Any]:
    dogtail_error: Exception | None = None
    try:
        from dogtail.tree import root as dogtail_root

        return "dogtail", dogtail_root
    except Exception as exc:
        dogtail_error = exc

    try:
        import pyatspi

        return "pyatspi", pyatspi.Registry.getDesktop(0)
    except Exception as exc:
        raise RuntimeError(
            "Could not load Dogtail or pyatspi. "
            f"Dogtail error: {dogtail_error!r}. pyatspi error: {exc!r}"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump desktop accessibility hierarchy with Dogtail/AT-SPI.")
    parser.add_argument("--app", help="Filter top-level applications by substring, e.g. firefox or chromium")
    parser.add_argument("--max-depth", type=int, default=4, help="Maximum recursion depth to print")
    parser.add_argument("--max-children", type=int, default=25, help="Maximum children per node")
    parser.add_argument("--delay", type=float, default=0.0, help="Sleep before inspection to let UI settle")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a text tree")
    args = parser.parse_args()

    if args.delay > 0:
        time.sleep(args.delay)

    backend, root_node = _load_root()
    apps = _find_apps(root_node, args.app)
    result = {
        "backend": backend,
        "display": sys.argv and __import__("os").environ.get("DISPLAY", ""),
        "app_filter": args.app,
        "applications_found": len(apps),
        "applications": [_dump_node(app, 0, args.max_depth, args.max_children) for app in apps],
    }

    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    print(f"backend={backend} display={result['display']!r} applications_found={len(apps)}")
    if args.app and not apps:
        print("No matching application was exposed through AT-SPI.")
        print("Tip: ensure the app is open and the desktop accessibility bus is active.")
        return 1

    def render(node: dict[str, Any], prefix: str = "") -> None:
        name = node.get("name") or "<unnamed>"
        role = node.get("role") or "<unknown-role>"
        print(f"{prefix}- {role}: {name} [{node.get('child_count', 0)} children]")
        for child in node.get("children", []):
            render(child, prefix + "  ")
        if node.get("truncated_children"):
            print(f"{prefix}  … +{node['truncated_children']} more children")

    for app in result["applications"]:
        render(app)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
