#!/usr/bin/env python3
"""
check_env.py — run this after setup.sh and paste the last line into the homework form.

It prints ONE line. If it starts with GO you are ready for Session 4. If it starts
with NO-GO, the line names what is broken; paste it anyway — a sortable column of
what is broken across the class is more useful to your instructor than silence.

    python check_env.py
"""

from __future__ import annotations

import importlib.metadata as md
import os
import platform
import sys

PINS = {
    "langchain": "1.3.16",
    "langchain-core": "1.6.1",
    "langgraph": "1.2.11",
    "langsmith": "0.11.1",
    "langchain-tavily": "0.2.18",
}
PROVIDER_PKG = {
    "anthropic": "langchain-anthropic",
    "openai": "langchain-openai",
    "google": "langchain-google-genai",
}
PROVIDER_KEY = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    problems: list[str] = []

    if sys.version_info < (3, 11):
        problems.append(f"python{sys.version_info.major}.{sys.version_info.minor}")

    if sys.prefix == sys.base_prefix:
        problems.append("no-venv")

    for pkg, want in PINS.items():
        try:
            got = md.version(pkg)
        except md.PackageNotFoundError:
            problems.append(f"missing:{pkg}")
            continue
        if got != want:
            problems.append(f"{pkg}={got}!={want}")

    provider = os.environ.get("COURSE_PROVIDER", "").strip().lower()
    if provider not in PROVIDER_PKG:
        problems.append("COURSE_PROVIDER-unset")
    else:
        pkg = PROVIDER_PKG[provider]
        try:
            md.version(pkg)
        except md.PackageNotFoundError:
            problems.append(f"missing:{pkg}")
        if not os.environ.get(PROVIDER_KEY[provider]):
            problems.append(f"no-key:{PROVIDER_KEY[provider]}")

    for var in ("TAVILY_API_KEY", "LANGSMITH_API_KEY"):
        if not os.environ.get(var):
            problems.append(f"no-key:{var}")

    # reasoning_effort is a standard parameter only from langchain-core 1.5.2.
    try:
        core = tuple(int(x) for x in md.version("langchain-core").split(".")[:3])
        if core < (1, 5, 2):
            problems.append("core<1.5.2")
    except Exception:
        pass

    # Does the provider import actually work? This is where google most often fails.
    if provider in PROVIDER_PKG and f"missing:{PROVIDER_PKG[provider]}" not in problems:
        mod = {"anthropic": "langchain_anthropic",
               "openai": "langchain_openai",
               "google": "langchain_google_genai"}[provider]
        try:
            __import__(mod)
        except Exception as exc:
            problems.append(f"import-fail:{mod}:{type(exc).__name__}")

    os_tag = f"{platform.system()}-{platform.machine()}"
    py = f"{sys.version_info.major}.{sys.version_info.minor}"
    head = "GO" if not problems else "NO-GO"
    print()
    print(f"{head} | {os_tag} | py{py} | {provider or '?'} | "
          f"{';'.join(problems) if problems else 'all-pins-ok'}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
