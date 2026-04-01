#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pyyaml",
# ]
# ///
"""
import_zettel.py - Claude Lit Workflow 匯入工具

將 Claude Lit Workflow 生成的 Zettelkasten 匯入 ProgramVerse Obsidian vault。

用法：
    python import_zettel.py --citekey Adams-2020
    python import_zettel.py --batch
    python import_zettel.py --citekey Adams-2020 --dry-run

版本: 1.0
日期: 2025-11-25
"""

import argparse
import logging
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

# ============================================================
# 資料結構定義
# ============================================================

@dataclass
class Config:
    """配置資料結構"""
    # 路徑
    claude_lit_output: Path
    vault: Path
    annotation_folder: str
    pdf_folder: str
    bibtex_file: str

    # 命名
    use_at_prefix: bool = False
    folder_structure: bool = True

    # BibTeX
    bibtex_enabled: bool = True
    author_format: str = "abbreviated"
    fallback_on_missing: bool = True

    # 行為
    conflict_strategy: str = "conservative"
    migrate_old_format: bool = True
    backup_before_migrate: bool = True
    backup_folder: str = "Atlas/recycle/annotation_migration_backup"
    generate_report: bool = True

    # 日誌
    log_level: str = "INFO"
    show_progress: bool = True


@dataclass
class BibEntry:
    """BibTeX 條目資料結構"""
    citekey: str
    title: str = ""
    authors: str = ""
    year: str = ""
    doi: str = ""
    entry_type: str = ""
    raw_authors: str = ""  # 原始作者字串


@dataclass
class ZettelIndex:
    """Zettel Index 資料結構"""
    citekey: str
    title: str = ""
    authors: str = ""
    year: str = ""
    generated_date: str = ""
    card_count: int = 0
    cards: list = field(default_factory=list)
    mermaid: str = ""
    raw_content: str = ""


@dataclass
class Card:
    """卡片資料結構"""
    id: str
    title: str
    core: str
    path: str
    order: int


@dataclass
class ImportResult:
    """匯入結果"""
    citekey: str
    mode: str  # "create" | "upgrade"
    success: bool
    message: str = ""
    card_count: int = 0
    migrated: bool = False


# ============================================================
# 配置載入
# ============================================================

def load_config(config_path: Path) -> Config:
    """載入 YAML 配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    return Config(
        # 路徑
        claude_lit_output=Path(data['paths']['claude_lit_output']),
        vault=Path(data['paths']['vault']),
        annotation_folder=data['paths']['annotation_folder'],
        pdf_folder=data['paths']['pdf_folder'],
        bibtex_file=data['paths']['bibtex_file'],

        # 命名
        use_at_prefix=data.get('naming', {}).get('use_at_prefix', False),
        folder_structure=data.get('naming', {}).get('folder_structure', True),

        # BibTeX
        bibtex_enabled=data.get('bibtex', {}).get('enabled', True),
        author_format=data.get('bibtex', {}).get('author_format', 'abbreviated'),
        fallback_on_missing=data.get('bibtex', {}).get('fallback_on_missing', True),

        # 行為
        conflict_strategy=data.get('behavior', {}).get('conflict_strategy', 'conservative'),
        migrate_old_format=data.get('behavior', {}).get('migrate_old_format', True),
        backup_before_migrate=data.get('behavior', {}).get('backup_before_migrate', True),
        backup_folder=data.get('behavior', {}).get('backup_folder', 'Atlas/recycle/annotation_migration_backup'),
        generate_report=data.get('behavior', {}).get('generate_report', True),

        # 日誌
        log_level=data.get('logging', {}).get('level', 'INFO'),
        show_progress=data.get('logging', {}).get('show_progress', True),
    )


# ============================================================
# BibTeX 解析器
# ============================================================

class BibTeXParser:
    """BibTeX 解析器"""

    def __init__(self, bibtex_path: Path, author_format: str = "abbreviated"):
        self.bibtex_path = bibtex_path
        self.author_format = author_format
        self.entries: dict[str, BibEntry] = {}
        self._parse()

    def _parse(self):
        """解析 BibTeX 檔案"""
        content = self.bibtex_path.read_text(encoding='utf-8')

        # 匹配 BibTeX 條目：@type{citekey, ... }
        # 使用非貪婪匹配，處理巢狀大括號
        entry_pattern = r'@(\w+)\{([^,]+),([^@]*?)(?=\n@|\Z)'

        for match in re.finditer(entry_pattern, content, re.DOTALL):
            entry_type = match.group(1).lower()
            citekey = match.group(2).strip()
            fields_str = match.group(3)

            entry = BibEntry(citekey=citekey, entry_type=entry_type)

            # 解析欄位
            entry.title = self._extract_field(fields_str, 'title')
            entry.raw_authors = self._extract_field(fields_str, 'author')
            entry.authors = self._format_authors(entry.raw_authors)
            entry.year = self._extract_field(fields_str, 'year')
            entry.doi = self._extract_field(fields_str, 'doi')

            self.entries[citekey] = entry

    def _extract_field(self, fields_str: str, field_name: str) -> str:
        """從欄位字串中提取特定欄位值"""
        # 尋找 field = 開始的位置
        pattern = rf'{field_name}\s*=\s*'
        match = re.search(pattern, fields_str, re.IGNORECASE)
        if not match:
            return ""

        start = match.end()
        rest = fields_str[start:].strip()

        if rest.startswith('{'):
            # 處理大括號包圍的值，支援巢狀
            value = self._extract_braced_value(rest)
        elif rest.startswith('"'):
            # 處理引號包圍的值
            end = rest.find('"', 1)
            value = rest[1:end] if end > 0 else rest[1:]
        else:
            # 處理純數字或其他
            match2 = re.match(r'(\d+)', rest)
            value = match2.group(1) if match2 else ""

        # 清理 LaTeX 格式
        value = self._clean_latex(value)
        return value.strip()

    def _extract_braced_value(self, text: str) -> str:
        """提取大括號包圍的值（支援巢狀）"""
        if not text.startswith('{'):
            return ""

        depth = 0
        for i, char in enumerate(text):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return text[1:i]  # 去掉最外層的大括號
        return text[1:]  # 找不到配對，返回去掉第一個 { 的內容

    def _clean_latex(self, text: str) -> str:
        """清理 LaTeX 格式"""
        # 移除 {{ }} 包圍
        text = re.sub(r'\{\{(.+?)\}\}', r'\1', text)
        # 移除 { } 包圍
        text = re.sub(r'\{(.+?)\}', r'\1', text)
        # 處理特殊字元
        replacements = {
            r'\"a': 'ä', r'\"o': 'ö', r'\"u': 'ü',
            r'\"A': 'Ä', r'\"O': 'Ö', r'\"U': 'Ü',
            r"\'e": 'é', r"\'a": 'á', r"\'i": 'í',
            r'\ss': 'ß',
        }
        for latex, char in replacements.items():
            text = text.replace(latex, char)
        return text

    def _format_authors(self, raw_authors: str) -> str:
        """格式化作者字串"""
        if not raw_authors:
            return ""

        # 分割作者（以 " and " 分隔）
        authors = re.split(r'\s+and\s+', raw_authors)
        formatted = []

        for author in authors:
            author = author.strip()
            if not author:
                continue

            # 處理 {van Rooij} 等複合姓氏
            author = re.sub(r'\{([^}]+)\}', r'\1', author)

            if ',' in author:
                # 格式：LastName, FirstName
                parts = author.split(',', 1)
                last_name = parts[0].strip()
                first_name = parts[1].strip() if len(parts) > 1 else ""
            else:
                # 格式：FirstName LastName
                parts = author.rsplit(' ', 1)
                if len(parts) == 2:
                    first_name, last_name = parts
                else:
                    last_name = author
                    first_name = ""

            if self.author_format == "abbreviated":
                # Smith, J.
                if first_name:
                    initials = '. '.join([n[0] for n in first_name.split() if n]) + '.'
                    formatted.append(f"{last_name}, {initials}")
                else:
                    formatted.append(last_name)
            elif self.author_format == "full":
                # John Smith
                if first_name:
                    formatted.append(f"{first_name} {last_name}")
                else:
                    formatted.append(last_name)
            else:
                # original
                formatted.append(author)

        # 用 & 連接最後一位作者
        if len(formatted) > 1:
            return ', '.join(formatted[:-1]) + ', & ' + formatted[-1]
        elif formatted:
            return formatted[0]
        return ""

    def get(self, citekey: str) -> Optional[BibEntry]:
        """根據 citekey 取得條目"""
        return self.entries.get(citekey)


# ============================================================
# Zettel 解析器
# ============================================================

class ZettelParser:
    """Claude Lit Zettelkasten 解析器"""

    def __init__(self, zettel_folder: Path):
        self.zettel_folder = zettel_folder
        self.index_path = zettel_folder / "zettel_index.md"
        self.cards_folder = zettel_folder / "zettel_cards"

    def parse(self) -> Optional[ZettelIndex]:
        """解析 zettel_index.md"""
        if not self.index_path.exists():
            return None

        content = self.index_path.read_text(encoding='utf-8')

        # 分離 frontmatter 和內容
        parts = content.split('---', 2)
        if len(parts) < 3:
            return None

        frontmatter = yaml.safe_load(parts[1])
        body = parts[2]

        zettel = ZettelIndex(
            citekey=frontmatter.get('title', ''),
            title=frontmatter.get('title', ''),
            authors=frontmatter.get('authors', ''),
            year=str(frontmatter.get('year', '')),
            generated_date=frontmatter.get('generated_date', ''),
            card_count=frontmatter.get('card_count', 0),
            raw_content=content
        )

        # 提取卡片清單
        zettel.cards = self._parse_cards(body)

        # 提取 Mermaid 圖
        zettel.mermaid = self._extract_mermaid(body)

        return zettel

    def _parse_cards(self, body: str) -> list[Card]:
        """解析卡片清單"""
        cards = []
        # 匹配格式：### N. [標題](path)\n- **ID**: `id`\n- **核心**: "core"
        pattern = r'### (\d+)\. \[(.+?)\]\((.+?)\)\s*\n- \*\*ID\*\*: `(.+?)`\s*\n- \*\*核心\*\*: ["\']?(.+?)["\']?\s*(?=\n\n|\n###|\Z)'

        for match in re.finditer(pattern, body, re.DOTALL):
            cards.append(Card(
                order=int(match.group(1)),
                title=match.group(2),
                path=match.group(3),
                id=match.group(4),
                core=match.group(5).strip('"\'')
            ))

        return cards

    def _extract_mermaid(self, body: str) -> str:
        """提取 Mermaid 圖"""
        match = re.search(r'```mermaid\s*\n(.*?)```', body, re.DOTALL)
        return match.group(1).strip() if match else ""

    def get_card_files(self) -> list[Path]:
        """取得所有卡片檔案"""
        if not self.cards_folder.exists():
            return []
        return sorted(self.cards_folder.glob("*.md"))


# ============================================================
# 現有 Annotation 偵測器
# ============================================================

class AnnotationDetector:
    """偵測現有 Annotation 筆記"""

    def __init__(self, config: Config):
        self.config = config
        self.annotation_base = config.vault / config.annotation_folder

    def detect(self, citekey: str) -> tuple[str, Optional[Path]]:
        """
        偵測現有 Annotation

        返回: (mode, existing_path)
            mode: "create" | "upgrade"
            existing_path: 現有檔案路徑（若為 create 則為 None）
        """
        # 檢查舊格式：@{citekey}.md
        old_format_path = self.annotation_base / f"@{citekey}.md"
        if old_format_path.exists():
            return ("upgrade", old_format_path)

        # 檢查新格式：{citekey}/{citekey}.md
        new_format_path = self.annotation_base / citekey / f"{citekey}.md"
        if new_format_path.exists():
            return ("upgrade", new_format_path)

        # 無現有筆記
        return ("create", None)


# ============================================================
# 匯入器
# ============================================================

class ZettelImporter:
    """Zettel 匯入器"""

    def __init__(self, config: Config, bibtex: Optional[BibTeXParser] = None, dry_run: bool = False):
        self.config = config
        self.bibtex = bibtex
        self.dry_run = dry_run
        self.detector = AnnotationDetector(config)
        self.logger = logging.getLogger(__name__)

    def import_zettel(self, zettel_folder: Path) -> ImportResult:
        """匯入單一 Zettel"""
        # 解析 zettel
        parser = ZettelParser(zettel_folder)
        zettel = parser.parse()

        if not zettel:
            return ImportResult(
                citekey="unknown",
                mode="error",
                success=False,
                message=f"無法解析: {zettel_folder}"
            )

        citekey = zettel.citekey
        self.logger.info(f"處理: {citekey}")

        # 偵測模式
        mode, existing_path = self.detector.detect(citekey)
        self.logger.info(f"  模式: {mode}")

        # 取得 BibTeX 資料
        bib_entry = None
        if self.bibtex:
            bib_entry = self.bibtex.get(citekey)
            if bib_entry:
                self.logger.info(f"  BibTeX: 找到")
            else:
                self.logger.warning(f"  BibTeX: 未找到 {citekey}")

        # 執行匯入
        if mode == "create":
            return self._create_new(zettel, parser, bib_entry)
        else:
            return self._upgrade_existing(zettel, parser, bib_entry, existing_path)

    def _create_new(self, zettel: ZettelIndex, parser: ZettelParser,
                    bib_entry: Optional[BibEntry]) -> ImportResult:
        """新建模式"""
        citekey = zettel.citekey

        # 目標路徑
        target_folder = self.config.vault / self.config.annotation_folder / citekey
        target_file = target_folder / f"{citekey}.md"
        cards_folder = target_folder / "cards"

        if self.dry_run:
            self.logger.info(f"  [DRY-RUN] 將建立: {target_folder}")
            return ImportResult(citekey=citekey, mode="create", success=True,
                              message="[DRY-RUN]", card_count=zettel.card_count)

        # 建立資料夾
        target_folder.mkdir(parents=True, exist_ok=True)
        cards_folder.mkdir(exist_ok=True)

        # 生成 Annotation Note 內容
        content = self._generate_annotation_content(zettel, bib_entry)

        # 寫入檔案
        target_file.write_text(content, encoding='utf-8')
        self.logger.info(f"  建立: {target_file}")

        # 複製卡片
        copied_cards = self._copy_cards(parser, cards_folder, citekey)
        self.logger.info(f"  複製卡片: {copied_cards} 張")

        return ImportResult(
            citekey=citekey,
            mode="create",
            success=True,
            message=f"新建完成",
            card_count=copied_cards
        )

    def _upgrade_existing(self, zettel: ZettelIndex, parser: ZettelParser,
                          bib_entry: Optional[BibEntry], existing_path: Path) -> ImportResult:
        """升級模式"""
        citekey = zettel.citekey
        migrated = False

        # 目標資料夾結構
        target_folder = self.config.vault / self.config.annotation_folder / citekey
        target_file = target_folder / f"{citekey}.md"
        cards_folder = target_folder / "cards"

        # 檢查是否需要遷移（舊格式 → 新格式）
        is_old_format = existing_path.name.startswith('@')

        if self.dry_run:
            if is_old_format:
                self.logger.info(f"  [DRY-RUN] 將遷移: {existing_path.name} → {target_file}")
            else:
                self.logger.info(f"  [DRY-RUN] 將升級: {existing_path}")
            return ImportResult(citekey=citekey, mode="upgrade", success=True,
                              message="[DRY-RUN]", card_count=zettel.card_count, migrated=is_old_format)

        # 讀取現有內容
        existing_content = existing_path.read_text(encoding='utf-8')

        # 遷移舊格式
        if is_old_format and self.config.migrate_old_format:
            migrated = True

            # 備份
            if self.config.backup_before_migrate:
                backup_folder = self.config.vault / self.config.backup_folder
                backup_folder.mkdir(parents=True, exist_ok=True)
                backup_file = backup_folder / f"{existing_path.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(existing_path, backup_file)
                self.logger.info(f"  備份: {backup_file}")

            # 建立新資料夾結構
            target_folder.mkdir(parents=True, exist_ok=True)
            cards_folder.mkdir(exist_ok=True)

            # 刪除舊檔案（移動到新位置）
            existing_path.unlink()
            self.logger.info(f"  遷移: {existing_path.name} → {target_folder.name}/")
        else:
            # 確保資料夾存在
            target_folder.mkdir(parents=True, exist_ok=True)
            cards_folder.mkdir(exist_ok=True)

        # 合併內容（保守策略）
        if self.config.conflict_strategy == "conservative":
            merged_content = self._merge_content(existing_content, zettel, bib_entry)
        else:
            # force 模式：完全重新生成
            merged_content = self._generate_annotation_content(zettel, bib_entry)

        # 寫入檔案
        target_file.write_text(merged_content, encoding='utf-8')
        self.logger.info(f"  更新: {target_file}")

        # 複製卡片
        copied_cards = self._copy_cards(parser, cards_folder, citekey)
        self.logger.info(f"  複製卡片: {copied_cards} 張")

        return ImportResult(
            citekey=citekey,
            mode="upgrade",
            success=True,
            message=f"升級完成" + (" (已遷移)" if migrated else ""),
            card_count=copied_cards,
            migrated=migrated
        )

    def _generate_annotation_content(self, zettel: ZettelIndex,
                                     bib_entry: Optional[BibEntry]) -> str:
        """生成 Annotation Note 內容（Create 模式使用）"""
        # 合併 metadata（BibTeX 優先）
        title = bib_entry.title if bib_entry and bib_entry.title else zettel.title
        authors = bib_entry.authors if bib_entry and bib_entry.authors else zettel.authors
        year = bib_entry.year if bib_entry and bib_entry.year else zettel.year
        doi = bib_entry.doi if bib_entry else ""

        # 生成卡片清單
        card_list = self._generate_card_list(zettel.cards, zettel.citekey)

        # 生成 Mermaid 圖
        mermaid_section = ""
        if zettel.mermaid:
            mermaid_section = f"```mermaid\n{zettel.mermaid}\n```"

        # 新結構順序：卡片清單 → 概念網絡圖 → (人工標註區 - 新建時為空) → Connection Gear
        content = f'''---
title: "{title}"
authors: "{authors}"
year: "{year}"
doi: "{doi}"
tags: "concept/anno"
annotated: true
conn: to be created
geared: [ ]
imported_from: "claude_lit_workflow"
imported_date: "{datetime.now().strftime('%Y-%m-%d')}"
card_count: {zettel.card_count}
---

[Source pdf]({zettel.citekey}.pdf)

# 📚 卡片清單

{card_list}

# 🗺️ 概念網絡圖

{mermaid_section}

# Connection Gear⚙️

<!-- 在此添加你的 Connection Gear 筆記 -->

'''
        return content

    def _generate_card_list(self, cards: list[Card], citekey: str) -> str:
        """生成卡片清單 Markdown"""
        lines = []
        for card in cards:
            # 更新路徑指向 cards/ 子資料夾
            new_path = f"cards/{card.id}.md"
            lines.append(f"### {card.order}. [{card.title}]({new_path})")
            lines.append(f"- **ID**: `{card.id}`")
            lines.append(f'- **核心**: "{card.core}"')
            lines.append("")
        return '\n'.join(lines)

    def _merge_content(self, existing: str, zettel: ZettelIndex,
                       bib_entry: Optional[BibEntry]) -> str:
        """合併現有內容與新資料（保守策略）"""
        # 解析現有 frontmatter
        parts = existing.split('---', 2)
        if len(parts) >= 3:
            try:
                existing_fm = yaml.safe_load(parts[1])
            except:
                existing_fm = {}
            existing_body = parts[2]
        else:
            existing_fm = {}
            existing_body = existing

        # 合併 metadata（BibTeX 優先，但保留現有值如果 BibTeX 沒有）
        title = bib_entry.title if bib_entry and bib_entry.title else existing_fm.get('title', zettel.title)
        authors = bib_entry.authors if bib_entry and bib_entry.authors else existing_fm.get('authors', zettel.authors)
        year = bib_entry.year if bib_entry and bib_entry.year else existing_fm.get('year', zettel.year)
        doi = bib_entry.doi if bib_entry and bib_entry.doi else existing_fm.get('doi', '')

        # 保留現有的 conn 和 geared（重要！）
        conn_value = existing_fm.get('conn', 'to be created')
        geared_value = existing_fm.get('geared', False)
        tags_value = existing_fm.get('tags', 'concept/anno')

        # 格式化 conn（可能是字串或列表）
        if isinstance(conn_value, list):
            conn_yaml = '\n'.join([f'  - "{item}"' for item in conn_value])
            conn_yaml = f"\n{conn_yaml}"
        elif conn_value and conn_value != 'to be created':
            conn_yaml = f'"{conn_value}"'
        else:
            conn_yaml = '"to be created"'

        # 格式化 tags（可能是字串或列表）
        if isinstance(tags_value, list):
            tags_yaml = '\n'.join([f'  - "{item}"' for item in tags_value])
            tags_yaml = f"\n{tags_yaml}"
        else:
            tags_yaml = f'"{tags_value}"' if tags_value else '"concept/anno"'

        # 保留現有的人工標註內容（支援多種標題格式）
        collaborated_section = self._extract_collaborated_section(existing_body)
        connection_gear = self._extract_section(existing_body, "Connection Gear")

        # 生成新的卡片清單和 Mermaid
        card_list = self._generate_card_list(zettel.cards, zettel.citekey)
        mermaid_section = f"```mermaid\n{zettel.mermaid}\n```" if zettel.mermaid else ""

        # 新結構順序：卡片清單 → 概念網絡圖 → 人工標註 → Connection Gear
        content = f'''---
title: "{title}"
authors: "{authors}"
year: "{year}"
doi: "{doi}"
tags: {tags_yaml}
annotated: true
conn: {conn_yaml}
geared: {str(geared_value).lower() if isinstance(geared_value, bool) else geared_value}
imported_from: "claude_lit_workflow"
imported_date: "{datetime.now().strftime('%Y-%m-%d')}"
card_count: {zettel.card_count}
---

[Source pdf]({zettel.citekey}.pdf)

# 📚 卡片清單

{card_list}

# 🗺️ 概念網絡圖

{mermaid_section}
{collaborated_section}
# Connection Gear⚙️

{connection_gear if connection_gear else "<!-- 在此添加你的 Connection Gear 筆記 -->"}

'''
        return content

    def _extract_section(self, content: str, section_name: str) -> str:
        """從內容中提取特定區塊"""
        # 匹配 # Section Name 或 ## Section Name 到下一個標題或結尾
        pattern = rf'#+ {re.escape(section_name)}.*?\n(.*?)(?=\n#|\Z)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_collaborated_section(self, content: str) -> str:
        """提取整個人工標註區塊（支援多種標題格式）"""
        # 支援的標題變體：
        # - "# Collaborated Annotations by human brain🧠 and by AI 🤖"
        # - "## Collaborative Annotations by human🧠 and AI 🤖"
        # - "# Collaborated Annotations by human🧠 and by AI 🤖"
        # 終止條件：遇到任何 Connection Gear 標題（#+ Connection Gear）或其他主要區塊
        patterns = [
            r'(#+ Collaborat(?:ed|ive) Annotations.*?🧠.*?🤖.*?\n)(.*?)(?=\n#+ Connection Gear|\n# 📚|\Z)',
            r'(#+ Annotations by my brain.*?🧠.*?\n)(.*?)(?=\n#+ Connection Gear|\n# 📚|\Z)',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                # 返回完整的區塊（包含標題）
                header = match.group(1)
                body = match.group(2).strip()
                if body:  # 只有有內容時才返回
                    return f"\n{header}{body}\n\n"

        return ""

    def _copy_cards(self, parser: ZettelParser, target_folder: Path, citekey: str) -> int:
        """複製卡片檔案"""
        card_files = parser.get_card_files()
        copied = 0

        for card_file in card_files:
            target_path = target_folder / card_file.name
            if not self.dry_run:
                shutil.copy2(card_file, target_path)
            copied += 1

        return copied


# ============================================================
# 報告生成器
# ============================================================

def generate_report(results: list[ImportResult], config: Config) -> str:
    """生成匯入報告"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    # 統計
    total = len(results)
    created = sum(1 for r in results if r.mode == "create" and r.success)
    upgraded = sum(1 for r in results if r.mode == "upgrade" and r.success)
    migrated = sum(1 for r in results if r.migrated)
    failed = sum(1 for r in results if not r.success)
    total_cards = sum(r.card_count for r in results if r.success)

    report = f'''# 匯入報告 - {timestamp}

## 摘要

| 項目 | 數量 |
|------|------|
| 處理總數 | {total} |
| 新建 | {created} |
| 升級 | {upgraded} |
| 遷移 | {migrated} |
| 失敗 | {failed} |
| 卡片總數 | {total_cards} |

## 詳細

| citekey | 模式 | 卡片數 | 狀態 | 備註 |
|---------|------|--------|------|------|
'''

    for r in results:
        status = "✅" if r.success else "❌"
        note = r.message
        if r.migrated:
            note = "已遷移 " + note
        report += f"| {r.citekey} | {r.mode} | {r.card_count} | {status} | {note} |\n"

    return report


# ============================================================
# 主程式
# ============================================================

def setup_logging(level: str):
    """設定日誌"""
    import sys
    import io

    # Windows 終端 UTF-8 支援
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def find_zettel_folders(source_path: Path, citekey: Optional[str] = None) -> list[Path]:
    """尋找 Zettel 資料夾"""
    if citekey:
        # 尋找特定 citekey
        pattern = f"zettel_{citekey}_*"
        matches = list(source_path.glob(pattern))
        if not matches:
            # 嘗試直接匹配
            direct = source_path / f"zettel_{citekey}"
            if direct.exists():
                matches = [direct]
        return matches
    else:
        # 批次模式：所有 zettel_ 開頭的資料夾
        return [p for p in source_path.iterdir() if p.is_dir() and p.name.startswith('zettel_')]


def main():
    parser = argparse.ArgumentParser(
        description='Claude Lit Workflow 匯入工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
範例:
  python import_zettel.py --citekey Adams-2020
  python import_zettel.py --batch
  python import_zettel.py --citekey Adams-2020 --dry-run
        '''
    )

    parser.add_argument('-c', '--citekey', help='指定單一 citekey')
    parser.add_argument('-b', '--batch', action='store_true', help='批次處理所有')
    parser.add_argument('-n', '--dry-run', action='store_true', help='乾跑模式，不實際寫入')
    parser.add_argument('-f', '--force', action='store_true', help='強制覆蓋')
    parser.add_argument('--config', default='config.yaml', help='配置文件路徑')

    args = parser.parse_args()

    # 檢查參數
    if not args.citekey and not args.batch:
        parser.error("必須指定 --citekey 或 --batch")

    # 載入配置
    script_dir = Path(__file__).parent
    config_path = script_dir / args.config

    if not config_path.exists():
        print(f"錯誤: 找不到配置文件 {config_path}")
        sys.exit(1)

    config = load_config(config_path)

    # 覆蓋 force 選項
    if args.force:
        config.conflict_strategy = "force"

    # 設定日誌
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)

    # 載入 BibTeX
    bibtex = None
    if config.bibtex_enabled:
        bibtex_path = config.vault / config.bibtex_file
        if bibtex_path.exists():
            logger.info(f"載入 BibTeX: {bibtex_path}")
            bibtex = BibTeXParser(bibtex_path, config.author_format)
            logger.info(f"  條目數: {len(bibtex.entries)}")
        else:
            logger.warning(f"BibTeX 檔案不存在: {bibtex_path}")

    # 尋找要處理的 Zettel 資料夾
    zettel_folders = find_zettel_folders(config.claude_lit_output, args.citekey)

    if not zettel_folders:
        logger.error(f"找不到符合的 Zettel 資料夾")
        sys.exit(1)

    logger.info(f"找到 {len(zettel_folders)} 個 Zettel 資料夾")

    # 建立匯入器
    importer = ZettelImporter(config, bibtex, args.dry_run)

    # 執行匯入
    results = []
    for folder in zettel_folders:
        result = importer.import_zettel(folder)
        results.append(result)

    # 生成報告
    if config.generate_report and not args.dry_run:
        report = generate_report(results, config)
        report_folder = config.vault / "Atlas/tools/reports"
        report_folder.mkdir(parents=True, exist_ok=True)
        report_file = report_folder / f"import_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_file.write_text(report, encoding='utf-8')
        logger.info(f"報告已生成: {report_file}")

    # 輸出摘要
    success = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    logger.info(f"完成: {success} 成功, {failed} 失敗")


if __name__ == '__main__':
    main()
