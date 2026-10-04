# Windows 0.13.0 · 安装包第 1 版

源代码提交：82a6c7b。正式安装包大小 50,944,394 字节，SHA-256 见 SHA256SUMS.txt。

提供自有窗口、主题与正式图标、通知点击返回、任务卡片导航与独立修改采集时间、本地封面缓存、轻量图表与目录动画、中文样本词提取、登录后断点评论/分段弹幕采集及原文留存标记。启动与局域网设置自动保存，运行状态生效时间在界面注明。

安装保持稳定 AppId / UsePreviousAppDir，默认沿用原安装位置；用户运行数据在本地用户目录中保留。关闭程序后再安装。评论与弹幕接口可能限流、隐藏或删除内容，接口遍历结束不保证完整历史。

自动检查：188 项源码测试及隔离安装验证通过。详细范围见 validation-result.json 和 SECURITY-AUDIT.md。未进行逐页向导人工检查，未配置数字签名。当前只发布 Windows 安装包，不改变 Android APK。

公开 Release：https://github.com/littletaro97-arch/bilibili-data-monitor/releases/tag/windows-v0.13.0-installer.1

public-update-validation.json 记录了实际旧安装版更新器对真实发布元数据的识别、无凭据公开下载与 SHA-256 验证。实测匿名 API 限流，不能将元数据代入验证宣称为匿名联网检查成功；用户可稍后检查或直接从发布页下载。
