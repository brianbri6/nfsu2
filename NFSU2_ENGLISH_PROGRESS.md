# NFSU2 English APK localization — audit and continuation

## Current goal
Remove remaining Spanish from the Android interface and native diagnostics, patch **the upstream v0.14.9 APKs directly** (ARM64 and ARMv7), verify the result, and publish this fork's **v0.14.11 English** release. Original NFSU2 game data is not included.

## Findings confirmed from repository source
The previous translation missed: `RacingControlsView.java` accessibility label "Controles del juego"; Vulkan probe error strings in `gpu_probe.cpp` ("El paquete no ofrece…" and "Driver con funciones Vulkan incompletas"); "HLE pendiente / desde" from `guest_runtime.cpp`; D3D9 failure text and CPU/GPU texture/log labels from `d3d9_bridge.cpp`.

An additional functional bug was found: the previous direct APK patch changed the default language only. Existing installs retained the `language=Spanish` preference. The English source now uses preference key `language_english_v01411` with default `English UK`; the direct smali patch migrates both GameOptions getter and the language-picker's generated callback. Other languages may still be manually selected. The `language` option forwarded to the native game runtime is intentionally unchanged.

## Changes committed to main
- Android launcher, touch controls, settings, graphics cache, diagnostics, and previously untranslated Java UI localized.
- New fixes applied to `RacingControlsView.java`, `gpu_probe.cpp`, `guest_runtime.cpp`, and `d3d9_bridge.cpp`.
- Language preference reset for legacy Spanish users, without breaking the language picker.
- `localization/en-us.json`: UI and additional diagnostic translation source of truth.
- `localization/native-en-us.json`: byte-length-checked compiled ELF string replacements.
- `scripts/patch_nfsu2_apk_english.py`: direct APK patcher for smali, XML resources, and native ELF text. ELF replacements are NUL-padded to preserve offsets. Applies fork update/report links and language-default migration.
- `scripts/audit_nfsu2_apk_english.py`: post-patch Spanish detector for DEX const strings, XML text and app-owned native libraries. Unknown Spanish text blocks publication.
- `scripts/tests/test_apk_localization.py`: synthetic regression tests for migration, native byte sizes, smali patching and scan failures, plus source-literal audit.
- `.github/workflows/nfsu2-english-apk-release.yml`: checks test suite, pins apktool checksum, patches *both original APKs*, writes audit JSON, bumps to v0.14.11 (versionCode 26), aligns, signs, verifies and publishes only when previous steps pass. Audit reports are uploaded as artifacts.
- `android/app/build.gradle`: v0.14.11, versionCode 26.

## Verification done / not done
**Verified:** GitHub connector returned successful commits for all updated source/scripts/workflow files; file contents were refetched after update, including new v0.14.11 metadata.

**NOT verified:** No actual upstream APK binary was successfully retrieved into this chat's working container; direct smali/ELF patching and running on a phone are not tested here. The GitHub Actions pipeline is configured to perform those checks, but its completion and an uploaded APK release have **not** been confirmed. Do not claim a release asset exists until the Actions run succeeds.

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
