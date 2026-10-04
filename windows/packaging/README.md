# Windows 安装包

当前电脑版应用版本为 0.13.0，安装包编号为 `v0.13.0-installer.1`，已于 2026-10-04 发布至公开 GitHub Release。
包含正式根目录当前 Windows 源码，不使用历史源码目录，也不沿用 Android 的版本号。

## 安装与数据

- Windows 10/11 x64，内置 Python 运行时，无需另装 Python。
- 自有窗口复用 WebView2 Evergreen Runtime，不附带浏览器内核；缺失时提示微软下载页并回退浏览器。
- 关闭窗口隐藏到托盘；隐藏/最小化时跳过面板数据刷新，后台采集继续。
- 当前用户安装，无管理员提权；默认 `%LOCALAPPDATA%\Programs\BilibiliMonitor`。
- 中文欢迎页、使用说明、目录选择、开始菜单、可选桌面快捷方式及完成后启动。
- Windows 应用列表和开始菜单均有卸载入口，交互卸载提示数据保留目录。
- 安装版数据固定在 `%LOCALAPPDATA%\BilibiliMonitor\runtime-data`，升级与卸载保留数据。
- 源码模式继续使用 `windows/runtime-data`。旧数据需通过历史交换 ZIP 手动导入。
- 包内只包含程序、依赖、模板与公开示例响应，不复制源码工作区的用户数据。
- 设置页“退出程序”可停止服务，包括隐藏启动模式。

## 构建

在 Python 3.13.5 x64 环境中安装 `windows/requirements.txt` 与 PyInstaller 6.18.0
（本次 hooks 为 2026.0）。本次完整工具环境版本见发布目录的 `build-environment.txt`。

```powershell
cd E:\课外项目\Bilibili-monitor\windows
.\scripts\build-installer.ps1
```

默认编译器为用户提供的 `E:\D-diskExpansionCabin\Inno Setup 6\ISCC.exe`，可以用 `-Iscc` 指定。
通过 PyInstaller onedir 打包后由 Inno Setup 压缩为一个安装 EXE。
已存在的输出会阻止构建；下一次发行统一更新 `app/version.py`，构建脚本将版本传给安装器。
保持稳定 AppId 和 `UsePreviousAppDir=yes`，同一 Windows 用户的升级默认沿用注册的原目录。
窗口依赖固定 pywebview 6.1 / pythonnet 3.0.5，避免构建时自动漂移到未经验证的桥接版本。

中文翻译取自 [Kira 的 Inno Setup 简体中文翻译](https://github.com/kira-96/Inno-Setup-Chinese-Simplified-Translation)，
原始维护者信息保留在 `ChineseSimplified.isl` 文件头中。

## 验证

```powershell
$env:BILIBILI_MONITOR_DATA_DIR = Join-Path $env:TEMP 'bilibili-unit-tests'
python -m pytest -q
Remove-Item Env:\BILIBILI_MONITOR_DATA_DIR
python scripts\verify-installer.py releases\v0.13.0-installer.1\BilibiliMonitor-v0.13.0-installer.1-windows-x64-setup.exe --expected-payload dist\BilibiliMonitor
```

安装验证拒绝覆盖已注册的正式安装。它在临时中文路径中安装，用隔离的 `LOCALAPPDATA`
验证安装版默认路径，测试主页、设置、图表、报告、历史导出、配置保存、重复安装和卸载数据保留。
结束后卸载临时副本并移除其卸载注册信息，证据与模拟数据留在临时目录。
向导画面检查与自动化结果分开记录，不代表干净 Windows 虚拟机验收或实际网络采集验收。

## 回档

本次工作分支为 `codex/windows-desktop-release`，修改前源码为 `10c2572`。
用 `git revert` 回退本次提交；不要使用 `reset --hard`。
卸载安装版后保留的数据可用于重新安装本版；不保证任意旧版本可读未来的数据库结构。
本次发布记录与敏感信息检查见 `windows/releases/v0.13.0-installer.1/`；0.12.0 的历史证据保持原目录。安装包未配置数字签名。

## 0.13.0 发布验证补充

当前机器已有正式安装，本次用独立测试 AppId、临时用户目录与同一已扫描载荷验证安装、原目录沿用和卸载数据保留，未覆盖真实安装，也未使用 Computer Use。源码 188 项测试通过。正式资产已从公开下载地址下载，大小和 SHA-256 校验通过。

从已安装 0.12.0 EXE 提取的实际更新器代码，使用 GitHub 返回的真实发布元数据成功识别 0.13.0.1，并完成无凭据的公开下载和校验。匿名 GitHub API 在实测时返回 403 / 剩余配额 0；元数据验证使用 gh 读取结果代入，不宣称匿名联网检查通过。遇限流可稍后再检查，或从发布页直接下载安装包。没有把 GitHub Token 放进源码或安装包。
