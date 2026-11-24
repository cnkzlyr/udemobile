# Release hardening

Runtime network hardening uses `usesCleartextTraffic=false` and a Network
Security Configuration that permits cleartext only for the on-device ArkSigner
compatibility endpoint (`localhost` and `127.0.0.1`). WebView mixed content,
file/content URL access, geolocation, automatic media playback and unsafe custom
schemes are disabled. SSL errors are never bypassed. This reduces known attack
surface but is not a guarantee against every current or future vulnerability;
keep Android System WebView and app dependencies patched.

The normal `release` build uses R8 shrinking, optimization, identifier renaming and
resource shrinking. An optional second pass uses the Apache-2.0 `rufusin/Dex2C`
project to AOT-translate a small whitelist of pure Java helper methods into JNI/C++.
This is the closest audited open-source option in this project to a VM-style native
hardening layer; it is **not** PairIP, VMProtect or a complete virtual machine.

Dex2C is deliberately not downloaded or executed by Gradle. Pin and audit a commit,
install its Python/NDK/APKEditor prerequisites, configure `ndk_dir` in its `dcc.cfg`,
then run:

```sh
DEX2C_DIR=/opt/Dex2C GRADLE_CMD=gradle tools/harden-release-dex2c.sh
```

The whitelist is in `tools/dex2c-filter.txt`. Android lifecycle methods,
`@JavascriptInterface` methods, USB/card transport and vendor-library boundaries are
excluded because rewriting them can break reflection, WebView dispatch or ABI calls.
The produced APK must still be signed with the Play upload key and verified with
`apksigner`. Keep mapping files and native symbols privately for crash diagnosis.

