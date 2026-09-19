"""Minimal YAML dump for the foundations bundle — no extra dependency."""

from __future__ import annotations

from typing import Any


def dump_yaml(value: Any, indent: int = 0) -> str:
    prefix = "  " * indent
    if isinstance(value, dict):
        if not value:
            return prefix + "{}\n"
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                dumped = dump_yaml(item, indent + 1)
                if dumped.strip():
                    lines.append(dumped.rstrip("\n"))
            else:
                lines.append(f"{prefix}{key}: {dump_scalar(item)}")
        return "\n".join(lines) + "\n"
    if isinstance(value, list):
        if not value:
            return prefix + "[]\n"
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(dump_yaml(item, indent + 1).rstrip("\n"))
            else:
                lines.append(f"{prefix}- {dump_scalar(item)}")
        return "\n".join(lines) + "\n"
    return prefix + dump_scalar(value) + "\n"


def dump_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or any(ch in text for ch in ":#{}[],&*?|>'!%@`"):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text
