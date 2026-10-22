#!/usr/bin/env python3
"""Synthetic regression tests: APK locale patcher does not require game data."""
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
from patch_nfsu2_apk_english import patch_smali, patch_native, LANGUAGE_KEY
from audit_nfsu2_apk_english import audit, suspect

class EnglishPatchTests(unittest.TestCase):
    def stat(self):
        return {k: 0 for k in (
            "smali_strings", "preference_fields", "english_defaults",
            "preference_getters", "preference_setters"
        )}

    def test_game_language_pref_default_and_legacy_key(self):
        smali = '''
.field static final LANGUAGE:Ljava/lang/String; = "language"
.method static language(Landroid/content/Context;)Ljava/lang/String;
    .locals 2
    const-string v0, "language"
    const-string v1, "Spanish"
    return-object v1
.end method
'''
        stats = self.stat()
        result = patch_smali(smali, "GameOptions.smali", {}, stats, set())
        self.assertIn(f'LANGUAGE:Ljava/lang/String; = "{LANGUAGE_KEY}"', result)
        self.assertIn(f'const-string v0, "{LANGUAGE_KEY}"', result)
        self.assertIn('const-string v1, "English UK"', result)
        self.assertEqual(stats["english_defaults"], 1)
        self.assertEqual(stats["preference_getters"], 1)

    def test_launcher_lambda_uses_new_key_but_native_option_key_stays(self):
        smali = '''
.method private chooseLanguage()V
    .locals 2
    const-string v0, "Language"
.end method
.method private synthetic lambda$chooseLanguage$7(Landroid/content/DialogInterface;I)V
    .locals 2
    const-string v0, "language"
    return-void
.end method
'''
        stats = self.stat()
        result = patch_smali(smali, "LauncherActivity.smali", {}, stats, set())
        self.assertIn(f'const-string v0, "{LANGUAGE_KEY}"', result)
        self.assertEqual(stats["preference_setters"], 1)
        other = patch_smali('const-string v0, "language"\n',
                            "GameActivity.smali", {}, self.stat(), set())
        self.assertEqual(other, 'const-string v0, "language"\n')

    def test_smali_string_translation_preserves_identifiers(self):
        txt = 'const-string v1, "Controles del juego"\nconst-string v2, "driverLoadFailed"\n'
        stats = self.stat()
        result = patch_smali(txt, "RacingControlsView.smali",
                             {"Controles del juego": "Game controls"}, stats, set())
        self.assertIn('"Game controls"', result)
        self.assertIn('"driverLoadFailed"', result)
        self.assertEqual(stats["smali_strings"], 1)

    def test_native_rewrites_do_not_change_elf_size(self):
        old = "Driver con funciones Vulkan incompletas"
        target = "Missing required Vulkan functions"
        data = b'\x7fELF\x00' + old.encode() + b'\x00other text\x00'
        result, count = patch_native(data, {old: target}, set())
        self.assertEqual(len(data), len(result))
        self.assertEqual(count, 1)
        self.assertIn(target.encode() + b'\x00', result)
        self.assertNotIn(old.encode(), result)

    def test_auditor_catches_untranslated_smali_xml_native(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            s = root / "smali/com/nfsu2/test.smali"
            s.parent.mkdir(parents=True)
            s.write_text('const-string v0, "Controles del juego"\n')
            x = root / "res/values/strings.xml"
            x.parent.mkdir(parents=True)
            x.write_text('<resources><string name="action">No se pudo cargar el juego</string></resources>')
            layout = root / "res/layout/prompt.xml"
            layout.parent.mkdir(parents=True)
            layout.write_text('<TextView xmlns:android="http://schemas.android.com/apk/res/android" android:text="Guardar"/>')
            asset = root / "assets/help.txt"
            asset.parent.mkdir(parents=True)
            asset.write_text("Pulsa JUGAR para continuar", encoding="utf-8")
            n = root / "lib/arm64-v8a/libnfsu2_android.so"
            n.parent.mkdir(parents=True)
            n.write_bytes(b'\x7fELF\x00Driver con funciones Vulkan incompletas\x00')
            findings = audit(root)
            self.assertEqual({f["surface"] for f in findings}, {"smali", "xml", "asset", "native"})

    def test_existing_source_no_spanish_prompts(self):
        java = ROOT / "android/app/src/main/java/com/nfsu2/androidevolved"
        cpp = ROOT / "android/app/src/main/cpp"
        paths = list(java.glob("*.java")) + list(cpp.glob("*.cpp"))
        self.assertGreaterEqual(len(paths), 10)
        found = []
        for path in paths:
            content = path.read_text(encoding="utf-8")
            for match in re.finditer(r'"(?:\\.|[^"\\])*"', content):
                literal = match.group()[1:-1]
                if suspect(literal):
                    found.append(f"{path.name}:{content.count(chr(10), 0, match.start())+1} {literal[:100]}")
        self.assertEqual(found, [], "\n".join(found))

    def test_unicode_escaped_spanish_is_detected(self):
        self.assertTrue(suspect(r"Configuraci\u00f3n"))
        self.assertFalse(suspect("GPU driver initialization failed"))

    def test_native_replacements_are_byte_length_safe(self):
        pairs = json.loads((ROOT / "localization/native-en-us.json").read_text())
        for original, translated in pairs.items():
            self.assertLessEqual(len(translated.encode("utf-8")), len(original.encode("utf-8")), original)


if __name__ == "__main__":
    unittest.main()
