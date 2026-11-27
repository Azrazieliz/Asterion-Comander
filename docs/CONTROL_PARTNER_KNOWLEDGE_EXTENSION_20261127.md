# Signed partner knowledge extension

Preserves the original locked [v1 cross-app contract](CONTROL_CROSS_APP_API_V1.md).

## Backward-compatible capability knowledge extension (Control implementation, 2026-11-27)

The existing `asterion.v1.capabilities` response's `pack_version` and `actions` remain authoritative for the action inventory. A partner can optionally publish a bounded `knowledge` array of at most 40 entries. Each entry has exactly `category`, `id`, `description`. Categories are `mode`, `model`, `limit`, `known_issue`, `data_format`, and `owner_change`. IDs use the existing action identifier syntax, descriptions are declarative text up to 300 characters, and the total response remains capped at 8192 characters. Publish no credentials, private content, or instructions to execute anything.

Control displays live installed version and pack version, supported actions, available metadata and explicitly missing categories. Approval is not connectivity; only a fresh signed provider response establishes the observed pack. This extension does not grant any operation authority and is not evidence that every partner has implemented it. Partner owners still need to publish real versioned knowledge.
