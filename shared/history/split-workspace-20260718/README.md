# Bili-monitor workspace hub

This directory contains two independent working trees:

- `bilibili数据监控-android/`: Android/Compose application.
- `bilibili数据监控-windows/`: Windows/Python/FastAPI application.

Do not place platform-private source, build output, runtime data, or releases in the other workspace. The shared history-exchange contract is mirrored in both workspaces and must be changed in the same iteration when its schema or vectors change. See `WORKSPACE_COORDINATION.md`.
