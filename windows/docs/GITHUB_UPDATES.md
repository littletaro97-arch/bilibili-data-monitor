# 电脑版 GitHub 更新约定与面板讨论

## 本次范围

从 `4b8b1cd` 干净基线创建 `codex/windows-github-updates`。仅源码、安装脚本和测试迭代，不打包、不安装、不推送或创建 Release。未改变 Android 更新机制、用户安装位置或真实配置。可对本次提交执行 `git revert` 回退。

设置页新增当前版本、手动检查、更新说明、发布页、校验后下载。没有自动查询或自动安装；下载完成后用户先退出监控，再手动运行安装向导。

更新源为现有 origin：`littletaro97-arch/bilibili-data-monitor`。2026-10-02 匿名 API 实测 HTTP 403（限流），匿名仓库网页 HTTP 404，目前不能确认公开可访问，不能宣称真实发布包下载已验收。若指定不同仓库，修改 `app/services/update_service.py` 的 `REPOSITORY` 后重新验证。程序无需用户 GitHub Token。

## 发布约定

仅 push 源码或 tag 不会形成更新。必须创建非 Draft、非 Prerelease 的 GitHub Release，并上传附件：

`BilibiliMonitor-v<三段版本>-installer.<修订号>-windows-x64-setup.exe`

例如 `BilibiliMonitor-v0.12.0-installer.1-windows-x64-setup.exe`，建议 tag 为 `windows-v0.12.0-installer.1`。该版本只是文档/测试示例，未发布。同仓库 Android Release 不会被识别为 Windows 更新。

1. 发布前更新 `app/version.py` 的 `APP_VERSION` 与 `INSTALLER_REVISION`。功能版提高三段版本，安装包修订提高修订号。设置页、历史导出与构建脚本共用此处。
2. 使用 `scripts/build-installer.ps1`，脚本将版本传入 ISCC，并生成对应路径/文件名；已有产物拒绝覆盖。直接编译 ISS 使用旧默认值，正式构建统一走脚本，不覆盖既有 0.11.1-installer.1。
3. 验收真实安装包的安装、退出后覆盖升级、目录/数据保留和卸载。保持 AppId `C3C19C03-7F8E-48E4-95F3-B497EB0C6AE6` 与每用户安装方式不变。
4. 上传到公开 Release，确认 GitHub API 附件 `digest` 为 `sha256:<64位摘要>`、大小准确且为 uploaded。缺少摘要时显示新版本，但禁止程序内下载，仍可查看发布页。
5. 用已安装旧版完成真实检查、下载、升级验收。最初不含更新入口的旧包需先手动安装一次含此功能的版本。

## 原安装目录与数据

明确配置 `UsePreviousAppDir=yes`：同一 Windows 用户且原安装记录存在时，向导默认沿用原目录；用户仍可主动改变。首次安装、便携版、换用户或记录丢失时不能识别原目录，会使用默认目录并允许选择。

冻结版数据仍在 `%LOCALAPPDATA%\BilibiliMonitor\runtime-data`，升级没有删除数据步骤。此次没有制作新包，“新版真实覆盖安装”留到下次获准打包时验收。

## 检查与下载边界

- 分页扫描发布列表，最多 1000 条，超过上限明确提示检查未完成；按安装包四段数字版本比较，避免 Android 版本号与 GitHub Latest 干扰。
- 忽略草稿、预发布、APK、源码 ZIP、异常命名及其他仓库的附件，不自动降级。
- 网络、403/429、404及格式错误明确提示，失败清除旧下载选择，不显示“已经最新”。
- 下载从指定仓库 HTTPS Release URL 开始，只允许 GitHub 与官方附件 CDN 重定向，保持证书验证。
- 流式下载限制 512 MiB，验证大小和 SHA-256 后才交给浏览器；失败清理 `.part`。缓存位于运行数据目录 `updates`，按摘要命名；浏览器最终保存位置由浏览器下载设置决定。
- 不执行下载的 EXE。摘要保障与 GitHub 元数据一致，不等价于独立代码签名；正式分发可后续考虑 Authenticode。

## 验证

完整 Windows 测试 `106 passed`，包括原生托盘及 24 项更新测试：数字版本/修订号比较、平台和预发布过滤、分页、API 错误、缺摘要、不可信来源/重定向、下载失败/摘要和大小不匹配、临时文件清理、设置页跳转/转义/附件下载，以及 AppId/原目录配置。

PowerShell 脚本语法检查无错误，没有执行打包。浏览器使用临时数据库与 MockTransport，实际点击检查，看到了版本、下载入口和说明；HTML 说明按文字显示。`evidence/20261002/settings-updates.png` 是模拟数据截图，不代表发布了 0.12.0。测试下载也是合成字节，没有执行真实 EXE。真实公开仓库查询/发布包下载受前述 403/404 限制，未验收。

## 自有面板判断

现阶段不必重写成原生 UI。若目标是桌面软件体验，推荐后续用 WebView2 窗口承载现有 FastAPI/HTML，复用图表和业务逻辑，同时保留浏览器与 LAN 入口。

收益：托盘唤回固定窗口，不反复开浏览器标签；统一关窗口到托盘与彻底退出、窗口恢复及位置记忆；不会另建一套 UI。它本身不会自动修复 HTTP、会话或导入认证等问题。

成本：WebView2 Runtime 依赖、GUI 主线程/服务生命周期协调、文件下载/导出、外链转默认浏览器和崩溃回退需独立验收。不能只加 WebView 就认为全部桌面行为已完成。

后续方案：可回退的窗口壳原型（如 pywebview edgechromium），只加载本机受控页面，不对外部网站暴露 Python 桥；关闭默认隐藏到托盘，退出关闭服务；验证图表、更新下载、导出与重启后再设为默认，保留“用浏览器打开”。本轮仅讨论，没有安装依赖或改造窗口。

参考：[GitHub Releases API](https://docs.github.com/en/rest/releases/releases#list-releases)、[Inno 原目录规则](https://jrsoftware.org/ishelp/topic_setup_usepreviousappdir.htm)、[pywebview Windows 引擎](https://pywebview.flowrl.com/guide/web_engine.html)、[窗口生命周期](https://pywebview.flowrl.com/guide/usage.html)。
