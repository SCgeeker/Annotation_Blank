# miniverse

極簡的 Obsidian vault，透過自訂串接的LLM，將學術論文 PDF 轉換成結構化的原子筆記。使用流程：放入 PDF、在 Obsidian 執行三道指令、取得包含約 20 張 Zettelkasten 原子卡片的完整結構化解讀筆記。

---

## miniverse 能做什麼

1. **Generate Slides** — 讀取 `+/pdf/` 中的 PDF，呼叫 `claude_lit_workflow` 產生結構化 Markdown 投影片大綱。
2. **Generate Zettel** — 利用投影片大綱（選擇性但建議使用）為論文產生 20 張 Zettelkasten 原子卡片。
3. **Import Zettel** — 將卡片複製到 `ACT/0️⃣Annotation/作者-年份/cards/`，並建立主 Annotation 筆記。

三個步驟都透過 Obsidian 內的 ALT+L 選單觸發。

---

## 前置需求

1. **Obsidian** — 從 [obsidian.md](https://obsidian.md) 下載，任何近期版本皆可。

2. **Python 3.11+ 與 uv** — uv 是 `claude_lit_workflow` 使用的套件管理工具。
   - 安裝 uv：`pip install uv` 或依照[官方安裝說明](https://docs.astral.sh/uv/getting-started/installation/)。
   - 驗證：`uv --version`

3. **claude_lit_workflow** — 處理 PDF 的 AI 後端。
   - 儲存庫：[https://github.com/SCgeeker/claude_lit_workflow](https://github.com/SCgeeker/claude_lit_workflow)
   - 將它 clone 到本機資料夾（例如 `C:/projects/claude_lit_workflow`）。

4. **至少一個 LLM API 金鑰** — 推薦使用 Google Gemini，因為它有免費額度，對一般學術用途已足夠。
   - 免費 Gemini 金鑰：[aistudio.google.com](https://aistudio.google.com/app/apikey)
   - 其他支援的供應商：OpenAI、Anthropic Claude。

---

## 快速設定

### 步驟一：Clone miniverse 並以 Obsidian vault 開啟

```bash
git clone https://github.com/SCgeeker/miniverse.git
```

開啟 Obsidian，點選**以資料夾開啟 vault**，選擇 `miniverse` 資料夾。

### 步驟二：安裝社群插件

在 Obsidian 內：

1. 前往**設定 → 社群插件 → 瀏覽**。
2. 搜尋 **QuickAdd**，安裝並啟用。
3. 搜尋 **Templater**，安裝並啟用。
4. 若出現提示，重新載入 Obsidian。

`.obsidian/plugins/` 中的插件設定檔已預先設定完成，不需要在 Obsidian 內進行額外設定。

### 步驟三：設定 claude_lit_workflow

```bash
cd /path/to/claude_lit_workflow
uv sync
```

在 `claude_lit_workflow` 根目錄建立 `.env` 檔案，填入你的 API 金鑰：

```env
# Google Gemini（推薦，有免費額度）
GOOGLE_API_KEY=你的金鑰

# 或者 OpenAI
# OPENAI_API_KEY=你的金鑰

# 或者 Anthropic
# ANTHROPIC_API_KEY=你的金鑰
```

驗證設定是否正確：

```bash
uv run slides --help
```

### 步驟四：編輯 workflow-config.json（供 QuickAdd 使用）

此檔案由 ALT+L 選單的 QuickAdd JavaScript wrapper 讀取（Generate Slides、Generate Zettel 使用）。開啟 `Atlas/tools/scripts/workflow-config.json`，將 `YOUR_CLAUDE_LIT_WORKFLOW_PATH` 替換為你本機 `claude_lit_workflow` clone 的絕對路徑。

範例（Windows）：
```json
"claude_lit_dir": "C:/projects/claude_lit_workflow"
```

範例（Mac/Linux）：
```json
"claude_lit_dir": "/home/yourname/projects/claude_lit_workflow"
```

### 步驟五：編輯 config.yaml（供 QuickAdd Scripts 使用）

此檔案由 Python 匯入腳本（`import_zettel.py`）讀取，對應 ALT+L 選單的第三步。開啟 `Atlas/tools/import/config.yaml`，替換兩個佔位符：

- `YOUR_CLAUDE_LIT_WORKFLOW_PATH` → 同上的路徑
- `YOUR_MINIVERSE_VAULT_PATH` → 本 vault 資料夾的絕對路徑

範例（Windows）：
```yaml
claude_lit_output: "C:/projects/claude_lit_workflow/output/zettelkasten_notes"
vault: "C:/Users/YourName/vaults/miniverse"
```

### 步驟五之二：（選擇性）設定 Zotero 書目匯出

Zotero 能為 Annotation 筆記提供更完整的書目資料（作者姓名、年份、期刊名稱、DOI）。此步驟為選擇性。若略過，匯入器會退回使用 zettel index 中擷取的 metadata，準確度較低。

**為什麼值得做？** Annotation 筆記的 frontmatter（`authors`、`year`、`container`）由 `.bib` 檔案填入。沒有 Zotero 的話，這些欄位可能不完整或遺失。

**從 Zotero 匯出：**

1. 開啟 Zotero。
2. 前往**檔案 → 匯出文獻庫…**
3. 選擇格式 **BibTeX**。
4. 將檔案儲存為 `My Library.bib`，直接放入 vault 的 `+/` 資料夾。
   - 完整路徑範例（Windows）：`C:/Users/YourName/vaults/miniverse/+/My Library.bib`

`config.yaml` 預設已指向 `+/My Library.bib`，只要存到該位置就不需要額外修改。

**自動同步（選擇性）：** 若你使用 Zotero 的 [Better BibTeX](https://retorque.re/zotero-better-bibtex/) 插件，可以設定在文獻庫變更時自動覆寫匯出檔案，讓 metadata 保持最新狀態。

**若略過此步驟：** 開啟 `Atlas/tools/import/config.yaml`，修改以下設定：
```yaml
bibtex:
  enabled: false
```

### 步驟六：建立 kb_output 符號連結

投影片輸出資料夾需要從 vault 內存取。請建立從 `+/kb_output` 指向 `claude_lit_workflow` 輸出目錄的符號連結。

**Windows（以系統管理員身分執行命令提示字元）：**
```cmd
mklink /D "C:\path\to\miniverse\+\kb_output" "C:\projects\claude_lit_workflow\output"
```

**Mac/Linux：**
```bash
ln -s /path/to/claude_lit_workflow/output /path/to/miniverse/+/kb_output
```

### 步驟七：將 PDF 放入 +/pdf/

將學術論文 PDF 複製或移動到 vault 內的 `+/pdf/` 資料夾。檔案名稱不需要與 citekey 相符。

---

## 使用方式

在 Obsidian 內按 **ALT+L** 開啟 MiniVerse Tools 選單，依序執行三個步驟：

**步驟一：Generate Slides（生成投影片）**
- 從清單中選擇 PDF。
- 選擇 Style、Detail 等級、語言和 LLM 供應商。
- 等待通知確認投影片 Markdown 已建立於 `+/kb_output/`。
- 開啟產生的 `.md` 檔案，檢視或編輯投影片大綱。這能提升下一步的卡片品質。

**步驟二：Generate Zettel（生成卡片）**
- 選擇同一份 PDF。
- 從 `+/kb_output/` 選擇對應的投影片檔案（選擇性，但建議使用）。
- 選擇 Detail 等級、語言和 LLM 供應商。
- 等待確認通知。

**步驟三：Import Zettel（匯入卡片）**
- 從已生成的 zettel 資料夾清單中選擇論文。
- 腳本會自動將卡片複製到 `ACT/0️⃣Annotation/作者-年份/cards/`，並開啟新建立的 Annotation 筆記。

---

## 資料夾結構

```
miniverse/
├── +/
│   ├── pdf/          ← 將你的 PDF 放在這裡
│   └── kb_output/    ← 符號連結指向 claude_lit_workflow/output/
├── ACT/
│   └── 0️⃣Annotation/ ← 產生的 Annotation 筆記存放於此
├── Atlas/
│   └── tools/
│       ├── import/
│       │   ├── import_zettel.py   （匯入腳本）
│       │   └── config.yaml        （填入路徑）
│       └── scripts/
│           ├── workflow-config.json  （填入路徑）
│           ├── slides_wrapper.js
│           ├── zettel_wrapper.js
│           └── import_wrapper.js
└── Templates/
    ├── Template, Generate Slides.md
    ├── Template, Generate Zettel.md
    └── Template, Import Zettel.md
```

---

## 問題排除

**ALT+L 沒有反應**
- 確認 QuickAdd 和 Templater 插件都已啟用。
- 前往**設定 → 快捷鍵**，搜尋「QuickAdd」，確認快捷鍵已指定給「MiniVerse Tools」選項。

**「無法讀取 workflow-config.json」**
- 確認檔案存在於 `Atlas/tools/scripts/workflow-config.json`，且 `claude_lit_dir` 值已正確填寫。

**「無法讀取 PDF 資料夾」**
- 確認 `+/pdf/` 存在且包含至少一個 `.pdf` 檔案。

**「找不到任何 Zettelkasten 資料夾」**
- 請先執行 Generate Zettel。Import 步驟需要 zettel 指令的輸出。

**「匯入失敗」/ Python 錯誤**
- 確認 `workflow-config.json` 中的 `python_executable` 指向可用的 Python 3.11+ 執行檔。在終端機執行 `python --version` 確認版本。
- Windows 上，`python` 可能指向 Microsoft Store 的替代程式。使用完整路徑，例如 `C:/Users/YourName/AppData/Local/Programs/Python/Python311/python.exe`。

**BibTeX metadata 遺失**
- 如果沒有 Zotero，在 `config.yaml` 中設定 `bibtex.enabled: false`。匯入器將改用 zettel index 中的 metadata。

**投影片或卡片生成速度很慢**
- LLM 呼叫依供應商和論文長度需要 30–120 秒，屬於正常現象。指令完成後 Obsidian 通知會出現。

**Google Gemini 免費額度說明**
- Gemini 免費方案（Gemini 1.5 Flash）每分鐘 15 次請求，每天 1,500 次請求，對一般學術用途已足夠。
- 若需要處理大量論文，考慮使用付費方案或改用 OpenAI/Anthropic。
