# WorkApp 0.1

台灣優先的全球職缺搜尋與持久化背景掃描。此 APP 位於 `workapp` 分支，從公司 `main` 的 `04ee2abb2da05acefc224c7d623c79af512f358b` 建立。

## 本機啟動

需要 Python 3.12 或以上；執行程式不需安裝第三方套件。

```sh
python3 -m workapp.server
```

打開 <http://127.0.0.1:8000>。請在 repository 根目錄執行。

SQLite 資料保存在 `data/workapp.sqlite3`，不加入 Git。停止服務再備份整個 `data/` 即可。掃描條件、首次發現紀錄、掃描歷史與來源快取均持久保存；重啟會補執行已到期的規則一次，不重播所有錯過的週期。

## 使用

1. 設定關鍵字（逗號分隔，符合任一項）、台灣／全球範圍、地點、工作模式與薪資門檻。
2. 搜尋並查看工作內容；點職稱到原始招募頁核對並應徵。
3. 點「儲存為自動掃描」，填寫名稱與每 6／12／24 小時頻率。
4. 首次掃描在 30 秒內執行。在「自動掃描」查看已發現職缺、手動掃描、暫停／恢復或刪除。

**關閉瀏覽器仍會掃描，但後端程序必須保持運行。** 首次掃描建立目前符合條件的基線，後續只對未曾記錄的來源職缺 ID 計為「首次發現」。這不是新發布時間；同一職缺重複出現不重複計數。通知管道尚未串接。

## 來源與覆蓋

| 來源 | 範圍 | 讀取間隔 | 實際驗證（2026-09-30） |
|---|---|---|---|
| [Appier / Greenhouse](https://job-boards.greenhouse.io/appier) | 台灣與海外公司職缺 | 至少 30 分鐘 | 68 個職缺，含台灣 |
| [Canonical / Greenhouse](https://job-boards.greenhouse.io/canonical) | 台灣與全球公司職缺 | 至少 30 分鐘 | 306 個職缺，含台灣 |
| [Remotive](https://remotive.com/) | 全球遠端職缺 | 至少 6 小時 | 16 個職缺 |

Remotive 使用完整列表 API，遵守建議最多每天 4 次；所有規則與搜尋共享跨重啟快取。其公開 API 職缺可能延遲 24 小時。職缺連回 Remotive 並標示来源，不加註冊門檻。

這是接入來源的搜尋，不是所有全球職缺的索引。104 自動讀取實測回傳 403；第一版未接入，也不繞過限制。未來台灣擴充可採正式合作或合法公開 API。

### 篩選的精確含義

- 「台灣可應徵」保守地包含地點明列 Taiwan、Taipei 等台灣城市，以及 Worldwide／Anywhere／Global。僅標示 Asia／APAC 的職缺不自動推定可在台灣應徵。地區條件仍需依原始招募頁確認；沒有法律資格保證。
- 明列台灣地點的職缺優先排序，其次全球適用的職缺，各群組依來源發布／更新時間排序。
- 工作模式只根據來源結構欄位，或職稱／地點中明列的 Remote、Home based、Hybrid、Office based。來源未明列則顯示「模式未明列」；不从描述中的「remote servers」之類文字推定。
- 薪資門檻比對公開區間上限。只解析明確的 TWD／NT$／新台幣或 USD／US$，且必須有月／年週期。不推測 `$80k` 的幣別或週期、不換匯、不把年薪除以 12。
- 啟用薪資門檻時，幣別與週期必須相同。選擇「仍包含薪資未公開／單位未明列」可保留無法可靠比較的職缺。多數公司来源未提供結構化薪資，所以薪資篩選可能大幅減少結果。
- 來源讀取失敗時保留快取並顯示警告。只有成功取得完整列表，才將不再列出的職缺標成「來源已不再列出」；這不等同確認公司停止招募。

## 驗證

```sh
python3 -m unittest discover -s tests -v
node --check workapp/static/app.js
```

13 個測試驗證條件與薪資單位、地區限制、排程持久化、去重併發、快取、資料來源失敗、刪除與跨來源寫入保護。HTTP 測試需要允許本機 loopback socket。

另已用 Chromium 實測桌面／375px 手機完整操作、200% 文字放大、錯誤與空結果。交付證據見 `project/acceptance/round-001.md`。

## API 與架構

- `GET /api/jobs`：上述篩選欄位、`page`；每頁 30 筆並附來源狀態。
- `GET /api/rules`、`POST /api/rules`：讀取／新增規則（`name`, `hours`, `filters`）。最多 50 組。
- `POST /api/scan`：`{"id": 1}`，執行規則並回傳符合數、首次發現數及警告。
- `POST /api/rules/pause`：`{"id": 1, "paused": true}`。
- `POST /api/rules/delete`：刪除該規則及其發現／執行紀錄。
- `GET /api/discoveries?rule_id=1`：取得該規則已發現的職缺與來源是否仍列出。
- `GET /api/status`：來源更新、失敗與更新間隔。

`providers.py` 提供来源轉接與欄位正規化；`domain.py` 定義薪資與篩選契約；`service.py` 管理 SQLite、快取與每 30 秒檢查到期的背景工作；`server.py` 是本機 HTTP API；`static/` 為無框架的響應式介面。

## 部署準備

這版供個人本機驗收，預設只綁定 `127.0.0.1`。尚未正式部署。

持續運行的部署需要 Python 主機／容器、持久磁碟、程序守護、HTTPS 與登入保護。避免同一資料庫啟動多個 scheduler；多副本需集中排程與鎖。若要公開或多使用者，需加入身份驗證與使用者資料隔離後再發布。原始 SQLite 文件不可放進公開靜態資產。

關鍵字英文採完整詞比對（Unity不會命中community或opportunity），Unity也比對Unity3D；中文仍可比對詞片段。搜尋與定期掃描共用此規則。

### 台灣人力銀行外站搜尋
搜尋頁提供 104、1111 站內搜尋與 Google 限定該站職缺頁搜尋。連結隨表單條件更新；站內僅帶入關鍵字，Google 帶入關鍵字（逗號 OR）、地點與模式詞。薪資與資格須在原站確認。這是外站入口，尚非職缺擷取或自動掃描整合，不計入列表數量。直接讀取目前遇到 104 空殼／403、1111 TLS 憑證錯誤、Google JavaScript 檢查頁。

### Google 結果直接顯示（SerpApi）
目前新增 `POST /api/web-search`，獨立於既有 API 職缺列表。搜尋按鈕在網頁內呈現 Google 第一頁收錄的 104／1111 單筆職缺標題與摘要；尚未確認在招、遠端、薪資與台灣應徵資格。薪資條件不套用於此區，不納入自動掃描。

啟用需自行準備 SerpApi 金鑰（服務方案及額度由帳號管理，程式不開通或購買方案）。在啟動伺服器的同一個 PowerShell 視窗執行：

```powershell
$workappSecureKey = Read-Host 'SerpApi key' -AsSecureString
$env:WORKAPP_SERPAPI_KEY = [System.Net.NetworkCredential]::new('', $workappSecureKey).Password
py -3.13 -m workapp.server
```

先關閉原本的 WorkApp 後端再重啟；`.env` 不會自動載入。不要把金鑰貼進對話、程式碼或 Git。設定後在搜尋頁輸入 Unity，按「搜尋 104／1111」。每次手動搜尋最多一筆 API 請求，查詢快取 6 小時，每小時上限 10 次；來源失敗保留過期快取並明示，不會把讀取失敗當成零職缺。後端測試使用模擬服務回應，未配置真實金鑰前不構成實際接入驗證。

服務文件：https://serpapi.com/search-api

### 104 直接搜尋
參考使用者 WorkManager 8fd3f43，使用瀏覽器正常載入搜尋頁，再從同一工作階段讀 JSON。104 要求驗證或拒絕讀取時停止並顯示失敗，不會把它當沒有職缺。2026-10-01 本機實測仍被拒絕，尚無成功真實結果。

安裝與啟動（Windows）：
```powershell
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m playwright install chromium
.venv/Scripts/python.exe -m workapp.server
```

在搜尋頁輸入單個關鍵字後按「直接搜尋 104」。讀前兩頁、快取 30 分鐘、失敗冷卻 5 分鐘；篩選後只顯示已讀取部分符合的結果，不是全站總數。尚未納入自動掃描；1111 沒有直接讀取器，Google 仍為需要金鑰的備選。虛擬環境與參考 repo 位於忽略目錄，不推送。
