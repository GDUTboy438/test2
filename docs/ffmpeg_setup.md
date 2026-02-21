# FFmpeg 本地化部署说明

本项目支持把 FFmpeg 放在项目目录，不依赖 Windows 全局环境变量。

## 1. 推荐目录结构

在项目根目录放置：

```text
tools/
  ffmpeg/
    bin/
      ffmpeg.exe
      ffprobe.exe
```

`FfmpegMediaIndexer` 会优先使用上面路径；找不到时才回退到系统 `PATH`。

## 2. 获取方式

1. 下载 Windows x64 版 FFmpeg（包含 `ffmpeg.exe`、`ffprobe.exe`）。
2. 解压后把两个可执行文件复制到 `tools/ffmpeg/bin/`。

## 3. 运行时行为

1. 若找到 FFmpeg：扫描后会写入时长、分辨率、编码信息，并生成 `.mm/thumbs/*.jpg`。
2. 若未找到 FFmpeg：扫描不会中断，但 `video_media`/`thumbnails` 会记录 `error` 状态和错误信息。

## 4. 打包注意事项

若使用 PyInstaller，请确保 `tools/ffmpeg/bin` 被拷贝到最终发布目录（与 `PortableVideoManager.exe` 同级的 `tools` 目录）。

