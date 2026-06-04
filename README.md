# Bilibili Audio Downloader

Input a Bilibili video URL, get the audio downloaded.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run
python main.py
# or: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000 in the browser.

## Deploy

Example with systemd + nginx:

```
[Unit]
Description=Bilibili Audio Downloader
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/downloadtool
ExecStart=/opt/downloadtool/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Put nginx in front for TLS termination and increase proxy timeout:

```
proxy_read_timeout 300s;
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DOWNLOADTOOL_TEMP_DIR` | `<tmp>/downloadtool` | Temp file directory |
| `DOWNLOADTOOL_MAX_TASK_AGE` | `1800` | Stale task TTL (seconds) |
| `DOWNLOADTOOL_CLEANUP_INTERVAL` | `600` | Cleanup interval (seconds) |
| `DOWNLOADTOOL_MAX_FILE_SIZE` | `200000000` | Max download size (bytes) |
