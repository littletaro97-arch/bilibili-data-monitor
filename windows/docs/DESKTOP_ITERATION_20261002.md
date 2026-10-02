# 电脑版源码迭代与双端检查（2026-10-02）

## 范围与回滚

正式仓库：`E:\课外项目\Bilibili-monitor`。开始时工作树干净，基线 `2476176`，独立分支 `codex/windows-tray-cover`。本轮只更新 Windows 源码、测试和检查记录，没有生成 EXE 安装包、更新包或 APK，没有发布。已安装的旧 EXE 不会自动获得这些功能。

本轮提交可通过 `git revert <本轮提交>` 回退；不要用 `reset --hard`。现有数据库结构无需迁移，封面使用已有 `videos.cover_url` 字段。本轮没有修改 Android 生产源码或用户真实数据库。

源码运行：在 `windows` 目录安装 `requirements.txt` 后使用现有 `run.bat`，或 `python -m app.main`。新增 Windows 依赖为 pystray、Pillow。

## 已实现

- Windows 系统托盘：占位图标；默认点击打开浏览器首页；右键打开面板、立即检测、进入设置、退出程序。托盘由服务进程持有，关闭浏览器不等于退出监控。退出走服务关闭流程并移除图标。
- 立即检测只针对运行中且不在冷却期的任务；遵守既有并发、请求间隔和风控策略。暂停、停止及错误状态不会被按钮自动恢复；连点及与自动检测重叠不会重复采集同一视频。完成后显示成功、失败、跳过数量。
- 视频详情加入 16:9 封面及标题、元信息布局；宽屏两列，窄屏单列。缺图/加载失败有占位提示。已有任务后续成功检测会补齐封面，页面刷新数据时更新图片。
- 仅显示 Bilibili/hdslb 可信域的 HTTP(S) 图片地址，并规范化为 HTTPS；拒绝凭据、异常端口、任意导入地址。图片由浏览器直接访问，使用 no-referrer，没有添加任意地址的服务端图片代理。

后续电脑版版本应保留封面采集、详情展示、缺图降级及响应式布局。下一次手机版迭代应处理 HTTP 封面规范化与详情封面缺失，当前仅记录差异。

## 封面先验测试与验收

开发前实测公开视频 `BV1GJ411x7h7` 的 VIEW 接口返回封面地址；原地址为 HTTP，另行验证其 HTTPS 地址 HTTP 200、1920×1080，证书验证启用。浏览器实际加载该图片后才开始实现。

- 完整 Windows 测试：`82 passed`，包括显式启用的 Windows 原生托盘测试。
- 原生托盘测试真实创建图标、检查可见与线程存活，执行实际菜单回调，再确认关闭后线程退出、图标不可见；浏览器启动用 mock 隔离。没有冒充人工鼠标左/右键点击验收。
- 真实 API/图片与浏览器显示验证通过。详情页面的统计数据使用临时合成数据；截图中的封面来自真实公开 CDN。
- 浏览器 1280 与 390 宽度均检查无横向溢出；390 宽度截图检查通过；无封面页面显示占位。宽屏检查包含 DOM 布局证据，不宣称截图中每个组件都已人工视觉验收。
- 测试使用临时数据目录；临时源码服务已通过退出接口正常关闭。Android 检查没有安装 APK 或进行手机实机验收。

证据：`evidence/20261002/detail-cover.png`、`cover-probe.json`、`windows-integrity-result.json`、`android-integrity-result.json`。

## 双端功能是否对齐：有差异

以下是当前源码能力差异，平台入口差异不自动视为缺陷，也不意味着本轮要全部对齐。

| 项目 | Windows | Android |
| --- | --- | --- |
| 指标 | 7 项常规指标及当前观看人数 | 7 项常规指标，没有当前观看人数 |
| 调度 | 每视频独立任务、秒级间隔、暂停/停止/错误/冷却、并发限制 | 全局分钟间隔、仅 Wi-Fi、前台/WorkManager/持续前台服务；没有等价的逐视频调度配置 |
| 通知与入口 | 本轮新增托盘及手动批量检测完成通知 | 刷新通知、汇总通知、权限与后台限制提示、持续通知和停止入口；普通刷新通知配置不同 |
| 删除与恢复 | 停止任务保留历史，可重新添加；支持按时间删除快照 | 回收站、恢复、永久删除视频及其快照；没有与 Windows 相同的任务状态模型 |
| 链接 | 文本/完整链接提取 BV，打开网页；不解析只有 b23.tv 的短链 | 支持 b23.tv 解析及客户端打开/网页回退 |
| 评论/弹幕 | 导入评论与弹幕、公开 XML 弹幕采集、词频/密度分析、HTML 报告；真实评论采集明确未启用 | 没有对应评论/弹幕分析与 HTML 报告 |
| 导出/导入 | 全库 CSV、单视频 CSV 历史导入、HTML 报告、v1 历史 ZIP | 单视频 JSON/CSV、文件选择与保存位置、系统分享、v1 历史 ZIP；没有同等全库 CSV/HTML/CSV 历史导入 |
| 图表 | Plotly 单指标、双轴及比值 | 单指标与比值、20/50/全部点数、降采样及偏好持久化；图表选项不一致 |
| 封面 | 本轮详情显示、HTTPS 规范化、浏览器缓存 | 列表缩略图及内存/磁盘缓存；详情未显示；HTTPS-only 策略会拒绝当前 API 返回的 HTTP 封面 |
| 历史来源身份 | 未保存 Android 的 originDeviceId/originSnapshotId，重新导出会丢失它们 | 保存来源设备/快照身份并用于去重 |
| 失败采集记录 | 失败记入任务/日志，不形成失败快照；历史导出按成功记录表达 | 保存失败状态/错误信息快照；经过 Windows 往返时失败语义不能完整保留 |

双方共有 v1 ZIP 手动结果交换，都没有自动局域网同步；不能将手动交换称为自动同步。

检查位置：Windows `collectors/provider.py`、`services/crawl_service.py`、`services/history_exchange_service.py`、`database.py`、`ui/pages.py`、`reports/templates`；Android `data/MonitorRepository.kt`、`data/HistoryExchange.kt`、`data/CoverUrlPolicy.kt`、`settings`、`worker` 以及 UI/导出实现。

## 明文与篡改检查

### 结论

双方本地数据库和导出内容没有应用层加密，具备相应文件写权限的人或程序可以篡改。网络获取统计指标使用 HTTPS，并启用客户端默认证书验证，不能因此称为网络明文传输；TLS 也不证明源站统计数值绝对真实。

| 路径 | 当前证据与边界 |
| --- | --- |
| Windows 本地 | 标准 sqlite3 数据库；JSON/CSV/HTML/ZIP 可读。临时数据库直接 SQL 改写后，Repository 读到了修改值。同一用户权限下的其他进程可能读写，不能推断任意远程用户都能直接改库。LAN 密码使用带盐 PBKDF2 哈希，不是明文密码。 |
| Android 本地 | 标准 Room/SQLite，没有 SQLCipher 或应用层字段加密。应用私有沙箱及系统设备加密提供保护，不等于具备应用层认证；普通其他 App 不能直接读取私有数据库，root、调试或获得相应权限者存在修改可能。未做手机实机改库测试。 |
| Android 备份 | Manifest 允许备份，未见专项排除规则；是否实际产生备份受系统/OEM 条件影响，未证实存在云端副本。需明确数据库及密钥的备份策略。 |
| 双端 ZIP | ZIP 内 JSON 是明文；SHA-256/checksums 无密钥，只能校验一致性。修改内容并重算摘要可以通过两端校验。 |
| API/封面 | 指标 API 使用 HTTPS，未发现关闭证书验证的实现。本轮 Windows 将可信 HTTP 封面升级 HTTPS；Android 拒绝原 HTTP 图片，导致缺图，并非已证实明文下载。 |
| Windows LAN 面板 | 启用 LAN 时绑定 0.0.0.0，HTTP 传输登录/会话和数据。现有会话值由密码哈希稳定推导，没有独立随机会话及过期管理；取得 Cookie 可重放，取得密码哈希可推导会话值。 |
| Windows 写操作 | 未见完整 Origin/CSRF/Host 校验，本机访问绕过 LAN 登录；存在跨站请求等入口风险，需要单独修复与验证。托盘操作直接调用服务，没有新增 HTTP 控制接口。 |

### 实证方法

`python -m scripts.probe_history_integrity` 仅创建临时合成数据，不访问真实数据库。原播放数 100，修改为 999999：

1. 不重算摘要：Windows、Android 都拒绝。
2. 重算 contentSha256 和 checksums：Windows、Android 都接受 999999。
3. Windows 临时库直接 SQL 修改：应用读取修改值，没有认证机制阻止或报警。

Android 证据来自 JVM 调用已有 v0.13.1 HistoryExchangeCodec 类；相关源码相对构建基线 `6e050fb` 没有变更。临时 Java harness 与两端 JSON 结果保存在证据目录。这证明当前交换校验不能防主动伪造，不代表手机实机/root/网络攻击已经测试。

### 解决方案与优先级

**必须处理（当使用 LAN 或要求数据可信时）**：LAN 面板配置 HTTPS，改为随机、可失效、有有效期的会话，补 Origin/CSRF/Host 校验与本地写操作保护；可信交换设计 v2，逐端生成密钥、签名导出并校验签名及受信设备。可使用设备级 Ed25519 签名；旧 v1 包标识为未认证数据，保持兼容并让用户确认，不能把摘要通过称为可信。密钥不可硬编码或跟数据一起导出。

**推荐（有保密需求时）**：Android Keystore、Windows DPAPI 保护本机密钥，结合 SQLCipher 或 AEAD 加密敏感数据库/导出。明确备份规则、加密导出及恢复流程。迁移前做一致性备份和恢复验证。公开统计数据若无保密要求，可以保留明文与系统访问保护，避免盲目增加密钥丢失和升级维护成本。加密与来源认证是两个目标，不能用加密替代签名。

**可选（需要审计/防回滚时）**：记录级签名/链、外部时间戳或远端检查点，以发现删除与旧库回滚；增加异常值提示。设备被完全控制且密钥可被调用时，本机方案仍有边界，第三方检查点才提供额外依据。

本轮按用户“检查并汇报”的范围只修正封面 HTTPS 展示路径，没有实施数据库加密、交换协议升级或 LAN 安全改造，也没有修改用户配置。

参考官方说明：[HTTPX 默认 TLS 校验](https://www.python-httpx.org/advanced/ssl/)、[Android 网络安全配置](https://developer.android.com/privacy-and-security/security-config)、[Android Auto Backup](https://developer.android.com/identity/data/autobackup)、[HMAC 密钥认证](https://docs.python.org/3/library/hmac.html)、[pystray 使用方式](https://pystray.readthedocs.io/en/latest/usage.html)。
