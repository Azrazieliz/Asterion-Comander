# Rounder → Asterion Control: recursive TeraBox inventory (2026-11-22)

**Scope:** Remote *metadata inventory only*. Existing Rounder and Control installations,
Windows worker, original phone pairing, signed APK identities, and native WSS are preserved.

## Verified existing connection

Asterion Control already implements `AppBridge.invoke / operation / capabilities`
on the signed Android phone, authenticated over its existing native WSS and Windows
worker. The private GitHub bridge is **only** the remote instruction/receipt transport.
No MCP gateway, OAuth tunnel, new pairing system, or file-downloading engine is added.

Rounder's `com.openlocal.office.asterion.bridge` provider implements:
- `asterion.v1.capabilities`: advertises `rounder.inventory.meta` and `rounder.inventory.page`.
- `asterion.v1.invoke`: performs an approved read-only inventory operation.
- `asterion.v1.status`: safely polls an existing request ID.
- `asterion.v1.cancel`: acknowledges the terminal read-only request; does not cancel the
  shared Rounder recursive search index or mutate cloud data.

## Consent and authorization

1. In **Asterion Control → Asterion app integrations → Manage app access**, approve
   the installed Rounder package `com.openlocal.office`. This stays on-device;
   network clients cannot approve it. Control pins Rounder's installed APK signer.
2. Open Rounder, connect the existing TeraBox account, choose the exact folder
   from the existing UI, then tap **Allow Control inventory (30 min)** in folder actions.
3. Rounder pins the existing original Control signer and Binder caller identity, and
   limits read access to the selected account and that folder's descendants. The
   selected folder must be present in the recursive metadata index.
4. Revoke any time from Rounder's same folder action sheet. Approval expires after
   30 minutes and automatically invalidates on TeraBox account change.

The process never transmits TeraBox cookies, stream URLs, arbitrary local
files or media bytes. File *names and paths* are private metadata and should
remain in owner-controlled Control/PC output—not public Git or logs.

## Direct supported operations

```json
{"package":"com.openlocal.office","action":"rounder.inventory.meta","request_id":"rounder-inventory-meta-unique123","payload":{}}
```

When the metadata scan has finished, use the returned
`generation`, `root`, and irreversible `account_fingerprint` to read pages:

```json
{"package":"com.openlocal.office","action":"rounder.inventory.page","request_id":"rounder-inventory-page-unique456","payload":{"generation":1,"after":"","format":"json"}}
```

Each page uses a fresh idempotency ID and returns an ordered `items` array,
`has_more`, and `next_after`. Call the next page using `after=next_after`
until `has_more=false`. Only completed generations are exported; disconnects,
account changes, revocation, and incomplete indexes fail closed.

CSV pages are also supported with `format=csv`. For efficient Windows exports,
the collector fetches JSON once and generates both representations locally.

## Windows collector — original Control worker

From the existing Control checkout/Python environment:

```powershell
python scripts/export_rounder_inventory_20261122.py --format both
```

The private export defaults to `D:\AsterionControl\exports\rounder\`
on the original Windows PC when that drive is present, otherwise the owner's
private `LOCALAPPDATA\AsterionControl\exports\rounder\` folder.

It invokes *only* existing authenticated `/app-bridge/invoke` and
`/app-bridge/operation` routes, assembles generation- and account-bound
JSON and CSV, validates every page, and stores durable checkpoints after
both staging writes. It can safely resume after a page boundary.

The Windows worker may execute this script as an already-authorized bounded
`pc_command` and return its short terminal summary through the existing
private GitHub bridge. **Do not upload the complete user inventory into the
public Rounder or Control repositories.** Specific entries or subtrees can
be examined privately by subsequent authorized worker queries.

## Release gates

- Rounder workflow `.github/workflows/openlocaloffice-build.yml` must compile
  the provider with the canonical original-signed Android production APK.
- Control collector source regression in
  `tests/test_rounder_inventory_collector_20261122.py` must pass.
- Final physical Samsung acceptance: Control recognizes Rounder after local
  approval; selected TeraBox subtree with nested files exports exactly once;
  compare file and folder counts and paths against Rounder's completed index;
  account change, revocation, permission expiry, Unicode names and loss of WSS
  are verified. A source commit or compiled APK is *not* device acceptance.
