# NFSU2 English APK localization — audit and continuation

## Top-left startup diagnostic overlay fix — v0.14.12
- Root cause: `GameActivity.setStatus()` only schedules the overlay dismissal on substring `Starting CRT entry point`, but the native worker reports `Ejecutando entrada CRT del juego…` (translated in the direct English APK to `Starting game CRT entry…`), so the condition is never true.
- Source: updated `GameActivity.java` to match `Starting game CRT entry` and dismiss the transient diagnostic overlay after **5 seconds**, preserving the original persistent diagnostic behavior on genuine errors.
- Source native worker: `guest_boot_worker.h` startup statuses translated to English to match the UI.
- Direct APK: `scripts/patch_nfsu2_apk_english.py` modifies the original `GameActivity.smali` startup substring test and `postDelayed` constant from 8000 to 5000 milliseconds. It asserts both changes occurred exactly once; a mismatch fails publication.
- Tests: two smali regression tests validate the matching literal, 5000-ms delay, and preservation of unrelated timers.
- Gradle metadata: versionName 0.14.12 / versionCode 27; GitHub Actions builds both Android ABIs based on upstream v0.14.9.
- Build run (initial): https://github.com/brianbri6/nfsu2/actions/runs/39766154795 — check run completion and release assets before declaring success.
- Note: the top-left `PopupWindow` is an Android diagnostic/status overlay, not the gameplay HUD or touch controls. The fix should not disable error reporting or other overlays.
- Device testing outstanding: startup on a phone plus forced startup error after the five-second timer to ensure the error remains visible. Re-signing via CI may require uninstall due to nonstable signer; back up saves first.


## Verified GitHub Actions run — 2026-10-22

- Run: https://github.com/brianbri6/nfsu2/actions/runs/39727031835 — **SUCCESS**.
- Latest release: https://github.com/brianbri6/nfsu2/releases/tag/v0.14.11 (both ARM64 and armeabi-v7a APKs uploaded).
- Fixed previously broken smali Unicode-escape matching (the regex looked for double backslashes, but apktool used single backslashes). This was the main reason Spanish menu labels remained.
- Fixed false-positive Spanish detection caused by treating arbitrary ELF machine-code bytes as UTF-8 text.
- Translated all remaining known Android app and driver archive prompts, including mixed Spanish-English text in touch layout dialogs.
- Fixed native string replacements to space-pad rather than NUL-pad substrings embedded in JSON messages; NUL would truncate the diagnostics.
- Actual APK jobs (both ABI variants): 245 smali replacements, 17 native replacements, English language default verified and preference setter migration verified, **0 untranslated Spanish findings reported** in the patch audit.
- Both signed with APK Signature Scheme v3; signing and zipalign checks completed. The workflow uses an ephemeral signing key unless stable NFSU2_SIGNING_* secrets are configured, so upgrade compatibility is **not guaranteed**.
- ARM64 APK SHA-256: `79ba6929005fa4a7247750c3a2c1ce474422d194425c1fc85f73e36640a0f402`
- ARMv7 APK SHA-256: `d855e152c020818b0268e0a0fdaf7f9465980b12852a4923e872be6a81946a55`
- Not yet verified on a physical Android device: visual inspection of every launcher/overlay dialog and in-game content. The original PC game's language files are outside the APK; for English game menus the user must supply `LANGUAGES/English.bin`.


## Current goal
Remove remaining Spanish from the Android interface and native diagnostics, patch **the upstream v0.14.9 APKs directly** (ARM64 and ARMv7), verify the result, and publish this fork's **v0.14.11 English** release. Original NFSU2 game data is not included.

## Findings confirmed from repository source
The previous translation missed: `RacingControlsView.java` accessibility label "Controles del juego"; Vulkan probe error strings in `gpu_probe.cpp` ("El paquete no ofrece…" and "Driver con funciones Vulkan incompletas"); "HLE pendiente / desde" from `guest_runtime.cpp`; D3D9 failure text and CPU/GPU texture/log labels from `d3d9_bridge.cpp`; and the user-visible `Descargas/NFSU2` report path in `Diagnostics.java`.

An additional functional bug was found: the previous direct APK patch changed the default language only. Existing installs retained the `language=Spanish` preference. The English source now uses preference key `language_english_v01411` with default `English UK`; the direct smali patch migrates both GameOptions getter and the language-picker's generated callback. Other languages may still be manually selected. The `language` option forwarded to the native game runtime is intentionally unchanged.

## Changes committed to main
- Android launcher, touch controls, settings, graphics cache, diagnostics, and previously untranslated Java UI localized.
- New fixes applied to `RacingControlsView.java`, `gpu_probe.cpp`, `guest_runtime.cpp`, and `d3d9_bridge.cpp`.
- Language preference reset for legacy Spanish users, without breaking the language picker.
- `localization/en-us.json`: UI and additional diagnostic translation source of truth.
- `localization/native-en-us.json`: byte-length-checked compiled ELF string replacements.
- `scripts/patch_nfsu2_apk_english.py`: direct APK patcher for smali, XML resources, and native ELF text. ELF replacements are NUL-padded to preserve offsets. Applies fork update/report links and language-default migration.
- `scripts/audit_nfsu2_apk_english.py`: post-patch Spanish detector for DEX const strings, XML text and app-owned native libraries. Unknown Spanish text blocks publication. Audits also scan layout XML attributes, app-owned text assets and Unicode-escaped strings.
- `scripts/tests/test_apk_localization.py`: synthetic regression tests for migration, native byte sizes, smali patching and scan failures, plus source-literal audit.
- `.github/workflows/nfsu2-english-apk-release.yml`: runs regression tests, pins apktool checksum, captures **before and after** Spanish inventories, patches *both original APKs*, writes JSON audits, bumps to v0.14.11 (versionCode 26), aligns, signs, verifies and publishes only when previous steps pass. Audit reports are preserved as Actions artifacts and included with the release.
- `android/app/build.gradle`: v0.14.11, versionCode 26.

## Verification done / not done
**Verified:** GitHub connector returned successful commits for all updated source/scripts/workflow files; file contents were refetched after update, including new v0.14.11 metadata.

**APK packaging now verified through GitHub Actions** (see successful run above). No local on-device visual test has been performed here.

**Potential blockers:** A future APK may introduce unexpected user-facing strings, changed smali method structure, or incompatible resources. The strict audit or preference migration assertion intentionally fails the job rather than silently publishing an incomplete translation. Inspect the job's audit artifact and logs if it fails. The source/game runtime is not rebuilt by the APK workflow.

**Signing:** Original upstream signing private key is not available. Unless the maintainer configures the four `NFSU2_SIGNING_*` secrets, CI uses a run-specific test signing key, incompatible with upstream and later differently signed builds. Back up saves; uninstall old APK before installing.

## Next actions
1. In https://github.com/brianbri6/nfsu2/actions/workflows/nfsu2-english-apk-release.yml, enable/run the workflow if necessary.
2. Confirm `python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v`, APK decode, patch, post-patch audit, signing and verification all pass for both architectures.
3. Ensure v0.14.11 assets plus `audit-arm64.json`, `audit-armeabi-v7a.json` and `SHA256SUMS.txt` exist at https://github.com/brianbri6/nfsu2/releases .
4. Test phone UI with a clean install and optionally a legacy saved Spanish preference (if compatible signing key is available).
5. For English **in-game** menus supply a legitimate copy of `LANGUAGES/English.bin`; the APK cannot translate external commercial game language resources.

## Reproduce without compiling game code
```bash
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v
java -jar apktool.jar d -f NFSU2-AndroidEvolved-v0.14.9-arm64.apk -o decoded-arm64
python3 scripts/patch_nfsu2_apk_english.py decoded-arm64 --translations localization/en-us.json --native-translations localization/native-en-us.json --audit-report audit-arm64.json
python3 scripts/audit_nfsu2_apk_english.py decoded-arm64
java -jar apktool.jar b decoded-arm64 -o rebuilt-arm64.apk
# Then zipalign, sign, and verify with Android SDK build-tools as in the workflow.
```
