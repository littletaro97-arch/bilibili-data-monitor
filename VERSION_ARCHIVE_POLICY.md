# 版本归档规则

本项目优先使用 Git commit、branch 和 tag 管理版本。

根目录 `versions/` 是迁移留下的空目录，不再放平台归档。Android 发布产物放在 `android/releases/`，Windows 发布记录放在 `windows/releases/`，整套历史材料放在各平台或 `shared/history/`。当前迁移基线使用 Git tag：

```text
pre-formal-dir-20260707
```

不要把运行日志、数据库、导出报告或缓存复制进版本归档。

