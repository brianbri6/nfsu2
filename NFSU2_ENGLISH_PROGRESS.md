# NFSU2 English localization progress

## Goal
Translate all user-visible Android launcher and control menus into English, then patch the original upstream Android v0.14.9 APKs directly and publish a new release on brianbri6/nfsu2.

## Source changes completed
- English translations committed for LauncherActivity, GameActivity, GameOptions, RacingControlsView, GpuDrivers, GpuProbeActivity, GraphicsCache, Diagnostics, ReleaseUpdates.
- Translated native Vulkan driver diagnostics and game-launch status messages in gpu_probe.cpp and main.cpp.
- English UK is the new default game language preference. Other game language files remain selectable.
- Update and issue-report links target this fork, not the upstream maintainer's repository.
- Android Gradle version bumped to 0.14.10, versionCode 25.
- Localization reference: localization/en-us.json (190 string mappings).

## Direct APK patch implementation
- scripts/patch_nfsu2_apk_english.py patches smali string constants in decoded upstream APKs, sets the default game language to English UK, redirects update links to this fork, and applies length-limited native message replacements in ELF libraries.
- .github/workflows/nfsu2-english-apk-release.yml downloads original v0.14.9 ARM64 and armeabi-v7a APKs, decodes with apktool, patches the APKs directly (no rebuilding game/native code), changes version metadata, reassembles, aligns, signs, verifies signatures and publishes v0.14.10.
- Workflow runs on a change to its own file or manual workflow_dispatch.

## Validation, limits, and known risks
- GitHub source updates confirmed by connector commit responses; remaining Java string literals audited for accented Spanish and none detected in nine main UI classes.
- The source has NOT been compiled and no APK has been smoke-tested on an Android device here.
- This session cannot retrieve the upstream APK into the working container or use a GitHub release-upload API. The GitHub Actions workflow must run before release artifacts exist. A successful release has NOT yet been verified.
- The APKs cannot be installed over the upstream publisher's APK because the original signing key is unavailable. If no NFSU2_SIGNING_* secrets are provided, GitHub Actions generates a temporary signing key; later runs will not share that signature.
- A full in-game translation depends on the PC game LANGUAGES/English.bin and is separate from translating the Android app.

## Next steps
1. Open this fork's Actions tab; if Actions are disabled on the fork, enable workflows.
2. Run the "NFSU2 English APK Release" workflow manually if it did not trigger automatically.
3. Check its logs and confirm both APK files and SHA256SUMS.txt appear under GitHub Releases v0.14.10.
4. Test launcher, graphics-driver prompts, touch layouts, and gameplay on an Android device. Back up game saves before replacing an upstream-signed installation.
5. Configure stable NFSU2_SIGNING_KEYSTORE_BASE64, NFSU2_SIGNING_STORE_PASSWORD, NFSU2_SIGNING_KEY_PASSWORD, and NFSU2_SIGNING_KEY_ALIAS secrets before subsequent patch releases.

## Build commands
Source build (requires full Android SDK/NDK, lifted game source, and upstream build dependencies):
```sh
cd android
./gradlew assembleDebug
```
APK binary patch and release: GitHub Actions -> NFSU2 English APK Release -> Run workflow.
