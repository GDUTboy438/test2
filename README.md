# 便携式视频管理器（PySide6）

一个 Windows 桌面视频库管理工具，核心目标是离线、可携带、便于后续扩展。

## 当前功能

1. SQLite 存储：数据库位于 `<库根目录>/.mm/library.db`。
2. 增量扫描：新增/更新/缺失标记，不删除历史数据。
3. 目录结构视图：左侧目录树 + 右侧文件区（列表/网格切换）。
4. 检索能力：搜索、状态筛选、格式筛选、时长筛选、日期筛选、排序。
5. 播放能力：双击或按钮调用系统默认播放器打开视频。
6. FFmpeg 接入：获取元数据（时长/分辨率/编码等）并生成缩略图。
7. 扫描日志模块：主界面可打开日志窗口，查看扫描、元数据提取、缩略图生成结果。

## 项目结构

```text
app/
  main.py
  application/        # 用例层（服务、端口、模型）
  core/               # 核心扫描逻辑
  infrastructure/     # SQLite仓储、FFmpeg索引、扫描日志、文件打开
  ui/                 # 主窗口与日志窗口
docs/
  database_schema.md
  ffmpeg_setup.md
```

## 运行

1. 初始化虚拟环境（仅首次）：

```powershell
powershell -ExecutionPolicy Bypass -File setup_venv.ps1
```

2. 启动应用：

```powershell
.\.venv\Scripts\python.exe app\main.py
```

## FFmpeg 本地化

推荐把二进制放在项目目录，不依赖系统环境变量：

```text
tools/ffmpeg/bin/ffmpeg.exe
tools/ffmpeg/bin/ffprobe.exe
```

详情见 `docs/ffmpeg_setup.md`。

## 扫描日志

日志文件位置：

```text
<库根目录>/.mm/logs/scan_YYYYMMDD_HHMMSS.jsonl
```

日志事件包含：

1. `scan_start`
2. `file_discovered`
3. `media_probe_ok` / `media_probe_error`
4. `thumb_ok` / `thumb_error`
5. `scan_summary`

## 打包

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

如需打包后仍可用 FFmpeg 功能，请保持 `tools/ffmpeg/bin` 在发布目录中。
