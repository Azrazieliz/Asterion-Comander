# Asterion Control v0.9.1 — release build

This is the real Android **release build type**, not an assembleDebug APK.
It is non-debuggable, optimized with R8, resource-shrunk, zipaligned,
and signed by the exact original key required to update v0.8.6/0.8.8/0.9.0
without deleting app data.

The signing certificate originally belongs to the installed debug-era
application. Android requires that certificate for in-place upgrades; using
a new "release key" without key rotation would make the update fail.
The legacy certificate is protected in an encrypted GitHub Actions secret.

Artifacts:
- dist/Asterion-Control-v0.9.1-release.apk — actual release APK.
- dist/latest-release.json — canonical release update metadata.
- dist/latest.json — legacy updater compatibility only: same signed
  release APK bytes mirrored under the historical `-debug.apk` filename
  demanded by older installed Control versions.

No separate debug-variant APK is published by this workflow. Users updating
from v0.8.8 or v0.9.0 can retain all existing pairing, data, permissions and
settings, subject to the normal Android installer confirmation.

Source tests and release signature checks are automated. Android physical
installation, microphone operation, and cellular relay operation still
require real device receipts; APK packaging alone does not prove these.
