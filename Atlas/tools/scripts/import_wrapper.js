// Atlas/tools/scripts/import_wrapper.js
// Templater user script - 觸發 import_zettel.py 並開啟匯入的 Annotation Note
// 版本: 2.0  日期: 2026-03-16
// 變更: 路徑改由 workflow-config.json 集中管理，移除硬編碼

async function importZettel(tp) {
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
        return '';
    }

    // === 從 config 取得路徑 ===
    const uvPath       = cfg.uv_executable;
    const claudeLitDir = cfg.claude_lit_dir;
    const zettelSubdir = cfg.zettel_output_subdir;
    const zettelOutput = path.join(claudeLitDir, zettelSubdir);
    const scriptPath   = path.join(vaultPath, 'Atlas/tools/import/import_zettel.py');
    const importConfig = path.join(vaultPath, 'Atlas/tools/import/config.yaml');

    // === 取得所有可匯入的 citekeys ===
    function getAvailableCitekeys(zettelDir) {
        try {
            return fs.readdirSync(zettelDir)
                .map(name => { const m = name.match(/^zettel_(.+)_\d{8}$/); return m ? m[1] : null; })
                .filter(Boolean)
                .sort();
        } catch (e) {
            console.error('[import_wrapper] getAvailableCitekeys 失敗:', e.message);
            return [];
        }
    }

    const available = getAvailableCitekeys(zettelOutput);

    if (!available || available.length === 0) {
        new Notice('找不到任何 Zettelkasten 資料夾，請先執行 Generate Zettel');
        return '';
    }

    // === 讓用戶選擇 ===
    const selected = await tp.system.suggester(
        available,
        available,
        false,
        `選擇要匯入的論文（共 ${available.length} 篇）`
    );

    if (!selected) return '';

    // === 執行 Python 腳本 ===
    return new Promise((resolve) => {
        const cmd = `"${uvPath}" run "${scriptPath}" --citekey "${selected}" --config "${importConfig}"`;

        exec(cmd, { cwd: vaultPath, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } }, (error, stdout, stderr) => {
            if (error) {
                new Notice(`❌ 匯入失敗: ${stderr.trim()}`);
                console.error('[import_wrapper]', stderr);
                resolve('');
                return;
            }

            new Notice(`✓ 成功匯入 ${selected}`);
            console.log('[import_wrapper]', stdout);

            resolve(`ACT/0️⃣Annotation/${selected}/${selected}.md`);
        });
    });
}

module.exports = importZettel;
