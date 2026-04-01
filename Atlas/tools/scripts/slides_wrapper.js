// Atlas/tools/scripts/slides_wrapper.js
// Templater user script - 選擇 PDF，設定參數，呼叫 uv run slides 生成投影片
// 版本: 2.1  日期: 2026-03-23  更新: 新增 LLM provider / TWCC Ollama 選擇

async function generateSlides(tp) {
    const { exec } = require('child_process');
    const path = require('path');
    const fs = require('fs');

    // === 讀取 workflow-config.json ===
    const vaultPath = app.vault.adapter.basePath;
    const configJsonPath = path.join(vaultPath, 'Atlas/tools/scripts/workflow-config.json');

    let cfg;
    try {
        cfg = JSON.parse(fs.readFileSync(configJsonPath, 'utf-8'));
    } catch (e) {
        new Notice('❌ 無法讀取 workflow-config.json：' + e.message);
        return;
    }

    const claudeLitDir = cfg.claude_lit_dir;
    const uv           = cfg.uv_executable;
    const pdfFolder    = path.join(vaultPath, cfg.pdf_source_in_vault);
    const outputDir    = path.join(vaultPath, cfg.slides_output_subdir).replace(/\\/g, '/');

    // === 選擇 PDF ===
    let pdfs;
    try {
        pdfs = fs.readdirSync(pdfFolder)
            .filter(f => f.toLowerCase().endsWith('.pdf'))
            .sort();
    } catch (e) {
        new Notice('❌ 無法讀取 PDF 資料夾：' + pdfFolder);
        return;
    }

    if (pdfs.length === 0) {
        new Notice('找不到任何 PDF，請先將論文放入 +/pdf/');
        return;
    }

    const selectedPdf = await tp.system.suggester(
        pdfs,
        pdfs,
        false,
        `📄 選擇 PDF（共 ${pdfs.length} 個）`
    );
    if (!selectedPdf) return;

    // === 選擇 Style ===
    const styleLabels = [
        'modern_academic  — 現代學術（預設）',
        'classic_academic — 經典學術',
        'research_methods — 研究方法導向',
        'literature_review — 文獻回顧',
        'case_analysis    — 個案分析',
        'clinical         — 臨床報告',
        'teaching         — 教學簡報',
    ];
    const styleValues = [
        'modern_academic',
        'classic_academic',
        'research_methods',
        'literature_review',
        'case_analysis',
        'clinical',
        'teaching',
    ];
    const style = await tp.system.suggester(styleLabels, styleValues, false, '🎨 Style');
    if (!style) return;

    // === 選擇 Detail ===
    const detailLabels = [
        'standard     — 標準（預設）',
        'comprehensive — 完整詳細',
        'detailed      — 詳細',
        'brief         — 簡短',
        'minimal       — 最精簡',
    ];
    const detailValues = [
        'standard',
        'comprehensive',
        'detailed',
        'brief',
        'minimal',
    ];
    const detail = await tp.system.suggester(detailLabels, detailValues, false, '📊 Detail');
    if (!detail) return;

    // === 選擇 Language ===
    const langLabels = [
        'english  — 英文',
        'chinese  — 中文',
        'bilingual — 雙語',
    ];
    const langValues = ['english', 'chinese', 'bilingual'];
    const language = await tp.system.suggester(langLabels, langValues, false, '🌐 Language');
    if (!language) return;

    // === 選擇 Format ===
    const formatLabels = [
        'markdown — Markdown（Marp / reveal.js）',
        'pptx     — PowerPoint',
        'both     — Markdown + PowerPoint',
    ];
    const formatValues = ['markdown', 'pptx', 'both'];
    const format = await tp.system.suggester(formatLabels, formatValues, false, '💾 Format');
    if (!format) return;

    // === 探測本地 Ollama/TWCC Proxy ===
    const proxyOnline = await new Promise((resolve) => {
        const http = require('http');
        const req = http.get('http://localhost:11434/api/tags', (res) => {
            resolve(res.statusCode === 200);
        });
        req.setTimeout(500, () => { req.destroy(); resolve(false); });
        req.on('error', () => resolve(false));
    });

    // === 選擇 LLM Provider ===
    const providerLabels = proxyOnline ? [
        'ollama    — ✓ TWCC Proxy 已偵測（localhost:11434）',
        'auto      — 自動選擇（Gemini 優先）',
        'google    — Google Gemini',
        'openai    — OpenAI',
        'anthropic — Anthropic Claude',
    ] : [
        'auto      — 自動選擇（Gemini 優先）',
        'ollama    — TWCC Ollama（本地或遠端）',
        'google    — Google Gemini',
        'openai    — OpenAI',
        'anthropic — Anthropic Claude',
    ];
    const providerValues = proxyOnline
        ? ['ollama', 'auto', 'google', 'openai', 'anthropic']
        : ['auto', 'ollama', 'google', 'openai', 'anthropic'];
    const provider = await tp.system.suggester(providerLabels, providerValues, false, '🤖 LLM Provider');
    if (!provider) return;

    // === 若選 ollama，進一步選擇模型 ===
    let llmArgs = `--llm-provider ${provider}`;
    if (provider === 'ollama') {
        const twccModels = cfg.twcc_models || ['crystalmind', 'gemma-pro', 'gemma-pro-r'];
        const modelLabels = twccModels.map(m => m);
        const selectedModel = await tp.system.suggester(modelLabels, twccModels, false, '🧠 TWCC 模型');
        if (!selectedModel) return;
        llmArgs += ` --model ${selectedModel}`;
    }

    // === 組合指令並執行 ===
    const pdfPath = path.join(pdfFolder, selectedPdf).replace(/\\/g, '/');
    const cmd = `"${uv}" run slides --pdf "${pdfPath}" --style ${style} --detail ${detail} --language ${language} --format ${format} ${llmArgs}`;

    new Notice(`⏳ 生成投影片中：${selectedPdf}`);
    console.log('[slides_wrapper] 執行：', cmd);

    return new Promise((resolve) => {
        exec(cmd, { cwd: claudeLitDir, env: { ...process.env } }, (error, stdout, stderr) => {
            if (error) {
                new Notice(`❌ 投影片生成失敗：\n${stderr.trim()}`);
                console.error('[slides_wrapper]', stderr);
                resolve();
                return;
            }
            new Notice(`✓ 投影片已生成\n輸出：${outputDir}\n編輯完成後請執行 Generate Zettel`);
            console.log('[slides_wrapper]', stdout);
            resolve();
        });
    });
}

module.exports = generateSlides;
