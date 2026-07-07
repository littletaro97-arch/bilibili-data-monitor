# Windows端说明

## 启动

```powershell
python -m app.main
```

或双击：

```text
run.bat
```

默认地址：

```text
http://127.0.0.1:7860
```

## 测试

```powershell
python -m pytest
```

## 当前不调整源码位置

现有 Windows 端源码仍位于项目根的 `app/`。不要为了目录整齐立即移动到 `windows/app/`，否则需要同步修改：

- `app/config.py`
- 启动命令
- 测试导入路径
- 数据库路径
- 报告输出路径
- `run.bat`

这类移动应单独作为 `v0.2.x` 路径重构任务处理。

