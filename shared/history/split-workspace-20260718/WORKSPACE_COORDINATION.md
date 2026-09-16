# Dual-platform coordination

## Boundaries

- Android source, Gradle metadata, Android release records, and Android build archives belong only in `bilibili数据监控-android/`.
- Windows source, Python dependencies, runtime data, Windows release records, and Windows local backups belong only in `bilibili数据监控-windows/`.
- Neither workspace imports or runs code from the other.

## Shared contract

Both workspaces contain `shared/history-exchange/`. It is a mirrored data-contract copy, not a shared source directory. When changing its specification, schema, or test vectors:

1. Make the identical change in both workspaces in the same iteration.
2. Run each platform's own tests.
3. Compare the two contract trees before committing or releasing.

The split baseline was derived from dual-platform source commit `79d5d47fc5ad090ab1b12b963d1821624ffcfebe` on 2026-07-18. The former combined tree at `E:\bilibili数据监控-android` is reference-only and must not be used for new work.
