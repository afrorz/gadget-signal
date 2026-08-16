#!/usr/bin/env python3
"""
ogp.py — 記事ごとのOGP画像（1200×630 PNG）を生成する。

build.py から呼ばれる。フォントが見つからない環境では静かにスキップし、
ビルド自体は止めない（OGP画像が無くてもサイトは成立するため）。

単体実行するとサンプルを1枚出す:
    python3 scripts/ogp.py
"""
from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # Pillow 未導入でもビルドは通す
    Image = None

W, H = 1200, 630
BG = (251, 250, 248)
INK = (20, 24, 29)
INK_2 = (69, 78, 89)
INK_3 = (140, 145, 152)
ACCENT = (180, 71, 43)
RULE = (228, 225, 219)

# 探索順にフォント候補を並べる（Linux / macOS / Windows）
FONT_CANDIDATES = {
    "bold": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "C:/Windows/Fonts/YuGothB.ttc",
        "C:/Windows/Fonts/meiryob.ttc",
    ],
    "regular": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "C:/Windows/Fonts/YuGothR.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
    ],
}


def _font(weight: str, size: int):
    for path in FONT_CANDIDATES[weight]:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return None


def _tokenize(text: str) -> list[str]:
    """日本語は1文字ずつ、英数字の連なりは1語としてまとめる（語の途中で折り返さないため）。"""
    tokens, buf = [], ""
    for ch in text:
        if ch.isascii() and (ch.isalnum() or ch in ",.$%-+/'"):
            buf += ch
        else:
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
    if buf:
        tokens.append(buf)
    return tokens


def _wrap(draw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    """日本語は文字単位、英数は単語単位で折り返す。"""
    lines, cur = [], ""
    for ch in _tokenize(text):
        trial = cur + ch
        if draw.textlength(trial, font=font) > max_width and cur:
            # 行頭に来ると具合の悪い文字は前の行に送る
            if ch in "。、）」』】〉》・！？":
                lines.append(trial)
                cur = ""
                continue
            lines.append(cur)
            cur = ch
        else:
            cur = trial
        if len(lines) == max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and draw.textlength(lines[-1], font=font) > max_width - 40:
        lines[-1] = lines[-1][:-2] + "…"
    return lines


def render(title: str, category_label: str, site_title: str, out_path: Path) -> bool:
    """OGP画像を1枚書き出す。成功したら True。"""
    if Image is None:
        return False
    f_title = _font("bold", 52)
    f_small = _font("bold", 24)
    f_brand = _font("bold", 26)
    if not all([f_title, f_small, f_brand]):
        return False

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    pad = 88

    # 上端のアクセントバー
    d.rectangle([0, 0, W, 8], fill=ACCENT)

    # カテゴリ
    d.text((pad, 108), category_label, font=f_small, fill=ACCENT)

    # タイトル
    lines = _wrap(d, title, f_title, W - pad * 2, 4)
    y = 168
    for ln in lines:
        d.text((pad, y), ln, font=f_title, fill=INK)
        y += 76

    # 下端：罫線＋ブランド
    d.line([(pad, H - 108), (W - pad, H - 108)], fill=RULE, width=1)
    cx, cy = pad + 9, H - 66
    d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=ACCENT)
    d.text((pad + 32, H - 80), site_title.upper(), font=f_brand, fill=INK)
    label = "海外ガジェットの、まだ日本語で読めない話"
    d.text((W - pad - d.textlength(label, font=f_small), H - 76), label, font=f_small, fill=INK_3)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return True


if __name__ == "__main__":
    ok = render(
        "Honor Robot Phone 実機レビュー — 背面からジンバルが生えるスマホ、中国限定でCNY 9,999",
        "スマホ・ウェアラブル",
        "Gadget Signal",
        Path(__file__).resolve().parent.parent / "public" / "ogp" / "_sample.png",
    )
    print("生成しました" if ok else "フォントが見つからないためスキップしました")
