# 发布前敏感信息检查

检查对象：正式仓库 Git 全历史/当前改动、实际 PyInstaller 打包目录、冻结 EXE 的 Python 归档常量、安装后的文件清单。只发布验证通过的最终根目录安装包，不发布本地 attempt 产物。

方法：使用官方 gitleaks 8.30.1，下载包通过官方 SHA-256 清单校验；日志及报告启用完整脱敏。对冻结 EXE 使用 PyInstaller CArchiveReader/PYZ 读取器提取全部模块字符串常量到私有临时目录，再扫描；解包内容不上传。

结果：未发现实际 API Key、GitHub Token、应用私钥或用户密码凭据。扫描工具的结果并非数学上保证不存在所有未知形式敏感数据。

- 功能代码完成后全历史扫描覆盖 69 个提交约 1.34 MB，未发现实际凭据；发布文档提交后、推送前再复扫全部历史。
- 打包目录没有 config.toml、业务 SQLite 数据库、运行日志或 .env；没有打包用户运行目录。依赖中的 certifi/cacert.pem 是公开 CA 证书，不是私钥。
- 先前 Plotly widgetbundle.js 的 generic-api-key 命中实际是 `this.keys,er=this.bboxes` JavaScript 表达式，不是密钥；该 Notebook 组件未使用，最终包已移除以减小体积。
- 冻结模块常量扫描仅有第三方 `packaging.licenses._spdx` 许可证表候选，内容为相邻的 HIDAPI、hippocratic-2.1 SPDX 标识，不是凭据。没有设置整文件或通用密钥规则忽略来掩盖它；按人工核实记录为误报。
- 安装验证逐文件比对安装内容与扫描过的打包目录哈希；额外文件只允许 Inno 卸载程序/数据和安装说明。业务数据库由首次运行在独立用户目录生成。
- 没有捆绑 msedge.exe/chrome.exe 或 Fixed Version Runtime；仅包含 WebView2 SDK/Loader 和窗口桥接依赖。

源码中的公共 API URL、匿名请求头、公开演示视频/图片、版本号不是用户密钥。本轮不引入 Bilibili 登录 Cookie 或 GitHub 认证 Token 到应用；更新检查使用公开 API。

安全范围：本次检查防止把开发凭据或用户数据放入公开产物，未实施此前讨论的数据库加密、签名历史交换或 LAN HTTPS/会话全面改造。安装包 SHA-256 用于一致性检查，不等于发布者代码签名。
