# Official Marketplace plugin API v1

This contract is for the external `www.wyocyberrange.com` service and the standalone LabTech client. The existing `/api/marketplace/packages/` endpoint remains for `.coursepkg` files. The Marketplace service implementation lives in its own repository; this document does not make the service available.

## Authorization

The client presents its signed license bearer token issued by the official licensing service. License renewal includes a per-installation `plugin_client_secret` in the HTTPS POST only when configured; the official server stores a hash and grants `plugins_marketplace_enabled=true` only when the current secret matches. The Marketplace verifies the token signature, machine binding, credential version, entitlement, and unexpired `exp` on **each** catalog and download request. A fingerprint header alone does not authorize access. Reject expired/revoked tokens with 403; do not offer a download during the standalone's 30-day runtime grace period. Limit response and archive sizes, use HTTPS, and never log tokens or secrets.

## Endpoints

- `GET /api/marketplace/plugins/`: JSON `{"schema_version":1,"releases":[<release metadata>]}`. An optional search query is display-only; authorization and compatibility do not depend on it.
- `GET /api/marketplace/plugins/{plugin_id}/releases/{release_id}/download/`: ZIP bytes, `Content-Type: application/zip`. IDs are ASCII slugs, not paths. A missing or retired release returns 404; an unauthorized caller gets 403. Metadata in the catalog and download refer to the same immutable release ID.

Release metadata keys, all mandatory: `schema_version` (integer 1), `plugin_id` (lowercase ASCII letter followed by up to 39 lowercase letters, digits or hyphens), `release_id` (1–120 ASCII letters/digits/underscore/hyphen, starting alphanumeric), `version` (normalized safe PEP 440 version), `contract_version` (integer 1), `core_min`, `core_max`, `python_min`, `python_max` (inclusive versions), `archive_sha256` (lowercase 64-character hex), `entry_point` (`python.module:function`), `capabilities` (subset of `health`, `validate_configuration`, `provision`, `launch`, `status`, `finish`), `outbound_destinations` (up to 32 HTTPS origins), and `signature` (base64 Ed25519 signature). Unsupported schema or protocol versions fail closed.

The publisher signs the UTF-8 JSON object **without** `signature`, serialized with `sort_keys=True`, `separators=(',', ':')`, and `ensure_ascii=False`. The public Ed25519 PEM is pinned by the standalone administrator as `PLUGIN_MARKETPLACE_PUBLIC_KEY`. `archive_sha256` binds the exact downloaded bytes to signed metadata. Rotate trust roots with a core update and explicit overlap window; never take a new root key from unsigned catalog content.

The ZIP contains exactly `manifest.json` and one or more files under `wheels/` ending in `.whl`. The manifest is a JSON object exactly equal to `{"plugin_id":...,"version":...,"entry_point":...}` in the signed metadata. Archive compressed size is at most 128 MiB, inflated declared size at most 512 MiB, member count at most 1000, manifest at most 64 KiB. Reject duplicate paths, symlinks, encrypted files, traversal, and unlisted entries. The privileged installer streams each member with a byte limit and verifies its hash while extracting into a new staging directory; it never runs archive-provided root scripts.

## Compatibility and rollout

Only publish artifacts built for the declared Python and connector protocol ranges. A release is visible with an incompatible marker when unsupported by the client but cannot install. The client may exercise this API against a local fixture until the real Marketplace server is developed and deployed; that is not an end-to-end licensing or Marketplace verification.
