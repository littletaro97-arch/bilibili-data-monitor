# Android workspace boundary

This is the standalone Android working tree. Run Gradle from this directory and publish Android artifacts only under `releases/`.

It contains a mirrored `shared/history-exchange/` contract. Do not add Windows source, Python environments, SQLite runtime data, or Windows release artifacts here. Any shared-contract change must be mirrored to `E:\Bili-monitor\bilibili数据监控-windows\shared\history-exchange` in the same iteration.

Historical damaged Android build data is retained only as `workspace-history/damaged-workspace-backup-20260717.tar` and is not source code.
