# Bilibili Video Data Monitor｜B站视频数据监控（Windows / Android）

一款用于 **Bilibili / 哔哩哔哩视频数据监控** 的本地工具，提供 **Windows 10/11 桌面客户端** 和 **Android 应用**。支持定期记录公开视频的播放量、点赞、投币、收藏等指标，查看历史趋势、保存统计快照并导出数据。

**English:** A local Bilibili video statistics monitor for **Windows desktop and Android**. Track views, likes, coins, favorites and other public video metrics; review historical trends, manage monitoring tasks, and export data. The Windows edition also supports creator-upload tracking and optional authenticated comment/danmaku collection.

> 数据由 Bilibili 接口按任务间隔采集；实际刷新受网络、平台限制和系统调度影响，不能保证毫秒级实时或完整历史数据。

## 下载与安装 / Download

| 平台 | 当前公开版本 | 安装方式 |
| --- | --- | --- |
| **Windows 10/11 x64** | **0.15.0** | [下载 Windows 安装包（GitHub Release）](https://github.com/littletaro97-arch/bilibili-data-monitor/releases/tag/windows-v0.15.0-installer.1)；无需自行安装 Python |
| **Android** | **0.12.3** | [下载 Android APK（GitHub Release）](https://github.com/littletaro97-arch/bilibili-data-monitor/releases/tag/v0.12.3)；当前发布的是 Debug APK |

Windows 安装版采用独立窗口（基于 WebView2）和系统托盘；需有 **Microsoft Edge WebView2 Evergreen Runtime**，缺失时提供安装提示并可使用浏览器界面。**Windows 安装包尚未进行 Authenticode 数字签名**，可使用对应 Release 的 `SHA256SUMS.txt` 核对安装文件。升级、卸载时按发布说明保留用户数据。

## 主要功能 / Features

| 功能 | Windows | Android |
| --- | --- | --- |
| 监控多个 BV 号、B站视频链接及公开视频的统计数据 | ✅ | ✅ |
| 播放量、点赞、投币、收藏等指标与本地历史快照 | ✅ | ✅ |
| 历史趋势图、单指标和双指标比值展示 | ✅ | ✅ |
| 定时检测与手动刷新 | ✅ 逐任务调度 | ✅ Android 后台调度约束 |
| 本地持久化与数据导出 | ✅ SQLite、CSV、HTML 报告 | ✅ Room / SQLite、JSON、CSV |
| Windows 系统托盘、独立窗口、关闭后后台监控 | ✅ | — |
| 自动发现所关注 UP 主的新投稿并添加监控任务 | ✅ | — |
| 用户扫码登录后采集可见评论、楼中楼和分 P 弹幕（支持断点续采） | ✅ | — |
| Android 通知提醒与后台状态提示 | — | ✅ |
| Windows ↔ Android 历史数据 ZIP 导入 / 导出 | ✅ | ✅ |

**Windows 0.15.0：** 评论和弹幕采集可随视频监控任务分批执行，并在中断后从已有进度续采；平台限流和网络故障时采用退避处理。具体功能与限制以[该版本发布说明](https://github.com/littletaro97-arch/bilibili-data-monitor/releases/tag/windows-v0.15.0-installer.1)为准。

**Android：** 定时采集可能受系统省电策略和后台限制影响，不保证严格准点或持续运行。桌面端和移动端的功能与版本独立迭代。

## 快速开始 / Quick start

### Windows（推荐：直接安装）

1. 打开 [Windows Release 页面](https://github.com/littletaro97-arch/bilibili-data-monitor/releases/tag/windows-v0.15.0-installer.1)，下载 `windows-x64-setup.exe` 安装附件。
2. 运行安装器并启动 Bilibili Monitor，在界面中添加 BV 号、视频链接；按需设置监控间隔。
3. 在详情页查看数据快照和趋势图。登录态仅在使用需要授权的采集功能时才需要。

开发者可从源码运行：

```powershell
cd windows
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\run.bat
```

运行测试：在 `windows/` 下执行 `python -m pytest`。安装版与源码运行模式使用不同的数据目录，参见 [Windows 打包与数据目录说明](windows/packaging/README.md)。

### Android（源码构建）

```powershell
cd android
.\gradlew.bat clean test lintDebug assembleDebug
```

若项目路径包含中文字符，可使用 `android/scripts/build-ascii.ps1` 处理 Gradle 在部分环境中的路径兼容问题。具体实现与版本说明见 [Android README](android/README.md)。

## 项目结构 / Repository structure

- `windows/`：Windows 桌面应用、Python / FastAPI、页面、采集器、测试与发布记录。
- `android/`：原生 Android 应用，Jetpack Compose / Room、Gradle 工程与 APK 发布记录。
- `shared/`：两端共享的历史交换协议、Schema 和测试数据。
- 根目录：双端共同文档、版本治理、迁移与调试记录。完整说明见 [PROJECT_LAYOUT.md](PROJECT_LAYOUT.md)。

## 历史数据交换

Windows 与 Android 均支持手动导入 / 导出 `bilibili-history-exchange` v1 ZIP，用于交换**视频和统计快照**。该格式不包含评论、弹幕、Cookie、Token、设备信息、日志或原始数据库；**目前不支持自动双端同步**。参见 [历史交换规范](shared/history-exchange/HISTORY_EXCHANGE_SPEC.md)。

## 采集边界与注意事项 / Limitations

- 仅处理符合访问条件的 Bilibili 公开视频数据。需要登录态的 Windows 功能使用用户主动扫码获取的授权信息，并将其保存在当前 Windows 用户环境下。
- 不支持绕过验证码、平台限流或权限控制；遇到异常响应和风控限制时暂停或冷却。接口遍历完成不代表获取到了全部历史评论或弹幕。
- 本项目以本地数据保存为主；数据库与交换 ZIP 的隐私、完整性和来源可信度存在明确边界，请勿将普通导出文件当作不可篡改证据。
- 各平台发布记录和旧版本保留，**Windows 与 Android 的版本号不要混用**。源码回档以 Git commit、branch 和 tag 为依据。
- 仓库目前未提供 `LICENSE` 文件；公开可读不自动授予代码再分发、修改发布的许可。

详细说明：[采集边界与合规](抓取边界与合规说明.md) · [版本管理](VERSIONING.md) · [Windows 更新机制](windows/docs/GITHUB_UPDATES.md) · [Windows 与 Android 功能差异](windows/docs/DESKTOP_ITERATION_20261002.md)
