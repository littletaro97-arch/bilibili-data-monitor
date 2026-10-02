# B站数据监控

当前统一目录是一个项目根目录，下面分开维护 Windows 和 Android 两套客户端。目录职责以 [PROJECT_LAYOUT.md](PROJECT_LAYOUT.md) 为准。

## 目录职责

- `windows/`：Windows/Python/FastAPI 源码、测试、依赖、运行入口、运行数据、Windows 发布记录和 Windows 历史材料。
- `android/`：Android/Compose/Room 源码、Gradle 工程、Android 专属文档、APK 发布记录和 Android 历史材料。
- `shared/`：双端共用的数据结构、历史交换协议、测试向量和共享历史材料；不放平台私有源码。
- 根目录：只放双端共同开发文档、项目治理/迁移记录和入口说明。
- 根目录下的 `docs/`、`releases/`、`versions/` 不含文件；`history/` 也不含文件，只保留两个空的历史占位子目录。它们都是迁移留下的非活动目录。

## Windows

电脑版 EXE 安装包与构建说明见 [windows/packaging/README.md](windows/packaging/README.md)。
当前安装包在 `windows/releases/v0.11.1-installer.1/`，无需另装 Python，卸载保留用户数据。

2026-10-02 的电脑版源码迭代新增系统托盘和详情页封面展示；本轮未打包。
双端功能差异、数据安全检查与验收证据见 [windows/docs/DESKTOP_ITERATION_20261002.md](windows/docs/DESKTOP_ITERATION_20261002.md)。

```powershell
cd E:\课外项目\Bilibili-monitor\windows
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\run.bat
```

测试：

```powershell
cd E:\课外项目\Bilibili-monitor\windows
python -m pytest
```

Windows 运行数据位于 `windows/runtime-data/`：

- `config.toml`
- `data/bilibili_local.db`
- `logs/`
- `reports/`
- `exports/`

## Android

```powershell
cd E:\课外项目\Bilibili-monitor\android
.\gradlew.bat clean test lintDebug assembleDebug
```

中文正式路径下推荐使用：

```powershell
cd E:\课外项目\Bilibili-monitor\android
powershell -ExecutionPolicy Bypass -File .\scripts\build-ascii.ps1
```

脚本通过 ASCII junction 构建，并把 Debug APK 复制到 `android/releases/<版本>/`。

## 双端共享协议

Windows 设置页和 Android 设置页均可导入、导出 `bilibili-history-exchange` v1 ZIP。v1 只交换视频和统计快照；评论、弹幕、Cookie、Token、设备信息、日志和原始数据库不进入交换包。

详细规范见 `shared/history-exchange/HISTORY_EXCHANGE_SPEC.md`。

## 版本与安全

- Git commit、branch 和 tag 是源码回档依据。
- 不覆盖旧 APK、旧 Tag 或历史发布目录。
- `config.toml`、SQLite、运行日志、用户导出 ZIP、虚拟环境、Gradle 缓存、签名文件和设备信息不得提交。
- 当前采集仅使用公开数据范围，不处理登录 Cookie、验证码、代理池或风控绕过。
