# miniverse

> **Part of the [CSC PKM System](https://github.com/orgs/SCgeeker/projects)**
>
> | Repo | Role |
> |---|---|
> | [ACT_Base](https://github.com/SCgeeker/ACT_Base) | Core structure & note templates |
> | **Annotation_Blank** ← *you are here* | Obsidian annotation vault |
> | [claude_lit_workflow](https://github.com/SCgeeker/claude_lit_workflow) | AI backend — slides & zettel generation |
> | [zotero-arxiv-daily](https://github.com/SCgeeker/zotero-arxiv-daily) | Paper discovery & Zotero ingestion |
> | [twcc-ollama-proxy](https://github.com/SCgeeker/twcc-ollama-proxy) | Local LLM inference proxy |
>
> **Pipeline:** arXiv/Zotero → `zotero-arxiv-daily` → `claude_lit_workflow` (+ optional `twcc-ollama-proxy`) → **`Annotation_Blank`** → structured notes

A minimal Obsidian vault for converting academic PDFs into structured Annotation notes using AI. It strips the full [Program_verse](https://github.com/SCgeeker/Program_verse) workflow down to a single pipeline: drop a PDF, run three commands in Obsidian, get a fully-formed Annotation note with 20 atomic Zettelkasten cards.

---

## What miniverse does

1. **Generate Slides** — reads a PDF from `+/pdf/`, calls `claude_lit_workflow` to produce a structured Markdown slide outline.
2. **Generate Zettel** — uses the slide outline (optional but recommended) to generate 20 atomic Zettelkasten cards for the paper.
3. **Import Zettel** — copies the cards into `ACT/0️⃣Annotation/Author-Year/cards/` and creates the main Annotation note.

All three steps are triggered from a single ALT+L menu inside Obsidian.

---

## Prerequisites

1. **Obsidian** — download from [obsidian.md](https://obsidian.md). Any recent version works.

2. **Python 3.11+ with uv** — uv is the package manager used by `claude_lit_workflow`.
   - Install uv: `pip install uv` or follow the [official installer](https://docs.astral.sh/uv/getting-started/installation/).
   - Verify: `uv --version`

3. **claude_lit_workflow** — the AI backend that processes PDFs.
   - Repository: [https://github.com/SCgeeker/claude_lit_workflow](https://github.com/SCgeeker/claude_lit_workflow)
   - Clone it to a local folder (e.g., `C:/projects/claude_lit_workflow`).

4. **At least one LLM API key** — Google Gemini is recommended because it has a free tier.
   - Get a free Gemini key at [aistudio.google.com](https://aistudio.google.com/app/apikey).
   - Other supported providers: OpenAI, Anthropic Claude.

---

## Quick Setup

### Step 1 — Clone miniverse and open as an Obsidian vault

```bash
git clone https://github.com/SCgeeker/miniverse.git
```

Open Obsidian, click **Open folder as vault**, and select the `miniverse` folder.

### Step 2 — Install community plugins

Inside Obsidian:

1. Go to **Settings → Community plugins → Browse**.
2. Search for **QuickAdd** and install it. Enable it.
3. Search for **Templater** and install it. Enable it.
4. Reload Obsidian if prompted.

The plugin configuration files in `.obsidian/plugins/` are already pre-configured. No further setup is needed inside Obsidian.

### Step 3 — Set up claude_lit_workflow

```bash
cd /path/to/claude_lit_workflow
uv sync
```

Create a `.env` file in the `claude_lit_workflow` root with your API key:

```env
# Google Gemini (recommended — free tier available)
GOOGLE_API_KEY=your_key_here

# Or OpenAI
# OPENAI_API_KEY=your_key_here

# Or Anthropic
# ANTHROPIC_API_KEY=your_key_here
```

Verify the setup works:

```bash
uv run slides --help
```

### Step 4 — Edit workflow-config.json (for QuickAdd)

This file is read by the QuickAdd JavaScript wrappers that power the ALT+L menu (Generate Slides, Generate Zettel). Open `Atlas/tools/scripts/workflow-config.json` and replace `YOUR_CLAUDE_LIT_WORKFLOW_PATH` with the absolute path to your `claude_lit_workflow` clone.

Example (Windows):
```json
"claude_lit_dir": "C:/projects/claude_lit_workflow"
```

Example (Mac/Linux):
```json
"claude_lit_dir": "/home/yourname/projects/claude_lit_workflow"
```

### Step 5 — Edit config.yaml (for **Generate Slides, Import Zettel**)

This file is read by the Python import script (`import_zettel.py`) that runs in Step 3 of the ALT+L menu. Open `Atlas/tools/import/config.yaml` and replace both placeholder values:

- `YOUR_CLAUDE_LIT_WORKFLOW_PATH` → same path as above
- `YOUR_MINIVERSE_VAULT_PATH` → absolute path to this vault folder

Example (Windows):
```yaml
claude_lit_output: "C:/projects/claude_lit_workflow/output/zettelkasten_notes"
vault: "C:/Users/YourName/vaults/miniverse"
```

### Step 5b — (Optional) Set up Zotero BibTeX export

Zotero provides richer metadata for your Annotation notes (author names, year, journal, DOI). This step is optional. Without it, the importer falls back to metadata extracted from the zettel index, which is less accurate.

**Why bother?** The Annotation note frontmatter (`authors`, `year`, `container`) is populated from the `.bib` file. Without Zotero, these fields may be incomplete or missing.

**Export from Zotero:**

1. Open Zotero.
2. Go to **File → Export Library…**
3. Choose format **BibTeX**.
4. Save the file as `My Library.bib` directly into the vault's `+/` folder.
   - Full path example: `C:/Users/YourName/vaults/miniverse/+/My Library.bib`

The `config.yaml` already points to `+/My Library.bib` by default — no further changes needed if you save it there.

**Auto-sync (optional):** If you use the [Better BibTeX](https://retorque.re/zotero-better-bibtex/) plugin for Zotero, you can set it to automatically export and overwrite the file whenever your library changes. This keeps metadata always up to date.

**If you skip this step:** Open `Atlas/tools/import/config.yaml` and set:
```yaml
bibtex:
  enabled: false
```

### Step 6 — Create the kb_output symlink

The slides output folder must be accessible inside the vault. Create a symlink from `+/kb_output` to the `claude_lit_workflow` output directory.

**Windows (run as Administrator):**
```cmd
mklink /D "C:\path\to\miniverse\+\kb_output" "C:\projects\claude_lit_workflow\output"
```

**Mac/Linux:**
```bash
ln -s /path/to/claude_lit_workflow/output /path/to/miniverse/+/kb_output
```

### Step 7 — Put a PDF in +/pdf/

Copy or move an academic paper PDF into the `+/pdf/` folder inside the vault. The filename does not need to match the citekey.

---

## Usage

Press **ALT+L** inside Obsidian to open the MiniVerse Tools menu. Run the three steps in order:

**Step 1 — Generate Slides**
- Select your PDF from the list.
- Choose Style, Detail level, Language, and LLM provider.
- Wait for the notice confirming the slide Markdown was created in `+/kb_output/`.
- Open the generated `.md` file and review or edit the slide outline. This improves card quality in the next step.

**Step 2 — Generate Zettel**
- Select the same PDF.
- Select the corresponding slide file from `+/kb_output/` (optional but recommended).
- Choose Detail level, Language, and LLM provider.
- Wait for the confirmation notice.

**Step 3 — Import Zettel**
- Select the paper from the list of generated zettel folders.
- The script copies cards into `ACT/0️⃣Annotation/Author-Year/cards/` and opens the new Annotation note automatically.

---

## Folder layout

```
miniverse/
├── +/
│   ├── pdf/          ← put your PDFs here
│   └── kb_output/    ← symlink to claude_lit_workflow/output/
├── ACT/
│   └── 0️⃣Annotation/ ← generated Annotation notes appear here
├── Atlas/
│   └── tools/
│       ├── import/
│       │   ├── import_zettel.py   (import script)
│       │   └── config.yaml        (fill in paths)
│       └── scripts/
│           ├── workflow-config.json  (fill in paths)
│           ├── slides_wrapper.js
│           ├── zettel_wrapper.js
│           └── import_wrapper.js
└── Templates/
    ├── Template, Generate Slides.md
    ├── Template, Generate Zettel.md
    └── Template, Import Zettel.md
```

---

## Troubleshooting

**ALT+L does nothing**
- Make sure both QuickAdd and Templater plugins are enabled.
- Go to **Settings → Hotkeys**, search for "QuickAdd", and verify the hotkey is assigned to the "MiniVerse Tools" choice.

**"Cannot read workflow-config.json"**
- The vault path inside Obsidian may use backslashes on Windows. The script handles this automatically. Verify the file exists at `Atlas/tools/scripts/workflow-config.json`.

**"Cannot find PDF folder"**
- Confirm that `+/pdf/` exists and contains at least one `.pdf` file.

**"No zettelkasten folders found"**
- Run Generate Zettel first. The import step requires output from the zettel command.

**"import failed" / Python error**
- Check that `python_executable` in `workflow-config.json` resolves to a working Python 3.11+ binary. Run `python --version` in your terminal to verify.
- On Windows, `python` may point to the Microsoft Store stub. Use the full path (e.g., `C:/Users/YourName/AppData/Local/Programs/Python/Python311/python.exe`).

**BibTeX metadata missing**
- If you do not have Zotero, set `bibtex.enabled: false` in `config.yaml`. The importer will use metadata from the zettel index instead.

**Slides or zettel generation is slow**
- LLM calls take 30–120 seconds depending on provider and paper length. This is normal. The Obsidian Notice will appear when the command finishes.
