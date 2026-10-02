# 电脑版卡片、主题与图标本地验收

基线 `acb3573`，本轮分支 `codex/windows-card-theme-icons`。仅本地源码/Git；没有推送、打标签、构建安装包或修改既有 Release。Android 未修改。

## 已实现

- 用户提供的透明图标用于页面品牌、favicon、更新模块、WinForms 窗口/任务栏及托盘。原件从桌面移到 `windows/design/branding/app-icon-original.png`；运行 PNG/ICO 在 `windows/app/assets/`。以后打包脚本收集运行资源并设置 EXE 图标，本轮未构建 EXE。
- 全部应用页面及新生成的独立 HTML 报告支持深浅色。首次跟随系统，右上角切换并在当前浏览器/窗口配置中保存；不同客户端独立选择。Plotly 图表、输入控件、状态提示和 Windows 标题栏同步适配。
- 移除右上角返回首页；左上角品牌仍可回首页，详情等页面保留内容区返回按钮。
- 参考用户 HTML 原型采用每任务一张卡，标识/数据/操作分区，时间简化显示且 title 保留原值；保留原有真实链接、操作接口和采集状态模型。其它设备访问位于任务列表之后。没有把原型演示数据写入用户数据库。
- running→绿色正常，paused/有效冷却→黄色中断，error→红色异常，stopped→灰色停止（回收站）；仅改变显示，不改任务状态含义。
- 普通页面文字支持选择复制，浏览器 Ctrl+A/C 验证通过。表单和 Plotly 图表交互保留，不把图形绘制层当作普通文字输入框。
- 封面代码修复：原详情在绘制后恢复图表偏好并执行 location.replace，存在二次导航闪烁路径。现在首页链接提前带偏好，直接进入详情时在 head 恢复；图片预加载并解码后显示，新封面先解码后替换，失败保留原封面，取消过期替换。
- Windows 通知点击接入现有托盘默认首页动作，点击后由独立线程唤回首页。适配固定 pystray 0.19.5 的 Windows 消息后端，并保留右键、超时等原行为。[Microsoft Shell_NotifyIcon 回调说明](https://learn.microsoft.com/zh-cn/windows/win32/api/shellapi/nf-shellapi-shell_notifyiconw)。

## 验证与边界

125 项 pytest 通过，启用真实 Windows 托盘测试：在真实图标消息循环分发通知点击事件，验证首页动作；超时不激活，右键仍委托原处理。主题接口验证本地 Host/Origin 边界与布尔输入，静态资源只开放允许的运行资源。

浏览器检查浅/深色卡片、更新模块、状态颜色、579 px 宽度无横向溢出、复制文字、深色图表实际 SVG 背景和封面解码。改变双轴指标后回首页，视频链接和实际详情 URL 已携带保存的指标，避免显示后再导航。

最终真实 Evergreen 窗口烟测通过：自定义 Icon 存在、加载、关闭到托盘、隐藏时停止业务刷新、恢复设置、重复启动激活与正常退出。实际用户数据窗口也检查深色标题栏和卡片首页。

真实通知点击试验 `--notification-test` 未观察到可点击的 Windows 弹出通知，等待超时；不能声称真实鼠标点击验收通过。已通过的是程序与真实 Win32 消息循环的事件路径。没有修改用户系统通知设置。手动验收：托盘“立即检测”完成后，点击 Windows 通知，应唤回首页。

## 临时运行与回档

原便携进程 PID 367548 通过 `/shutdown` 正常退出。启动前对关闭后的 SQLite 做一致性备份，并备份配置：`windows/history/runtime-snapshots/20261002-ui-before-acceptance/`（Git 忽略）。

本地验收版以 `D:\python\pythonw.exe -m app.main` 在正式 `windows/` 目录运行，沿用 `%LOCALAPPDATA%\BilibiliMonitor\runtime-data`；监听 `http://127.0.0.1:7860`。旧便携 EXE 未覆盖。后台采集按原任务设置继续。

本轮临时 UI 测试服务/数据位于独立 TEMP 目录，服务已退出；最终验收服务保留运行。退出后重新打开旧便携 EXE 可回到已发布界面；回退本轮源码使用 git revert，不重置用户数据。若以后重新启动源码验收版：

```powershell
cd E:\课外项目\Bilibili-monitor\windows
$env:BILIBILI_MONITOR_DATA_DIR = Join-Path $env:LOCALAPPDATA 'BilibiliMonitor\runtime-data'
pythonw -m app.main
```

真实通知试验失败证据：TEMP 下 `bilibili-native-panel-qop2esxv/result.json`。最终窗口烟测成功证据：`bilibili-native-panel-3f9fgmwu/result.json`。独立测试与用户验收数据没有混用。
