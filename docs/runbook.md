# 运行与验证手册（Runbook）

更新时间：2026-02-16

## 1. 环境要求

- Windows 10/11 x64
- 使用项目内 `.venv`（不要混用 Conda）
- 已安装 VC++ 2015-2022 x64 运行库
- FFmpeg 放置在项目目录：
- `tools/ffmpeg/bin/ffmpeg.exe`
- `tools/ffmpeg/bin/ffprobe.exe`

## 2. 初始化（首次）

```powershell
powershell -ExecutionPolicy Bypass -File setup_venv.ps1
```

## 3. 启动应用

```powershell
.\.venv\Scripts\python.exe app\main.py
```

## 4. 快速验收流程

1. 选择视频库根目录。
2. 点击扫描，确认数据库文件已生成：
- `<库根目录>/.mm/library.db`
3. 打开“标签提取”窗口，执行一次任务。
4. 打开“候选标签评审”窗口：
- 验证可全选（全部候选）/反选/批量通过/批量不通过。
5. 打开任意视频详情：
- 验证标签以短按钮显示（约四字宽，超长省略）。

## 5. 日志检查

- 扫描日志目录：`<库根目录>/.mm/logs/`
- 标签提取日志目录：`<库根目录>/.mm/logs/`
- 关键事件建议关注：
- `rule_match_summary`
- `candidate_terms_detected`
- `candidate_summary`
- `tag_mining_summary`

## 6. 常见问题处理

1. `ImportError: DLL load failed while importing QtCore`
- 原因：环境混用或运行库缺失。
- 处理：
- 仅使用 `.venv` 启动
- 重新执行 `setup_venv.ps1`
- 确认 VC++ 运行库已安装

2. FFmpeg 报 `Invalid data found when processing input`
- 原因：视频文件损坏或容器头损坏。
- 处理：记录错误并跳过；必要时对源文件做修复或替换。

3. 临时目录删除失败（`WinError 32`）
- 原因：`library.db` 连接未关闭。
- 处理：在脚本退出前调用 `service.close()`。

## 7. 冒烟脚本

```powershell
.\.venv\Scripts\python.exe tools\smoke_tag_mining.py
```

