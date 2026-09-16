# Bilibili-monitor migration plan

Status: source consolidation, platform reorganization, and user-authorized legacy cleanup completed on 2026-08-29; pending user runtime validation.

## Scope

This directory initially consolidated the four supplied workspaces without deleting or modifying any source file:

- `E:\bilibili数据监控`
- `E:\Bili-monitor`
- `C:\Users\LittleTaro\Desktop\课外项目\bilibili数据监控`
- `C:\Users\LittleTaro\Desktop\课外项目\bilibili数据监控-local-backups`

The formal desktop repository at `C:\Users\LittleTaro\Desktop\课外项目\bilibili数据监控` is the current source baseline (`v0.12.3`, commit `79d5d47fc5ad090ab1b12b963d1821624ffcfebe`).

## Target layout

- `android\`: Android source, Android-specific docs, Android releases, and Android history.
- `windows\`: Windows source, Windows-specific docs, current runtime data, Windows releases, and Windows history.
- Root Markdown files: cross-platform development docs, project governance, migration evidence, and version rules.
- `shared\`: shared data contracts, exchange schemas, test vectors, and shared historical material.
- Root `docs\`, `releases\`, and `versions\`: empty migration leftovers; root `history\` has no files and only two empty placeholder subdirectories. They are retained because this pass does not delete anything.
- `.git\`: one copy of the formal repository history; source repositories remain untouched.

## Deduplication rule

For every destination path, an existing identical SHA-256 file is reused. A differing file is never overwritten automatically. The canonical `v0.12.3` repository wins active-source conflicts; older or unique material is retained under the matching platform's `history\` or under `shared\history\`, with its source and snapshot identity recorded in the final manifest.

## Acceptance gates

1. All four source paths were present during migration verification; after the user's explicit confirmation that historical data is not needed, they were moved to the Windows Recycle Bin.
2. Active Android and Windows source files come from the canonical `v0.12.3` baseline.
3. The newest Windows database is copied without mutation and remains SQLite-valid.
4. Identical Android/Windows release records and duplicate backup snapshots appear only once in the target.
5. Destination file counts and SHA-256 hashes are checked after copying.
6. No runtime start, build, database migration, or device test is claimed as passed by this migration alone.
