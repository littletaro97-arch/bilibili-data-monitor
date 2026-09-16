# Bilibili-monitor migration manifest

Migration date: 2026-08-29

## Original source records

- `E:\bilibili数据监控`
- `E:\Bili-monitor`
- `C:\Users\LittleTaro\Desktop\课外项目\bilibili数据监控`
- `C:\Users\LittleTaro\Desktop\课外项目\bilibili数据监控-local-backups`

Before authorized cleanup, no file in the four source directories was deleted, moved, or overwritten. Files were moved only inside the target during the later platform reorganization.

## Active target selection

The active source is copied from the formal repository:

- Tag: `v0.12.3`
- Commit: `79d5d47fc5ad090ab1b12b963d1821624ffcfebe`
- Android: `android\` including `android\releases\` and `android\history\`
- Windows: `windows\` including `windows\releases\`, `windows\history\`, and `windows\runtime-data\`
- Cross-platform development material: root Markdown files
- Shared contracts and shared history: `shared\`
- One Git metadata tree: `.git\`

The active Windows runtime was copied from `E:\bilibili数据监控` into `windows\runtime-data\`:

- `config.toml`
- `data\bilibili_local.db`
- `logs\app.log`
- `logs\launcher.log`
- Empty runtime directories for `data\exports\` and `reports\output\`

The runtime database was copied byte-for-byte. Before this migration it reported SQLite `integrity_check=ok`, 3 tasks, 3 videos, and 2,215 snapshots; its `user_version` was 0 and may be migrated by the v0.12.3 application on first launch.

## Deduplication decisions

- The Android source in `E:\Bili-monitor\bilibili数据监控-android` was compared with the formal Android source. 87 files were identical; the two differing files were the standalone-workspace `README.md` and `scripts\build-ascii.ps1`. The formal repository copy is active; the standalone variants are retained under `android\history\split-workspace-20260718\`. The active build script was then path-adjusted for the new `android\releases\` location.
- Android release records: 60 files were identical. Only the formal copy is present at `android\releases\`.
- The Windows source in `E:\Bili-monitor\bilibili数据监控-windows` matched the formal source for all active source files except its standalone documentation variant. Only the formal copy is active; the variant is retained under `windows\history\split-workspace-20260718\`.
- Windows release records: 6 files were identical. Only the formal copy is present at `windows\releases\`.
- The two supplied copies of `pre-cleanup-20260809` and the two supplied copies of `pre-v0.11.0-20260711` were byte-identical backup sets. Each set is copied once under `windows\history\local-backups\`.
- The older combined v0.2.0 Android source is retained once under `android\history\legacy-combined-v0.2.0\`; its Windows source and documents are retained once under `windows\history\legacy-combined-v0.2.0\`, and its shared documents/contracts are retained once under `shared\history\legacy-combined-v0.2.0\`. Runtime data and caches were excluded from that source snapshot because the newest runtime data is active under `windows\runtime-data\`.

## Historical material retained

- `android\history\legacy-combined-v0.2.0\`: old combined Android source and Android documents/spec.
- `windows\history\legacy-combined-v0.2.0\`: old combined Windows source, Windows documents/spec, and Windows config/launcher.
- `shared\history\legacy-combined-v0.2.0\`: old shared documents, schema, scripts, and coordination files.
- `android\history\split-workspace-20260718\`: differing standalone Android documentation/build script and Android workspace metadata.
- `windows\history\split-workspace-20260718\`: standalone Windows documentation and workspace metadata.
- `shared\history\split-workspace-20260718\`: split-workspace coordination files.
- `windows\history\runtime-snapshots\split-runtime-data-20260718\`: older split workspace runtime snapshot.
- `windows\history\runtime-snapshots\combined-reference-runtime-20260718\`: separate reference runtime snapshot.
- `windows\history\local-backups\pre-v0.11.0-20260711\`
- `windows\history\local-backups\pre-cleanup-20260809\`

## Verification evidence

The following copy checks were completed immediately after the initial consolidation, before the target-only platform reorganization:

- Formal repository mirror: 332 files checked; missing 0; SHA-256 mismatches 0.
- Active runtime mirror: 4 files checked; SHA-256 mismatches 0.
- Historical runtime mirrors: 16 files checked; missing/mismatched 0.
- Legacy v0.2.0 mirror: 80 files checked; missing/mismatched 0.
- Split-workspace metadata: 11 files checked; missing/mismatched 0.
- All four source directories were present during the initial migration verification.

The target-only reorganization then moved Android releases and Android history under `android\`, Windows releases and Windows history under `windows\`, and cross-platform history under `shared\history\`. It did not overwrite files. The root placeholder directories `docs\`, `releases\`, and `versions\` are empty; root `history\` has no files and only two empty placeholder subdirectories. All are retained.

## Authorized legacy cleanup

On 2026-08-29, the user confirmed that historical data is not needed and authorized retaining only the consolidated program. The following original directories were sent to the Windows Recycle Bin, not permanently erased:

- `E:\bilibili数据监控`
- `E:\Bili-monitor`
- `C:\Users\LittleTaro\Desktop\课外项目\bilibili数据监控`
- `C:\Users\LittleTaro\Desktop\课外项目\bilibili数据监控-local-backups`

The target `E:\课外项目\Bilibili-monitor` was not included in this cleanup. The Recycle Bin has not been emptied, so the four directories remain recoverable until it is cleared.

## Runtime caution

`windows\runtime-data\config.toml` was preserved unchanged. Its source configuration has LAN access enabled, so review it before launching if the target should be local-only; the current v0.12.3 code will otherwise bind LAN mode according to that configuration.

The platform reorganization moved files only inside the target directory. The four source paths were removed only after the user's authorization above; root empty directories were not deleted. This manifest does not claim a Windows runtime start, Android build, emulator/device test, or production acceptance. Those remain separate user validation steps.

## Runtime observation after initial copy

During the post-reorganization read-only check, an active `pythonw.exe -m app.main` process was detected and the target log tail showed scheduled collection continuing through `2026-08-29 00:36:53`. The target database remained readable with `integrity_check=ok`, `user_version=1`, 3 videos, 2,267 `video_stats_snapshot` rows, 3 crawl tasks, and 432 crawl logs. Its current hash therefore differs from the initial copied baseline (which had `user_version=0` and 2,215 snapshots); this is runtime activity after the initial copy, not a reorganization overwrite. The process was not stopped and the runtime data was not replaced.
