#!/usr/bin/env python3
"""Patch an upstream NFSU2 APK decoded by apktool, without recompiling native code.

Three surfaces are covered: smali/DEX strings, Android XML resources, and
length-limited ELF strings. Existing Spanish language preferences are retired
once, while the launcher language picker and native "language" option survive.
The post-patch audit is mandatory; unknown Spanish prompts stop the release.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

CONST = re.compile(
    r'(?m)^(?P<start>\s*const-string(?:/jumbo)?\s+[vp]\d+,\s*")'
    r'(?P<value>(?:\\.|[^"\\])*)(?P<end>")'
)
METHOD = re.compile(r"(?ms)^\.method[^\n]*\n.*?^\.end method[^\n]*$", re.MULTILINE)
LANGUAGE_KEY = "language_english_v01411"
UPSTREAM = "codepdbh/nfsu2-recompiled"
FORK = "brianbri6/nfsu2"


def patch_smali(contents: str, filename: str, translations: dict[str, str],
                stats: dict[str, int], matched: set[str]) -> str:
    """Only modify string instructions, not class/method signatures."""
    ordered = sorted(translations.items(), key=lambda kv: -len(kv[0]))

    def translate(m: re.Match[str]) -> str:
        old = m.group("value")
        # apktool encodes every non-ASCII character in smali as \\uXXXX.
        # Source dictionaries contain literal UTF-8 characters. Normalize only
        # Unicode escapes, preserving smali's \\n and escaped quote syntax.
        normalized = re.sub(
            r"\\u([0-9a-fA-F]{4})",
            lambda x: chr(int(x.group(1), 16)), old
        )
        new = normalized.replace(UPSTREAM, FORK)
        for source, target in ordered:
            if source in new:
                new = new.replace(source, target)
                matched.add(source)
        if old != new:
            stats["smali_strings"] += 1
        return m.group("start") + new + m.group("end")

    contents = CONST.sub(translate, contents)
    if filename == "GameOptions.smali":
        # The .field constant may be emitted independently of its inlined uses.
        contents, n = re.subn(
            r'(?m)(^\.field[^\n]*\bLANGUAGE:Ljava/lang/String;\s*=\s*)"language"',
            lambda m: m.group(1) + '"' + LANGUAGE_KEY + '"', contents
        )
        stats["preference_fields"] += n

    if filename == "GameActivity.smali":
        # Native guest boot reports "Starting game CRT entry…" in the English
        # binary, but the original Java overlay checks "Starting CRT entry
        # point". That branch never runs, leaving the top-left PopupWindow up.
        # Patch the original APK directly: don't depend on recompiling Java.
        contents, n = re.subn(
            r'(?m)(^\s*const-string(?:/jumbo)?\s+[vp]\d+,\s+)"Starting CRT entry point"',
            lambda m: m.group(1) + '"Starting game CRT entry"', contents
        )
        stats["overlay_startup_triggers"] += n

        def shorten_overlay_timeout(m: re.Match[str]) -> str:
            method = m.group()
            if '"Starting game CRT entry"' not in method:
                return method
            # Within the startup-status callback, postDelayed() gets 8000ms.
            # Keep fatal/error messages in the original persistent else branch.
            method, count = re.subn(
                r'(?m)(^\s*const-wide/16\s+[vp]\d+,\s+)0x1f40\b',
                lambda z: z.group(1) + '0x1388', method
            )
            stats["overlay_timeout_patches"] += count
            return method

        contents = METHOD.sub(shorten_overlay_timeout, contents)

    if filename in {"GameOptions.smali", "LauncherActivity.smali"}:
        def migrate(m: re.Match[str]) -> str:
            method = m.group()
            header = method.split("\n", 1)[0]
            if filename == "GameOptions.smali" and re.search(r"\blanguage\(Landroid/content/Context;\)", header):
                method, n = re.subn(
                    r'(?m)(^\s*const-string(?:/jumbo)?\s+[vp]\d+,\s+)"Spanish"',
                    lambda x: x.group(1) + '"English UK"', method
                )
                stats["english_defaults"] += n
                method, n = re.subn(
                    r'(?m)(^\s*const-string(?:/jumbo)?\s+[vp]\d+,\s+)"language"',
                    lambda x: x.group(1) + '"' + LANGUAGE_KEY + '"', method
                )
                stats["preference_getters"] += n
            if filename == "LauncherActivity.smali" and ("chooseLanguage(" in header or "lambda$chooseLanguage$" in header):
                method, n = re.subn(
                    r'(?m)(^\s*const-string(?:/jumbo)?\s+[vp]\d+,\s+)"language"',
                    lambda x: x.group(1) + '"' + LANGUAGE_KEY + '"', method
                )
                stats["preference_setters"] += n
            return method
        contents = METHOD.sub(migrate, contents)
    return contents


def patch_native(source: bytes, translations: dict[str, str], matched: set[str]) -> tuple[bytes, int]:
    """Fixed-size ELF replacements preserve embedded JSON and larger strings."""
    hits = 0
    output = source
    for old, new in sorted(translations.items(), key=lambda kv: -len(kv[0])):
        encoded = old.encode("utf-8")
        replacement = new.encode("utf-8")
        if len(replacement) > len(encoded):
            raise ValueError(f"native replacement is longer than source: {old!r}")
        count = output.count(encoded)
        if count:
            # Use trailing spaces; an embedded NUL could truncate a JSON payload.
            padding = b" " * (len(encoded) - len(replacement))
            output = output.replace(encoded, replacement + padding)
            hits += count
            matched.add(old)
    if len(source) != len(output):
        raise AssertionError("native library changed size")
    return output, hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("decoded_apk", type=Path)
    parser.add_argument("--translations", type=Path, default=Path("localization/en-us.json"))
    parser.add_argument("--native-translations", type=Path, default=Path("localization/native-en-us.json"))
    parser.add_argument("--audit-report", type=Path, default=None)
    args = parser.parse_args()
    root = args.decoded_apk
    if not root.is_dir() or not list(root.glob("smali*/**/*.smali")):
        parser.error("Provide a full apktool-decoded APK with smali directories")
    ui = json.loads(args.translations.read_text(encoding="utf-8"))
    native = json.loads(args.native_translations.read_text(encoding="utf-8"))
    stats = {k: 0 for k in (
        "smali_files", "smali_strings", "xml_files", "asset_files", "native_files",
        "native_strings", "preference_fields", "preference_getters",
        "preference_setters", "english_defaults", "overlay_startup_triggers",
        "overlay_timeout_patches")}
    matched_ui: set[str] = set()
    matched_native: set[str] = set()
    for path in sorted(root.glob("smali*/**/*.smali")):
        before = path.read_text(encoding="utf-8")
        after = patch_smali(before, path.name, ui, stats, matched_ui)
        if before != after:
            path.write_text(after, encoding="utf-8")
            stats["smali_files"] += 1

    # The app currently builds most strings directly in Java, but cover future
    # resources too. XML replacements must preserve valid escaped XML.
    for path in sorted(root.glob("res/**/*.xml")):
        old = path.read_text(encoding="utf-8")
        updated = old
        for source, target in sorted(ui.items(), key=lambda kv: -len(kv[0])):
            if source in updated:
                updated = updated.replace(source, target)
                matched_ui.add(source)
        if updated != old:
            import xml.etree.ElementTree as ET
            ET.fromstring(updated)
            path.write_text(updated, encoding="utf-8")
            stats["xml_files"] += 1

    # Also cover app-owned text assets (layout presets / embedded help/config).
    for path in sorted((root / "assets").rglob("*")) if (root / "assets").is_dir() else []:
        if not path.is_file() or path.suffix.lower() not in {
            ".txt", ".json", ".xml", ".html", ".htm", ".properties", ".md"
        }:
            continue
        try:
            old = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        updated = old
        for source, target in sorted(ui.items(), key=lambda kv: -len(kv[0])):
            if source in updated:
                updated = updated.replace(source, target)
                matched_ui.add(source)
        if updated != old:
            if path.suffix.lower() == ".json":
                json.loads(updated)
            path.write_text(updated, encoding="utf-8")
            stats["asset_files"] += 1

    # Restrict ELF rewriting to the application's own shared libraries.
    for path in sorted(root.glob("lib/**/libnfsu2*.so")):
        old = path.read_bytes()
        updated, n = patch_native(old, native, matched_native)
        if updated != old:
            path.write_bytes(updated)
            stats["native_files"] += 1
        stats["native_strings"] += n

    # Mandatory audit (both source-like and ELF byte strings).
    from audit_nfsu2_apk_english import audit
    findings = audit(root)
    report = {
        **stats,
        "ui_translation_keys_matched": len(matched_ui),
        "native_translation_keys_matched": len(matched_native),
        "unmatched_ui_keys": sorted(set(ui) - matched_ui),
        "unmatched_native_keys": sorted(set(native) - matched_native),
        "untranslated_spanish": findings,
    }
    message = json.dumps(report, indent=2, ensure_ascii=False)
    print(message)
    if args.audit_report:
        args.audit_report.parent.mkdir(parents=True, exist_ok=True)
        args.audit_report.write_text(message + "\n", encoding="utf-8")
    problems = []
    if stats["smali_files"] < 5 or stats["smali_strings"] < 50:
        problems.append("Too few strings patched; upstream APK may have changed")
    if stats["english_defaults"] != 1:
        problems.append("GameOptions English default was not patched exactly once")
    if not stats["preference_getters"] or not stats["preference_setters"]:
        problems.append("Old saved Spanish language preference still in use")
    if stats["overlay_startup_triggers"] != 1:
        problems.append("Top-left startup overlay trigger not patched exactly once")
    if stats["overlay_timeout_patches"] != 1:
        problems.append("Top-left overlay 5-second auto-dismiss timeout not patched exactly once")
    if findings:
        problems.append("Spanish app-owned strings remain (see audit report)")
    if problems:
        for p in problems:
            print("ERROR:", p, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
