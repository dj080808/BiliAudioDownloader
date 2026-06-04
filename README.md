# 🎵 Bilibili 音频下载器

一个基于 FastAPI 的 Web 应用，粘贴 Bilibili 视频链接即可提取并下载音频，无需登录。

## 功能

- 🎯 **简洁的 Web 界面** — 粘贴链接，点击下载
- 🖼️ **实时预览** — 下载前显示视频标题、封面和时长
- 📊 **下载进度** — 实时进度条，显示百分比和文件大小
- 🧹 **自动清理** — 临时文件和过期任务自动删除
- 🔒 **域名校验** — 仅接受 bilibili.com / b23.tv 链接
- 🌍 **CORS 已开启** — 可从其他域名调用 API
- 🐳 **无需数据库** — 所有状态存于内存，Python 之外零依赖

## 支持的链接

支持所有常见的 Bilibili 视频链接：

- `https://www.bilibili.com/video/BV1xx411c7mD`
- `https://b23.tv/xxxxxx`（短链接）
- 任何 `bilibili.com` 或 `b23.tv` 域名下的视频链接

## 快速开始

### 环境要求

- **Python 3.10+**
- **pip**

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
2. 点击 **Submit** 或按回车键
3. 稍等几秒，服务器获取视频信息并下载音频
4. 下载完成后，页面会显示视频标题、封面和时长——点击 **Download Audio** 保存文件
5. 点击 **Reset** 可以继续下载下一个视频

音频文件通常为 `.m4a` 格式（AAC 编码），所有主流设备均可播放。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 返回前端页面 |
| `POST` | `/api/prepare` | 提交链接（请求体：`{"url": "..."}`），返回 `task_id` |
| `GET` | `/api/task/{task_id}` | 查询任务状态、进度、元数据和下载地址 |
| `GET` | `/api/download/{task_id}` | 下载音频文件（下载完成后自动清理） |

### API 调用示例

```bash
# 1. 提交链接
curl -X POST http://localhost:8000/api/prepare \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.bilibili.com/video/BV1xx411c7mD"}'
# 返回：{"task_id": "abc123...", "status": "preparing"}

# 2. 轮询直到状态变为 "ready"
curl http://localhost:8000/api/task/abc123...
# 返回：{"task_id": "...", "status": "downloading", "progress": 45, ...}

# 3. 下载音频
curl -O http://localhost:8000/api/download/abc123...
```

### 任务状态说明

| 状态 | 含义 |
|------|------|
| `preparing` | 正在从 Bilibili 获取视频信息 |
| `downloading` | 正在下载音频（可通过 progress 字段查看进度） |
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

示例：

```bash
# Linux / macOS
export DOWNLOADTOOL_TEMP_DIR=/var/cache/downloadtool
export DOWNLOADTOOL_MAX_FILE_SIZE=500000000   # 500 MB

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
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 工作原理

```
浏览器 ──POST /api/prepare──▶ FastAPI
         {url}                      │
                                    ├─ yt-dlp --dump-json  → 提取视频信息
                                    ├─ yt-dlp -f bestaudio → 下载音频
                                    │   （每 0.5 秒检测文件大小来获取进度）
                                    │
         ◀──GET /api/task/{id}──── task_manager（内存字典）
         ◀──GET /api/download/{id}─ FileResponse + BackgroundTask 清理
```

- **yt-dlp** 处理所有 Bilibili 链接格式和音频提取
- **无需 ffmpeg** — 直接提供原生 `bestaudio` 流（通常为 `.m4a` 格式）
- **文件大小轮询** 获取下载进度，比解析 yt-dlp 的 stderr 更简单可靠
- **内存任务存储** — 简单快速，无需外部数据库

## 项目结构

```
downloadtool/
├── main.py              # FastAPI 应用、路由、后台任务
├── downloader.py        # yt-dlp 子进程封装
├── task_manager.py      # 基于内存的异步安全任务存储
├── models.py            # Pydantic 数据模型与枚举
├── config.py            # 所有配置常量
├── requirements.txt     # Python 依赖
├── static/
│   └── index.html       # 单页前端（内嵌 CSS + JS）
└── README.md
```

## 依赖

| 包 | 用途 |
|---|---|
| [FastAPI](https://fastapi.tiangolo.com/) | Web 框架 |
| [uvicorn](https://www.uvicorn.org/) | ASGI 服务器 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Bilibili 视频/音频提取（通过子进程调用） |

## 许可证

MIT
