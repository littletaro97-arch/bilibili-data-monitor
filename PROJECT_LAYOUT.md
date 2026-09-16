# 当前目录布局

本文档是 `E:\课外项目\Bilibili-monitor` 的当前目录职责说明。迁移完成后，活动文件按平台隔离；历史材料仍保留，但不参与默认构建和运行。

## 根目录：双端共同开发材料

根目录直接保留以下内容：

- `README.md`、`PROJECT_LAYOUT.md`、`PROJECT_OVERVIEW.md`：项目入口和目录说明。
- `版本迭代记录.md`、`当前项目审计报告.md`、`开发任务清单.md`：双端共同的版本、审计和任务记录。
- `实机测试记录.md`、`debug记录.md`：跨平台测试与排错记录；具体平台的历史附件仍在对应平台目录。
- `数据结构说明.md`、`抓取边界与合规说明.md`：双端共同的数据和合规边界。
- `VERSIONING.md`、`VERSION_ARCHIVE_POLICY.md`：版本和归档规则。
- `MIGRATION_PLAN.md`、`MIGRATION_MANIFEST.md`、`MIGRATION_LOG.md`：本次迁移的计划、证据和日志。
- `.git/`、`.gitignore`：统一项目的 Git 元数据和忽略规则。

`shared/` 也位于根目录，但它不是平台源码，而是双端共用的数据契约、交换协议、Schema、测试向量和共享历史材料。

## Android：Android 专属内容

`android/` 内的所有活动内容都属于 Android：

- Gradle 工程、`app/`、构建脚本和 Android README。
- `android_control_client_codex_spec.md`：Android 实现规格。
- `docs/`：Android 专属说明，例如封面显示排查和 Android 端规划。
- `releases/`：Android 各版本 APK、构建信息、变更记录和测试报告。
- `history/`：Android 旧工作区、旧合并工程和历史材料。

## Windows：Windows 专属内容

`windows/` 内的所有活动和历史内容都属于 Windows：

- `app/`、`tests/`、`requirements.txt`、`config.example.toml`、`run.bat`：Windows 应用和入口。
- `runtime-data/`：当前 Windows 配置、SQLite 数据库、日志、导出和报告；属于运行数据，不是源码。
- `bilibili_local_analytics_codex_spec.md`：Windows 实现规格。
- `docs/`：Windows 专属说明。
- `releases/`：Windows 各版本发布记录。
- `history/`：旧合并工程、旧拆分工作区、旧运行快照、本地备份和根入口兼容脚本。

## 没有活动文件的旧目录

根目录下的 `docs/`、`releases/`、`versions/` 当前为空；`history/` 当前不含文件，只保留 `legacy-combined-v0.2.0/` 和 `split-workspace-20260718/` 两个空的历史占位子目录。它们是迁移过程中保留的非活动目录；本次按“先不删除历史内容”的要求不删除它们，也不把新文件放回去。后续验证通过后，如需清理空目录，可以单独处理。

## 使用边界

- Windows 从 `windows/run.bat` 启动，运行数据只认 `windows/runtime-data/`。
- Android 从 `android/` 执行 Gradle，APK 只输出到 `android/releases/`。
- 双端共用协议和开发文档放在根目录或 `shared/`；不得把平台私有源码放回根目录。
- `android/history/`、`windows/history/` 和 `shared/history/` 下的内容只用于追溯，不是当前构建输入。
