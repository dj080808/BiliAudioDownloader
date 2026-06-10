# 🎵 Bilibili 音频下载器

一个基于 FastAPI 的 Web 应用，粘贴 Bilibili 视频链接即可提取并下载音频，无需登录。

## 功能

- 🎯 **简洁的 Web 界面** — 粘贴链接，选择格式，点击下载
- 🎛️ **多格式支持** — MP3 / M4A / Opus / FLAC / WAV / AAC，前端下拉框自由切换
- 🖼️ **实时预览** — 下载前显示视频标题、封面和时长
- 📊 **下载进度** — 实时进度条，显示百分比和文件大小
- 📋 **最近下载列表** — 基于 localStorage，自动记录最近下载的链接，点击即可回填
- 🔄 **下载后自动重置** — 点击下载按钮后自动清空界面，方便连续下载
- 🧹 **自动清理** — 临时文件和过期任务自动删除
- 🔒 **域名校验** — 仅接受 bilibili.com / b23.tv / b22.tv 链接
- 🔗 **智能补全** — 自动为裸域名补全 `https://` 前缀
- 🌍 **CORS 已开启** — 可从其他域名调用 API
- 🐳 **无需数据库** — 所有状态存于内存，Python 之外零依赖

## 支持的链接

支持所有常见的 Bilibili 视频链接：

- `https://www.bilibili.com/video/BV1xx411c7mD`
- `https://b23.tv/xxxxxx`（短链接）
- `www.bilibili.com/video/BV1xx411c7mD`（自动补全 `https://`）
- 任何 `bilibili.com`、`b23.tv`、`b22.tv` 域名下的视频链接

## 支持的音频格式

| 格式 | 说明 | 是否需要 ffmpeg |
|------|------|:---:|
| **MP3** | 通用兼容，默认格式 | ✅ 需要 |
| **M4A (AAC)** | Bilibili 原生格式，无需转码 | ❌ 不需要 |
| **Opus** | Bilibili 原生格式，高音质低码率 | ❌ 不需要 |
| **FLAC** | 无损压缩 | ✅ 需要 |
| **WAV** | 无损未压缩 | ✅ 需要 |
| **AAC** | 高级音频编码 | ✅ 需要 |

> 💡 **提示**：如果只想快速下载且不想安装 ffmpeg，选择 M4A 或 Opus（原生格式）即可。MP3 / FLAC / WAV / AAC 需要 ffmpeg 做音频转换。

### 安装 ffmpeg（如需非原生格式）

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows ( chocolatey / winget )
choco install ffmpeg
# 或
winget install ffmpeg
```

## 快速开始

### 环境要求

- **Python 3.10+**
- **pip**
- （可选）**ffmpeg** — 仅 MP3 / FLAC / WAV / AAC 格式需要

### 1. 克隆项目并安装依赖

```bash
git clone <repo-url> && cd downloadtool
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python main.py
```

服务默认运行在 `http://0.0.0.0:8000`，带热重载。

也可以直接用 uvicorn：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 打开浏览器

访问 **http://localhost:8000** 即可看到 Web 界面。

## 使用方法

1. **粘贴** Bilibili 视频链接到输入框（例如 `https://www.bilibili.com/video/BV1xx411c7mD`）
2. 从下拉框**选择音频格式**（默认 MP3）
3. 点击 **Submit** 或按回车键
4. 稍等几秒，服务器获取视频信息并下载音频
5. 下载完成后，页面会显示视频标题、封面和时长——点击 **Download Audio** 保存文件
6. 点击下载后页面**自动重置**；也可以随时点击 **Reset** 取消当前任务并重新开始

**最近下载列表**会自动记录每次成功下载的链接，点击历史记录可快速回填链接和格式，方便重复下载。记录保存 7 天，最多 30 条。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 返回前端页面 |
| `POST` | `/api/prepare` | 提交链接（请求体：`{"url": "...", "format": "mp3"}`），返回 `task_id` |
| `GET` | `/api/task/{task_id}` | 查询任务状态、进度、元数据和下载地址 |
| `GET` | `/api/download/{task_id}` | 下载音频文件（下载完成后自动清理） |

### API 调用示例

```bash
# 1. 提交链接（指定格式为 mp3）
curl -X POST http://localhost:8000/api/prepare \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.bilibili.com/video/BV1xx411c7mD", "format": "mp3"}'
# 返回：{"task_id": "abc123...", "status": "preparing"}

# 2. 轮询直到状态变为 "ready"
curl http://localhost:8000/api/task/abc123...
# 返回：{"task_id": "...", "status": "downloading", "progress": 45, "title": "...", ...}

# 3. 下载音频
curl -O http://localhost:8000/api/download/abc123...
```

### 任务状态说明

| 状态 | 含义 |
|------|------|
| `preparing` | 正在从 Bilibili 获取视频信息 |
| `downloading` | 正在下载/转换音频（可通过 progress 字段查看进度） |
| `ready` | 音频已就绪，可以下载 |
| `error` | 出错（错误信息见 error 字段） |

## 配置项

所有配置均通过环境变量设置，有合理的默认值：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DOWNLOADTOOL_TEMP_DIR` | `<系统临时目录>/downloadtool` | 临时存放下载音频的目录 |
| `DOWNLOADTOOL_MAX_TASK_AGE` | `1800`（30 分钟） | 过期任务自动清理的时间（秒） |
| `DOWNLOADTOOL_CLEANUP_INTERVAL` | `600`（10 分钟） | 清理任务的间隔（秒） |
| `DOWNLOADTOOL_MAX_FILE_SIZE` | `200000000`（200 MB） | 音频文件大小上限，超过则中止下载 |
| `DOWNLOADTOOL_DEFAULT_AUDIO_FORMAT` | `mp3` | 默认输出音频格式 |

示例：

```bash
# Linux / macOS
export DOWNLOADTOOL_TEMP_DIR=/var/cache/downloadtool
export DOWNLOADTOOL_MAX_FILE_SIZE=500000000   # 500 MB
export DOWNLOADTOOL_DEFAULT_AUDIO_FORMAT=m4a

# Windows (PowerShell)
$env:DOWNLOADTOOL_TEMP_DIR="D:\cache\downloadtool"

# 然后正常启动
python main.py
```

## 部署

### 使用 systemd（Linux）

```ini
# /etc/systemd/system/downloadtool.service
[Unit]
Description=Bilibili Audio Downloader
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/downloadtool
ExecStart=/opt/downloadtool/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
Environment="DOWNLOADTOOL_TEMP_DIR=/var/cache/downloadtool"

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now downloadtool
```

### 配合 nginx 使用

在 nginx 后面做 TLS 终止。由于下载可能耗时较长，需要加大代理超时时间：

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;      # 大文件下载需要长超时
        proxy_buffering off;           # 文件下载体验更好
    }
}
```

### Docker（参考）

暂无官方镜像，一个简单的 `Dockerfile` 如下：

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> 镜像中预装了 ffmpeg，支持所有音频格式。

## 工作原理

```
浏览器 ──POST /api/prepare──▶ FastAPI
         {url, format}              │
                                    ├─ yt-dlp --dump-json  → 提取视频信息
                                    ├─ yt-dlp -f bestaudio → 下载音频
                                    │   （原生格式直接下载，其他格式用 ffmpeg 转码）
                                    │   （每 0.5 秒检测文件大小来获取进度）
                                    │
         ◀──GET /api/task/{id}──── task_manager（内存字典）
         ◀──GET /api/download/{id}─ FileResponse + BackgroundTask 清理
```

- **yt-dlp** 处理所有 Bilibili 链接格式和音频提取
- **原生格式（M4A / Opus）** 直接下载，无需 ffmpeg
- **转码格式（MP3 / FLAC / WAV / AAC）** 通过 yt-dlp 的 `--extract-audio` + ffmpeg 做后处理
- **文件大小轮询** 获取下载进度，比解析 yt-dlp 的 stderr 更简单可靠
- **内存任务存储** — 简单快速，无需外部数据库
- **同源部署** — FastAPI 同时提供静态页面和 API，正常使用无 CORS 问题（CORS 中间件仍保留以增加灵活性）

## 项目结构

```
downloadtool/
├── main.py              # FastAPI 应用、路由、后台任务
├── downloader.py        # yt-dlp 子进程封装（元数据提取 + 音频下载）
├── task_manager.py      # 基于内存的异步安全任务存储
├── models.py            # Pydantic 数据模型与枚举
├── config.py            # 所有配置常量（环境变量可覆盖）
├── requirements.txt     # Python 依赖
├── static/
│   └── index.html       # 单页前端（内嵌 CSS + vanilla JS）
└── README.md
```

## 依赖

| 包 | 用途 |
|---|---|
| [FastAPI](https://fastapi.tiangolo.com/) | Web 框架 |
| [uvicorn](https://www.uvicorn.org/) | ASGI 服务器 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Bilibili 视频/音频提取（通过子进程调用） |
| （可选）[ffmpeg](https://ffmpeg.org/) | MP3 / FLAC / WAV / AAC 格式的音频转码 |

## 许可证

MIT
