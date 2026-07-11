# B站数据监控

本仓库在同一根目录内维护两个彼此隔离的客户端，以及一套只包含数据契约的共享历史交换规范。

## 目录

- `windows/`：Windows/Python/FastAPI 应用、测试、依赖和运行入口。
- `android/`：Android/Compose/Room 应用和 Gradle 工程。
- `shared/history-exchange/`：双端历史交换格式 v1、JSON Schema 和测试向量；不放平台私有源码。
- `releases/windows/`、`releases/android/`：按平台和版本归档发布记录。
- `docs/`：仓库级总览、版本、迁移和测试记录。

## Windows

```powershell
cd windows
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\run.bat
```

也可以从仓库根目录运行兼容入口 `run.bat`。业务入口只有 `windows/run.bat`；根入口只负责转发。

测试：

```powershell
cd windows
python -m pytest
```

Windows 运行数据位于 `windows/runtime-data/`：

- `config.toml`
- `data/bilibili_local.db`
- `logs/`
- `reports/`
- `exports/`

首次运行会在新位置不存在时复制旧根目录 `config.toml`、`data/`、`logs/`、`reports/`，校验后继续使用新位置；不会删除或覆盖旧数据。

## Android

```powershell
cd android
.\gradlew.bat clean test lintDebug assembleDebug
```

中文正式路径下推荐使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\android\scripts\build-ascii.ps1
```

脚本通过 ASCII junction 构建，并把 Debug APK 复制到对应 `releases/android/<版本>/`。

## 历史交换

Windows 设置页和 Android 设置页均可导入、导出 `bilibili-history-exchange` v1 ZIP。v1 只交换视频和统计快照；评论、弹幕、Cookie、Token、设备信息、日志和原始数据库不进入交换包。

交换采用合并导入：完全重复记录跳过，身份相同但内容不同的记录报告冲突且不覆盖。详细规范见 `shared/history-exchange/HISTORY_EXCHANGE_SPEC.md`。

## 版本与安全

- Git commit、branch 和 tag 是源码回档依据。
- 不覆盖旧 APK、旧 Tag 或历史发布目录。
- `config.toml`、SQLite、运行日志、用户导出 ZIP、虚拟环境、Gradle 缓存、签名文件和设备信息不得提交。
- 当前采集仅使用公开数据范围，不处理登录 Cookie、验证码、代理池或风控绕过。
