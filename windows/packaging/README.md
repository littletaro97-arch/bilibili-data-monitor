# Windows 安装包

电脑版应用版本为 0.11.1，本次安装包独立编号为 `v0.11.1-installer.1`。
包含正式根目录当前 Windows 源码，不使用历史源码目录，也不沿用 Android 的版本号。

## 安装与数据

- Windows 10/11 x64，内置 Python 运行时，无需另装 Python。
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
已存在的正式输出会阻止构建；下一次发行需修改 `installer.iss` 的安装包编号、输出目录、文件名、
版本资源及脚本输出检查，保留稳定 AppId 以便识别升级。

中文翻译取自 [Kira 的 Inno Setup 简体中文翻译](https://github.com/kira-96/Inno-Setup-Chinese-Simplified-Translation)，
原始维护者信息保留在 `ChineseSimplified.isl` 文件头中。

## 验证

```powershell
$env:BILIBILI_MONITOR_DATA_DIR = Join-Path $env:TEMP 'bilibili-unit-tests'
python -m pytest -q
Remove-Item Env:\BILIBILI_MONITOR_DATA_DIR
python scripts\verify-installer.py releases\v0.11.1-installer.1\BilibiliMonitor-v0.11.1-installer.1-windows-x64-setup.exe
```

安装验证拒绝覆盖已注册的正式安装。它在临时中文路径中安装，用隔离的 `LOCALAPPDATA`
验证安装版默认路径，测试主页、设置、图表、报告、历史导出、配置保存、重复安装和卸载数据保留。
结束后卸载临时副本并移除其卸载注册信息，证据与模拟数据留在临时目录。
向导画面检查与自动化结果分开记录，不代表干净 Windows 虚拟机验收或实际网络采集验收。

## 回档

本次工作分支为 `codex/windows-installer`，修改前源码为 `a3d08f6`。
用 `git revert` 回退本次提交；不要使用 `reset --hard`。
卸载安装版后保留的数据可用于重新安装本版；不保证任意旧版本可读未来的数据库结构。
产物仅本地生成，未签名、未上传、未发布。
