# Calendar Reporter

Google Calendar 行事曆自動報告工具。每天透過 GitHub Actions 自動抓取行事曆事件，產出純文字報告並發布到 GitHub，讓夥伴可以直接瀏覽。

## 📁 專案結構

```
calendar-discord-reporter/
├── fetch_public.py                      # 獨立抓取腳本（GitHub Actions 用）
├── calendar_report.py                   # 報告產生核心模組
├── main.py                              # Discord 通知入口（本機用）
├── verify_calendar.py                   # 驗證 Google Calendar 連線
├── requirements.txt                     # Python 依賴
├── .gitignore
├── .github/workflows/update-calendar.yml  # 每日自動更新 workflow
├── docs/calendar.txt                    # 自動產出的行事曆報告
└── README.md
```

## 🔄 自動發布（GitHub Actions）

每天台北時間 08:00（UTC 00:00）自動執行：

1. 從 Google Calendar 抓取未來 16 天的行事曆事件（包含今天與未來 15 天）
2. 產出純文字報告寫入 `docs/calendar.txt`
3. 自動 commit 並 push 回 repo

### 取用行事曆內容

```
https://raw.githubusercontent.com/<你的帳號>/calendar-discord-reporter/main/docs/calendar.txt
```

啟用 GitHub Pages 後也可以用：
```
https://<你的帳號>.github.io/calendar-discord-reporter/calendar.txt
```

### 設定步驟

1. **GitHub Secrets**：到 repo → Settings → Secrets and variables → Actions → New repository secret
   - 名稱：`GOOGLE_SERVICE_ACCOUNT_KEY`
   - 值：貼上整份 Service Account 金鑰 JSON 內容

2. **手動測試**：到 Actions 頁面 → `Update calendar` → Run workflow

3. **（選用）啟用 GitHub Pages**：Settings → Pages → Source 選 `main` branch, `/docs` folder

## ⚠️ 安全須知

- **Service Account 金鑰**放在 GitHub Secrets，絕不 commit
- `.gitignore` 已包含 `gcp-key.json` 作為安全防線
- `CALENDAR_ID` 公開無害（沒有金鑰無法讀取行事曆）

## 🛠️ 本機開發

### 安裝

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e ../maple_toolkit   # 僅本機 Discord 功能需要
```

### 本機測試抓取（不需要 maple_toolkit）

```bash
# 設定認證
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/calendar-discord-reporter/google-credentials.json

# 執行
python fetch_public.py
```

### 驗證 Google Calendar 連線

```bash
python verify_calendar.py
```

### 發送到 Discord（需要 maple_toolkit）

```bash
python main.py
```

## 🔐 設定檔位置（本機用）

| 設定 | 位置 |
|------|------|
| 全域設定 | `~/.config/maple/global_config.json` |
| 專案設定 | `~/.config/calendar-discord-reporter/config.json` |
| Service Account 金鑰 | `~/.config/calendar-discord-reporter/google-credentials.json` |

> [!IMPORTANT]
> 如果 `verify_calendar.py` 回報「No events found」，請確認已在 Google Calendar 設定中將 Service Account 的 email（`...@...iam.gserviceaccount.com`）加為共用對象，並授予「查看所有活動詳細資料」權限。