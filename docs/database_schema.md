# 数据库结构设计（SQLite）

## 1. 目标

本项目将视频库元数据从 `library.json` 迁移为 SQLite，数据库文件固定在：

- `<库根目录>/.mm/library.db`

设计目标：

1. 保留当前 MVP 行为：相对路径、增量扫描、`missing` 软删除。
2. 支撑后续功能：FFmpeg 元信息、缩略图缓存、智能/手动标签、保存视图。
3. 保持可演进：应用层使用仓储接口，存储实现可独立演进。

## 2. 运行配置

仓储初始化时使用以下 SQLite 配置：

- `PRAGMA foreign_keys = ON`
- `PRAGMA journal_mode = WAL`
- `PRAGMA synchronous = NORMAL`
- `PRAGMA busy_timeout = 5000`

说明：允许生成 `-wal/-shm` 文件以换取更好的并发读写性能。

## 3. 表结构

### 3.1 `meta`

保存库级别元信息。

- `key TEXT PRIMARY KEY`
- `value TEXT NOT NULL`

当前键：

- `version`
- `root_id`
- `created_at`
- `updated_at`

### 3.2 `videos`

视频主表（核心业务表）。

- `id TEXT PRIMARY KEY`
- `rel_path TEXT NOT NULL UNIQUE`
- `filename TEXT NOT NULL`
- `ext TEXT NOT NULL`
- `size_bytes INTEGER NOT NULL`
- `mtime_epoch INTEGER NOT NULL`
- `added_at_epoch INTEGER NOT NULL`
- `last_seen_epoch INTEGER NOT NULL`
- `missing INTEGER NOT NULL DEFAULT 0`
- `missing_since_epoch INTEGER`
- `title_guess TEXT NOT NULL`
- `status TEXT NOT NULL DEFAULT ''`
- `notes TEXT NOT NULL DEFAULT ''`
- `created_at_epoch INTEGER NOT NULL`
- `updated_at_epoch INTEGER NOT NULL`

说明：

- `missing` 采用软删除语义，不物理删除历史视频记录。
- `missing_since_epoch` 记录开始缺失时间。

### 3.3 `video_media`

视频技术元信息（FFmpeg/ffprobe 扩展位）。

- `video_id TEXT PRIMARY KEY`
- `duration_ms INTEGER`
- `width INTEGER`
- `height INTEGER`
- `fps REAL`
- `video_codec TEXT`
- `audio_codec TEXT`
- `bitrate_kbps INTEGER`
- `audio_channels INTEGER`
- `media_created_epoch INTEGER`
- `probe_epoch INTEGER`
- `probe_status TEXT`
- `probe_error TEXT`
- `extra_json TEXT`
- `FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE`

### 3.4 `thumbnails`

缩略图缓存状态。

- `video_id TEXT PRIMARY KEY`
- `thumb_rel_path TEXT`
- `width INTEGER`
- `height INTEGER`
- `frame_ms INTEGER`
- `source_mtime_epoch INTEGER`
- `generated_epoch INTEGER`
- `generator TEXT`
- `status TEXT`
- `error_msg TEXT`
- `FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE`

建议缩略图文件路径：`<库根>/.mm/thumbs/...`

### 3.5 `tags`

标签字典表。

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `name TEXT NOT NULL UNIQUE COLLATE NOCASE`
- `color TEXT`
- `description TEXT`

### 3.6 `video_tags`

视频-标签关联表，支持来源区分（手动/AI）。

- `video_id TEXT NOT NULL`
- `tag_id INTEGER NOT NULL`
- `source TEXT NOT NULL`
- `confidence REAL`
- `created_at_epoch INTEGER NOT NULL`
- `updated_at_epoch INTEGER NOT NULL`
- `PRIMARY KEY(video_id, tag_id, source)`
- `FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE`
- `FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE`

### 3.7 `saved_views`

保存筛选/排序/列配置（数据库视图能力）。

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `name TEXT NOT NULL UNIQUE`
- `filter_json TEXT NOT NULL`
- `sort_json TEXT NOT NULL`
- `columns_json TEXT NOT NULL`
- `created_at_epoch INTEGER NOT NULL`
- `updated_at_epoch INTEGER NOT NULL`

## 4. 索引设计

- `idx_videos_filename` on `videos(filename)`
- `idx_videos_mtime` on `videos(mtime_epoch)`
- `idx_videos_missing_seen` on `videos(missing, last_seen_epoch)`
- `idx_video_media_duration` on `video_media(duration_ms)`
- `idx_video_media_resolution` on `video_media(width, height)`
- `idx_video_tags_tag_source` on `video_tags(tag_id, source)`
- `idx_thumbnails_status_epoch` on `thumbnails(status, generated_epoch)`

## 5. 当前扫描写入策略（SQL 原生事务）

当前版本已切换为 SQL 原生写入，不再通过内存 `videos` 全量中转后再保存。

流程如下：

1. 扫描文件系统，收集本次文件快照（`rel_path/filename/ext/size/mtime`）。
2. 在单事务中将快照写入临时表 `scan_input`。
3. 计算统计：
   - `added`：`scan_input` 中不存在于 `videos` 的记录数
   - `updated`：同路径下 `size/mtime` 发生变化的记录数
   - `seen`：本次扫描命中的记录数
4. 数据写入：
   - 新文件：插入 `videos`（生成 `id`，初始化默认字段）
   - 已存在文件：更新 `filename/ext/size/mtime/last_seen/missing`
   - 未命中文件：标记 `missing=1`，并维护 `missing_since_epoch`
5. 更新 `meta.updated_at`

事务语义：一次扫描写入为一个事务，保证一致性。

随后应用层会对“新增或内容变化”的视频触发媒体索引流程：

1. 调用 `ffprobe` 写入 `video_media`（时长、分辨率、编码、创建时间等）。
2. 调用 `ffmpeg` 生成缩略图并写入 `thumbnails`。
3. 即使 FFmpeg 不可用，也会写入 `probe_status/status='error'` 与错误信息，保证后续可诊断。

备注：标签同步逻辑仍独立于扫描流程；当前仅自动维护 `source='manual'` 的标签映射，不覆盖其他来源标签（如 AI）。

## 6. 未来扩展建议

### 6.1 FFmpeg 元信息任务

- 后台任务写 `video_media`
- 基于 `mtime` 与 `probe_epoch` 判断是否重探测
- `probe_status` 用于区分 `ok/error/pending`

### 6.2 缩略图任务

- 后台任务写 `thumbnails`
- `source_mtime_epoch` 用于判断缩略图是否失效
- UI 优先读取 `thumb_rel_path`，没有则回退系统缩略图

### 6.3 标签系统

- 手动标签：`source='manual'`
- AI 标签：`source='ai'`，可填 `confidence`
- 前端展示可聚合 `tags` 名称，不暴露内部 source 细节

### 6.4 保存视图

- `saved_views.filter_json` 保存筛选条件（标签、时长、分辨率、状态等）
- `saved_views.sort_json` 保存排序配置
- `saved_views.columns_json` 保存表格列可见性与宽度

## 7. 兼容性说明

- 当前不自动迁移旧 `library.json`。
- 新库在首次选择目录后初始化数据库结构。
- 首次扫描后将形成完整视频数据。
