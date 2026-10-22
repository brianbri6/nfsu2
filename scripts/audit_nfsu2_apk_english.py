#!/usr/bin/env python3
"""Inventory Spanish user-facing strings in a decoded NFSU2 Android APK.

Reports DEX const-string values, resources, and text in app-owned ELF shared
libraries. Only probable Spanish UI/error phrases are blockers. Technical IDs,
file names, and the English word "Spanish" are intentionally not blocked.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from xml.etree import ElementTree

SMALI_STRINGS = re.compile(r'(?m)^\s*const-string(?:/jumbo)?\s+[vp]\d+,\s*"((?:\\.|[^"\\])*)"')
NATIVE_STRINGS = re.compile(rb"[\x20-\x7e\x80-\xff]{8,}")
# Multiword markers minimize false positives from English technical logs.
SPANISH = re.compile(
    r"(?:\b(?:no se|se pudo|no hay|se cerr[oó]|se guard[oó]|"
    r"el paquete|el juego|el driver|el sistema|del juego|del sistema|"
    r"en el launcher|en la memoria|para ver|por favor|la gpu|"
    r"driver con|funciones vulkan incompletas|hle pendiente|"
    r"probar driver|controles del juego|texturas comprimidas|"
    r"sincron[ií]a cpu|cach[eé] gr[aá]fica|opciones de controles|"
    r"guardar dise[nñ]o|datos accesibles|memoria interna|"
    r"comprobando|cargando novedades|falta[n]? carpetas|"
    r"falta[n]? funciones|archivos del juego|pantalla panor[aá]mica|"
    r"escribe un nombre|guardar layout|el modo online|"
    r"se aplican|se conecta|control de inclinaci[oó]n|"
    r"conducci[oó]n por inclinaci[oó]n)\b|[¿¡])",
    re.IGNORECASE,
)
ACCENTED_SPANISH = re.compile(r"(?:[áéíóúñÁÉÍÓÚÑ])")
COMMON_UI = re.compile(
    r"\b(?:jugar|guardar|guardado|cancelar|aceptar|volver|importar|eliminar|"
    r"restaurar|aplicar|reiniciar|reintentar|carpetas|seleccionar|"
    r"actualizar|novedades|idioma|conducci[oó]n|opciones|sistema|"
    r"falta[n]?|cargando|comprobando|reemplazar|escribir|sensibilidad|"
    r"minimapa|servidor online|captura de pantalla)\b", re.IGNORECASE
)


def suspect(s: str) -> bool:
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
    if SPANISH.search(s) or COMMON_UI.search(s):
        return True
    # Accents in non-English Latin strings usually indicate untranslated UI.
    # Avoid matching French/Danish/Japanese labels left in language identifiers.
    if ACCENTED_SPANISH.search(s) and not (
        s.startswith("LANGUAGES/")
        or s.casefold() in {"français", "nederlands", "español", "italiano"} 
    ):
        return True
    return False


def audit(root: Path) -> list[dict[str, str | int]]:
    findings: list[dict[str, str | int]] = []
    for path in sorted(root.glob("smali*/**/*.smali")):
        text = path.read_text(encoding="utf-8")
        for m in SMALI_STRINGS.finditer(text):
            value = m.group(1)
            if suspect(value):
                findings.append({"surface": "smali", "file": str(path.relative_to(root)),
                                 "line": text.count("\n", 0, m.start()) + 1, "text": value[:240]})
    for path in sorted(root.glob("res/**/*.xml")):
        try:
            tree = ElementTree.parse(path)
            strings = [(node.text or "") for node in tree.iter()]
            strings += [val for node in tree.iter() for val in node.attrib.values()]
        except ElementTree.ParseError as error:
            findings.append({"surface": "xml", "file": str(path.relative_to(root)),
                             "line": 0, "text": f"Malformed XML: {error}"})
            continue
        for value in strings:
            if suspect(value):
                findings.append({"surface": "xml", "file": str(path.relative_to(root)),
                                 "line": 0, "text": value[:240]})
    # Some APKs package help, menus, or presets as plain-text assets.
    assets_dir = root / "assets"
    if assets_dir.is_dir():
        for path in sorted(assets_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {
                ".txt", ".json", ".xml", ".html", ".htm", ".md", ".properties"
            }:
                continue
            try:
                raw = path.read_text(encoding="utf-8")
            except (UnicodeError, OSError):
                continue
            for line_no, line in enumerate(raw.splitlines(), 1):
                if suspect(line):
                    findings.append({"surface": "asset", "file": str(path.relative_to(root)),
                                     "line": line_no, "text": line[:240]})
    for path in sorted(root.glob("lib/**/libnfsu2*.so")):
        binary = path.read_bytes()
        seen: set[str] = set()
        for m in NATIVE_STRINGS.finditer(binary):
            value = m.group().decode("utf-8", errors="ignore")
            if value in seen or not suspect(value):
                continue
            seen.add(value)
            findings.append({"surface": "native", "file": str(path.relative_to(root)),
                             "line": 0, "text": value[:240]})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("decoded_apk", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not args.decoded_apk.is_dir():
        parser.error("decoded APK path does not exist")
    findings = audit(args.decoded_apk)
    output = json.dumps({"untranslated_count": len(findings),
                         "strings": findings}, indent=2, ensure_ascii=False)
    print(output)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
