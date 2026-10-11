# Maintained Watchtower release and rollback

Changes by rzp-labs, 2026-10-11. GNU AGPL version 3; see LICENSE and NOTICE.md.

## Preparation

The reviewed compatibility source is `91cbfc46737bca36e59b4f6749541f9e5910d9fd`, based on upstream `35eb0518d33e710612beb88f29678900841dd33d`. Release commits preserve that ancestry. Run the offline UI tests including real MUI/theme fixtures using an existing consuming-app dependency installation, plus `python3 -m unittest discover -s tests -p test_packaging.py` and `node --check librarymanager.js`. Independently review any license, packaging, CI or release-source delta before publishing.

`python3 scripts/package_plugin.py --ref <reviewed-release-sha> --output dist` packages only allowlisted committed plugin code/assets/notices. It rejects dirty tracked changes, runtime/private selected-tree files, symlinks and incomplete packages. Identical Git source yields byte-identical stored ZIP entries. Build twice and compare bytes. Verify every packaged file hash against SOURCE-PROVENANCE.json and verify archive sha256 against index.yml/SHA256SUMS.

The manual Verify plugin package workflow creates artifacts only; it never tags, publishes or deploys. Its standalone Node checks skip real MUI tests without an existing consuming-app installation; those tests are a required local release gate and their results must be recorded separately.

## One coordinated publication

After independent review and parent coordination, publish exactly one versioned release tag `v<librarymanager.yml version>` at the reviewed release SHA with librarymanager.zip, index.yml, SOURCE-PROVENANCE.json and SHA256SUMS. GitHub's source archives at that tag supply corresponding source. The stable feed is `https://github.com/rzp-labs/watchtower/releases/latest/download/index.yml`; its package URL names the immutable versioned release. Never replace versioned assets. Re-download the release artifacts and verify source SHA/tree and package digest before installing.

## Reversible installed-feed switch

The package ID remains `librarymanager`. Before any installed mutation, save a private backup of the current installed code/manifest and plugin-source configuration, and take a consistent SQLite backup of Watchtower's database. Keep private backups on the existing host outside the plugin discovery path with restricted permissions. Do not upload private data into source, packages, public release artifacts or evidence logs. The initial current-known installed backup is rollback-only until a verified versioned prior artifact is available.

Add the maintained feed using the existing installation's source local_path so installation updates the current directory. Keep other sources/configuration unchanged; remove only the Watchtower upstream source when it exclusively serves Watchtower, otherwise retain it for its other packages. Do not uninstall first: the package installer replaces only manifest-listed code files, preserving database/history/runtime files and plugin settings. If the standard installer would trigger unapproved dependency changes, use a reviewed manifest-safe replacement of the verified package in the same directory and retain the maintained source receipt; do not bypass an approval denial.

Verify installed version/sourceURL, all package file hashes, database integrity and unchanged plugin settings. Reload plugin definitions only if safe; do not open UI flows that auto-start the watcher, change plugin settings, run tasks, rename/move/scan media, or deploy an app image. Restoration must put back only prior manifest-listed code/manifest and prior source configuration, retaining current database/history files. Restore a database snapshot only if proven necessary and after checking for writes since backup.
