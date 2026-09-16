# Windows端说明

## 当前源码位置

Windows 端源码位于本独立工作区根目录的 `app/`。不要将 Android Gradle 工程、APK 或 Android 构建缓存复制到这里。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

没有 `.venv` 时，`run.bat` 会回退到系统 Python。

## 启动

推荐命令：

```powershell
python -m app.main
```

或双击：

```text
run.bat
```

默认本机地址：

```text
http://127.0.0.1:7860
```

## LAN 配置

默认应保持：

```toml
[app]
host = "127.0.0.1"

[lan]
enabled = false
```

只有用户明确启用 LAN 且设置访问密码后，程序才会监听 `0.0.0.0`。启动日志会显示当前绑定地址；如果 LAN 开启，会输出风险提示。

本机调试时不要开启 LAN。公共 Wi-Fi、公司网络、不可信路由器环境下不要开启 LAN。

## 启动失败排查

1. 运行 `python -m app.main`，优先看控制台报错。
2. 如果端口占用，运行：

```powershell
netstat -ano | findstr :7860
```

3. 如果通过 `run.bat` 启动且窗口被隐藏，查看：

```text
runtime-data/logs/launcher.log
runtime-data/logs/app.log
```

4. 如果 LAN 已开启但无法访问，确认：

- `config.toml` 中 `[lan].enabled = true`
- 已设置访问密码
- 程序已重启
- 防火墙允许本机 7860 端口
- 手机和电脑在同一可信局域网

## 测试

```powershell
python -m pytest
```

当前测试使用 mock 响应和临时 SQLite，不依赖真实 B 站网络请求。
