# Portable Video Manager - 项目状态

更新时间：2026-02-16

## 1. 当前架构

- 技术栈：`PySide6 + SQLite + FFmpeg`
- 存储位置：`<视频库根目录>/.mm/library.db`
- 日志位置：`<视频库根目录>/.mm/logs/`
- 缩略图：由 FFmpeg 生成并索引到数据库
- 标签系统：
- 标签库（`tags`）独立存在，不依赖视频是否存在
- 视频标签关系（`video_tags`）区分 `manual` 与 `ai_title`
- 候选标签审核（`tag_candidates` + `tag_candidate_hits`）

## 2. 已完成能力（可用）

- 视频库选择、增量扫描（新增/更新/缺失标记）
- 目录树 + 文件区浏览（支持结构化显示，不是平铺）
- 视频元数据入库（时长、分辨率、编码等）
- 缩略图生成与展示（FFmpeg）
- 扫描日志 UI、标签提取日志 UI
- 标签提取任务（后台线程、进度条、可停止）
- 标签库 UI（新增、导入、删除、批量删除）
- 候选标签独立评审 UI（全量瓷砖展示、搜索、全选/反选、通过/不通过）
- 视频详情页标签增删（标签短按钮显示，超长省略）

## 3. 标签提取当前策略（已落地）

- 范围：
- `all`：全部视频
- `new_only`：仅未提取过的视频（基于 `videos.title_tag_mined_epoch`）
- 规则优先：
- 先用“标题字符命中标签库”直接打标
- 命中后该视频仍继续进入后续提取流程
- 模型/词项阶段：
- 继续提取候选词
- 白名单（标签库）内词直接入关系
- 白名单外词进入候选池，需审核后回写
- 清除 AI 标签：
- 仅删除 `video_tags(source='ai_title')`
- 不删除 `tags` 标签库条目

## 4. 关键模块

- 启动：`app/main.py`
- 主窗口：`app/ui/main_window.py`
- 标签提取窗口：`app/ui/tag_mining_window.py`
- 候选评审窗口：`app/ui/tag_candidate_review_window.py`
- 视频详情：`app/ui/video_detail_window.py`
- 应用服务：`app/application/library_service.py`
- 标签提取服务：`app/application/tag_mining_service.py`
- SQLite 仓储：`app/infrastructure/library_repository.py`

## 5. 已知风险/注意事项

- 运行环境必须使用同一个 `.venv`，避免 Conda 与 venv 混用导致 PySide6 DLL 问题。
- 某些损坏视频会导致 FFmpeg 报 `Invalid data found when processing input`，这是源文件问题，不是程序崩溃。
- 临时目录测试时，必须在退出前显式 `service.close()`，否则 Windows 可能锁住 `library.db`。

