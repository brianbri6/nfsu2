#!/usr/bin/env python3
"""Patch user-facing Android UI strings in a prebuilt NFSU2 APK via apktool smali.

This script never builds or replaces the native game binaries. The APK is unpacked
with apktool -r, only literal strings in .smali files are translated, and apktool
reassembles the package. Verify and sign the output before distribution.
"""
import argparse
import json
from pathlib import Path
import re
import sys

CONST_STRING = re.compile(r'(?m)^(?P<prefix>\s*const-string(?:/jumbo)?\s+[vp]\d+,\s*")(?P<value>(?:\\.|[^"\\])*)(?P<suffix>")')
GAME_LANGUAGE_METHOD = re.compile(
    r'(?ms)(\.method[^\n]*\blanguage\(Landroid/content/Context;\)Ljava/lang/String;.*?)(\.end method)'
)
UPSTREAM = "codepdbh/nfsu2-recompiled"
FORK = "brianbri6/nfsu2"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("decoded_apk", type=Path)
    parser.add_argument("--translations", type=Path, default=Path("localization/en-us.json"))
    args = parser.parse_args()
    translations = json.loads(args.translations.read_text(encoding="utf-8"))
    ordered = sorted(translations.items(), key=lambda pair: len(pair[0]), reverse=True)
    changed, matches, language_defaults, matched_keys = 0, 0, 0, set()

    for smali in args.decoded_apk.glob("smali*/**/*.smali"):
        original = smali.read_text(encoding="utf-8")
        def translate(m):
            global matches
            value = m.group("value")
            replacement = value.replace(UPSTREAM, FORK)
            for source, target in ordered:
                if source in replacement:
                    replacement = replacement.replace(source, target)
                    matched_keys.add(source)
            if replacement != value:
                matches += 1
            return m.group("prefix") + replacement + m.group("suffix")
        updated = CONST_STRING.sub(translate, original)
        if smali.name == "GameOptions.smali":
            def set_default(method):
                global language_defaults
                first, last = method.group(1), method.group(2)
                new, n = re.subn(
                    r'(?m)(^\s*const-string(?:/jumbo)?\s+[vp]\d+,\s+)"Spanish"',
                    r'\1"English UK"', first
                )
                language_defaults += n
                return new + last
            updated = GAME_LANGUAGE_METHOD.sub(set_default, updated)
        if updated != original:
            smali.write_text(updated, encoding="utf-8")
            changed += 1

    print(json.dumps({
        "smali_files_changed": changed,
        "translated_const_strings": matches,
        "translation_keys_matched": len(matched_keys),
        "game_language_defaults_changed": language_defaults,
        "unmatched_translations": sorted(set(translations) - matched_keys)
    }, ensure_ascii=False, indent=2))
    if changed < 5 or matches < 50 or language_defaults != 1:
        sys.exit("ERROR: APK localization patch incomplete; upstream APK layout/version may have changed.")


if __name__ == "__main__":
    main()
