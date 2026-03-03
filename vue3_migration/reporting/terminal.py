"""
Terminal output helpers — ANSI colors and formatting for CLI display.
"""

import sys

# ANSI escape codes
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_CYAN = "\033[36m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def supports_color() -> bool:
    """Check if the terminal supports ANSI color codes."""
    if not hasattr(sys.stdout, "isatty"):
        return False
    if not sys.stdout.isatty():
        return False
    return True


def green(text: str) -> str:
    return f"{_GREEN}{text}{_RESET}"


def yellow(text: str) -> str:
    return f"{_YELLOW}{text}{_RESET}"


def red(text: str) -> str:
    return f"{_RED}{text}{_RESET}"


def cyan(text: str) -> str:
    return f"{_CYAN}{text}{_RESET}"


def bold(text: str) -> str:
    return f"{_BOLD}{text}{_RESET}"


def dim(text: str) -> str:
    return f"{_DIM}{text}{_RESET}"


def red_bold(text: str) -> str:
    return f"{_RED}{_BOLD}{text}{_RESET}"


# -- Markdown colors (inline HTML for reports) --

def md_green(text: str) -> str:
    return f'<span style="color:#2ea043">{text}</span>'


def md_yellow(text: str) -> str:
    return f'<span style="color:#d29922">{text}</span>'


# -- Warning summary formatting --

def format_warning_summary(
    entries: "list",
    confidence_map: "dict",
) -> str:
    """Format a terminal-friendly warning summary for migration entries.

    Args:
        entries: list of MixinEntry objects (with .warnings, .mixin_stem)
        confidence_map: dict mapping mixin_stem -> ConfidenceLevel

    Returns:
        Formatted string ready for printing, or "" if no entries.
    """
    if not entries:
        return ""

    lines: list[str] = []
    for entry in entries:
        stem = entry.mixin_stem
        confidence = confidence_map.get(stem)
        conf_str = confidence.value if confidence else "?"

        if confidence and confidence.value == "HIGH":
            prefix = green("✓")
            conf_display = green(conf_str)
        elif confidence and confidence.value == "LOW":
            prefix = red("✗")
            conf_display = red(conf_str)
        else:
            prefix = yellow("⚠")
            conf_display = yellow(conf_str)

        warning_count = len(entry.warnings)
        if warning_count:
            lines.append(f"  {prefix} {stem} — {conf_display} confidence ({warning_count} warnings)")
            for w in entry.warnings:
                lines.append(f"    {yellow('⚠')} {w.category}: {w.message}")
        else:
            lines.append(f"  {prefix} {stem} — {conf_display} confidence")

    return "\n".join(lines)
