# 分支與版本規則

| 分支 | 內容 | 合併目標 |
|---|---|---|
| `main` | 公司制度、員工核心、共用模板 | 公司正式版本 |
| `company-member/<change-id>` | 員工或制度變更 | `main` |
| `project/<app-id>` | 單一 APP 的程式、需求、設計與記憶 | 長期保留，不合併回 main |
| `work/<app-id>/<task-id>` | 單項 APP 工作 | `project/<app-id>` |

## 命名注意

Git 不能同時建立 `project/app-a` 與 `project/app-a/login`，因為分支名稱存在路徑衝突。因此工作分支採用 `work/app-a/login`。這修正了初步架構圖的命名，保留公司與專案分開的原則。

## 新 APP

1. 從乾淨、已提交的 `main` 建立 `project/<app-id>`；若 main 尚未提交，先完成公司基線提交。
2. 將 `templates/project/` 複製為根目錄 `project/`，填寫內容；依技術選型建立程式與測試目錄。
3. 在 `project/company-version.md` 記錄來源公司版本及 main 的實際 commit SHA。
4. 工作分支從對應 APP 分支建立，完成並驗證後合併回該 APP。
5. 多 APP 同時開發可用 Git worktree 建立獨立工作目錄，避免相互切換造成混淆。

## 公司更新

公司變更在 `company-member/<change-id>` 完成；創辦人核准後合併 main 並更新公司版本。APP 不直接修改員工核心。需同步時在 APP 工作分支合併已核准的 main，檢查差異及衝突，驗證後更新 company-version 紀錄。

公司資料在各分支是版本快照，不會自動更新。main 不得引入 APP 專用程式或記憶；同步前確認公司提交的範圍。若 APP 暫不升級，明確記錄所用舊版。

## 初次建置

本次公司初版直接準備於 main 工作目錄；尚未提交的內容不構成 Git 版本或已核准發布。後續公司更新再使用公司變更分支。只在有對應工作時建立分支，不建立空白 APP 分支。
