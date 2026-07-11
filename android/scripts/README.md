# scripts

本目录用于未来放置项目维护脚本，例如：

- 数据导出检查
- schema 校验
- 发布前检查
- 文档检查

## Android 构建脚本

`build-ascii.ps1` 用于固定 Android 测试、打包和 APK 复制流程。

```powershell
powershell -ExecutionPolicy Bypass -File .\android\scripts\build-ascii.ps1
```

脚本会检查或创建：

```text
C:\Users\LittleTaro\codex-bilibili-monitor-ascii
```

该 junction 指向正式项目目录，用来规避 Windows 中文路径下 Gradle/JDK worker `@argfile` 可能导致的 Android unit-test classpath 问题。

脚本不提交 APK，不提交 `android/local.properties`、`.gradle/`、`build/`、签名密钥、`config.toml`、`data/` 或 `logs/`。
