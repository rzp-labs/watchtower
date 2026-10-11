# Watchtower provenance and modifications

Upstream project: https://github.com/kmarsh2311/watchtower
Upstream base: 35eb0518d33e710612beb88f29678900841dd33d (v1.0.18)

The upstream README at that revision identifies AGPL-3.0 in its license badge. This maintained fork retains that declaration and supplies the unmodified GNU Affero General Public License version 3 text in LICENSE. Existing upstream history, author attribution and bundled third-party license notices are retained. This notice does not claim that upstream supplied a missing license file or a further clarification.

Modified by rzp-labs, 2026-10-11:
- Support Watchtower's consumed UI controls on MUI-only hosts, preserving Bootstrap hosts.
- Preserve the host theme and component lifetime for filename correction through a React portal.
- Add offline compatibility/theme regression coverage.
- Add versioned, reproducible plugin packaging and source provenance.
- Discover and validate persistent PythonTools dependencies within Watchtower processes, with offline failure and replacement regressions.
- Include the canonical AGPLv3 license text and this dated modification notice.

The reviewed UI compatibility source is 91cbfc46737bca36e59b4f6749541f9e5910d9fd. The release records its complete source commit/tree separately. Dependency discovery changes only Watchtower process imports; media operation behavior is unchanged. Bundled watchdog and Roboto retain their separate license files in vendor-licenses/.

Maintained modifications are released under GNU AGPL version 3. Corresponding source and modification history are available at https://github.com/rzp-labs/watchtower and at each versioned release tag. No upstream copyright owner or grant text has been invented.
