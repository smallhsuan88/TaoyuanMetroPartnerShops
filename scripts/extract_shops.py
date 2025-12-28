"""Extract shop data from the partner PDF into JSON.

This script uses a lightweight PDF parser built from the PDF's embedded
ToUnicode maps to decode text objects without any third-party dependencies.
It is intentionally self contained so it can run in sandboxed CI environments
where installing packages or CLI tools (pdftotext, pdfminer, etc.) is not
possible.

Usage:
    python scripts/extract_shops.py

Outputs:
    data/shops.json – an array of shop dictionaries with keys:
    id, category_main, category_sub, name, phone, city, district, address,
    offers
"""

from __future__ import annotations

import json
import re
import zlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = ROOT / "桃園市政府員工卡特約商店名單及優惠措施一覽表(1217更新).pdf"
OUTPUT_PATH = ROOT / "data" / "shops.json"


# --------------------------- PDF text utilities --------------------------- #


def parse_to_unicode(map_data: str) -> Dict[int, str]:
    """Parse a ToUnicode CMap stream into a mapping table."""

    mapping: Dict[int, str] = {}
    lines = [line.strip() for line in map_data.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.endswith("beginbfchar"):
            count = int(line.split()[0])
            for offset in range(1, count + 1):
                parts = lines[i + offset].split()
                if len(parts) < 2:
                    continue
                src = int(parts[0].strip("<>"), 16)
                dst_hex = parts[1].strip("<>")
                mapping[src] = _decode_hex(dst_hex)
            i += count
        elif line.endswith("beginbfrange"):
            count = int(line.split()[0])
            for offset in range(1, count + 1):
                parts = lines[i + offset].split()
                if len(parts) < 3:
                    continue
                start = int(parts[0].strip("<>"), 16)
                end = int(parts[1].strip("<>"), 16)
                third = parts[2]
                if third.startswith("["):
                    values = " ".join(parts[2:])
                    while not values.strip().endswith("]"):
                        i += 1
                        values += " " + lines[i + offset]
                    hex_values = re.findall(r"<(.*?)>", values)
                    for index, dst_hex in enumerate(hex_values):
                        mapping[start + index] = _decode_hex(dst_hex)
                else:
                    base = int(third.strip("<>"), 16)
                    for code in range(start, end + 1):
                        mapping[code] = chr(base + code - start)
            i += count
        i += 1
    return mapping


def _decode_hex(dst_hex: str) -> str:
    if not dst_hex:
        return ""
    try:
        # Most glyphs are encoded as 2-byte UCS-2 hex values
        return bytes.fromhex(dst_hex).decode("utf-16-be")
    except Exception:
        try:
            return bytes.fromhex(dst_hex).decode("utf-8")
        except Exception:
            return ""


def build_unicode_map(pdf_bytes: bytes) -> Dict[int, str]:
    cmap: Dict[int, str] = {}
    for match in re.finditer(rb"stream\r?\n", pdf_bytes):
        start = match.end()
        end = pdf_bytes.find(b"endstream", start)
        if end == -1:
            continue
        raw = pdf_bytes[start:end].strip()
        try:
            decompressed = zlib.decompress(raw)
        except Exception:
            continue
        if b"begincmap" in decompressed:
            cmap.update(parse_to_unicode(decompressed.decode("latin-1")))
    return cmap


def decode_bytes(data: bytes, cmap: Dict[int, str]) -> str:
    if len(data) % 2 == 0:
        chars: List[str] = []
        for i in range(0, len(data), 2):
            code = int.from_bytes(data[i : i + 2], "big")
            mapped = cmap.get(code)
            if mapped:
                chars.append(mapped)
                continue
            try:
                chars.append(data[i : i + 2].decode("utf-8"))
            except Exception:
                continue
        if chars:
            return "".join(chars)
    try:
        return data.decode("utf-8")
    except Exception:
        return data.decode("big5", errors="ignore")


def parse_literal(data: bytes) -> bytes:
    """Decode escaped sequences inside PDF literal strings."""

    escapes = {
        ord("n"): 10,
        ord("r"): 13,
        ord("t"): 9,
        ord("b"): 8,
        ord("f"): 12,
        ord("("): 40,
        ord(")"): 41,
        ord("\\"): 92,
    }
    out = bytearray()
    i = 0
    while i < len(data):
        current = data[i]
        if current == 0x5C and i + 1 < len(data):
            nxt = data[i + 1]
            if nxt in escapes:
                out.append(escapes[nxt])
                i += 2
                continue
            if 48 <= nxt <= 55:
                oct_digits = [nxt]
                j = i + 2
                while j < i + 4 and j < len(data) and 48 <= data[j] <= 55:
                    oct_digits.append(data[j])
                    j += 1
                out.append(int(bytes(oct_digits), 8))
                i = j
                continue
        out.append(current)
        i += 1
    return bytes(out)


def extract_raw_tokens(pdf_bytes: bytes, cmap: Dict[int, str]) -> List[str]:
    tokens: List[str] = []
    string_pattern = re.compile(rb"<(?:[0-9A-Fa-f]+)>|\((?:\\.|[^\\])*?\)")
    for match in re.finditer(rb"stream\r?\n", pdf_bytes):
        start = match.end()
        end = pdf_bytes.find(b"endstream", start)
        if end == -1:
            continue
        raw = pdf_bytes[start:end].strip()
        try:
            decompressed = zlib.decompress(raw)
        except Exception:
            continue
        for string_match in string_pattern.finditer(decompressed):
            raw_value = string_match.group(0)
            if raw_value.startswith(b"<"):
                decoded = decode_bytes(
                    bytes.fromhex(raw_value[1:-1].decode("latin-1")), cmap
                )
            else:
                literal = parse_literal(raw_value[1:-1])
                decoded = decode_bytes(literal, cmap)
            if decoded:
                tokens.append(decoded)
    return tokens


# ----------------------------- Post-processing --------------------------- #


@dataclass
class Shop:
    id: int
    category_main: str
    category_sub: str
    name: str
    phone: str
    city: str
    district: str
    address: str
    offers: str


CATEGORIES = {
    "生活",
    "休閒",
    "藝文",
    "教育",
    "醫療",
    "交通",
    "旅宿",
    "購物",
    "美容",
    "服務",
    "保健",
    "其他",
}

ADDRESS_BREAK = [
    "優惠",
    "折",
    "享",
    "憑",
    "送",
    "贈",
    "消費",
    "即可",
    "持",
    "出示",
    "折扣",
    "折抵",
    "使用",
    "需",
    "本優惠",
    "折價",
    "任選",
    "至",
    "於",
    "內含",
]

HEADER_FRAGMENT = {
    "桃園市政府員工卡特",
    "約商店名單及",
    "優惠措施一覽",
    "表",
    "備註：詳",
    "細優惠內容請",
    "洽各特約商店",
    "頁，共",
    "頁",
}


def is_city(token: str) -> bool:
    return bool(re.match(r".*[市縣]$", token))


def cleanup_text(value: str) -> str:
    for fragment in HEADER_FRAGMENT:
        value = value.replace(fragment, "")
    value = re.sub(r"第\d+頁，共\d+頁", "", value)
    return value.strip()


def locate_entries(tokens: List[str]) -> List[int]:
    indices: List[int] = []
    cursor = 0
    current_id = 1
    while True:
        target = str(current_id)
        found = None
        for i in range(cursor, len(tokens) - 2):
            if (
                tokens[i] == target
                and tokens[i + 1] in CATEGORIES
                and re.fullmatch(r"[\u4e00-\u9fff]{1,4}", tokens[i + 2])
            ):
                found = i
                break
        if found is None:
            break
        indices.append(found)
        cursor = found + 1
        current_id += 1
    return indices


def slice_entries(tokens: List[str]) -> List[Shop]:
    starts = locate_entries(tokens)
    starts.append(len(tokens))
    shops: List[Shop] = []

    for start, end in zip(starts[:-1], starts[1:]):
        segment = tokens[start:end]
        shop_id = int(segment[0])
        cat_main = segment[1]
        cat_sub = segment[2]

        cursor = 3
        name_phone: List[str] = []
        while cursor < len(segment) and not is_city(segment[cursor]):
            name_phone.append(segment[cursor])
            cursor += 1

        if cursor >= len(segment):
            continue

        city = segment[cursor]
        district = segment[cursor + 1] if cursor + 1 < len(segment) else ""
        cursor += 2

        name_phone_str = "".join(name_phone)
        phone_match = re.search(
            r"\(?0\d{1,2}\)?\d{3,4}-?\d{3,4}|09\d{2}-?\d{6}", name_phone_str
        )
        phone = phone_match.group(0) if phone_match else ""
        name = name_phone_str.replace(phone, "", 1) if phone else name_phone_str

        address_parts: List[str] = []
        while cursor < len(segment):
            token = segment[cursor]
            if any(marker in token for marker in ADDRESS_BREAK):
                break
            address_parts.append(token)
            cursor += 1
        address = cleanup_text("".join(address_parts))
        offers = cleanup_text("".join(segment[cursor:]))

        shops.append(
            Shop(
                id=shop_id,
                category_main=cat_main,
                category_sub=cat_sub,
                name=name.strip(),
                phone=phone,
                city=city.strip(),
                district=district.strip(),
                address=address,
                offers=offers,
            )
        )
    return shops


# ------------------------------- Main routine ----------------------------- #


def main() -> None:
    pdf_bytes = PDF_PATH.read_bytes()
    cmap = build_unicode_map(pdf_bytes)
    raw_tokens = extract_raw_tokens(pdf_bytes, cmap)
    skip_tokens = {
        "",
        " ",
        "en-US",
        "zh-TW",
        "zh-TWen-US",
        "en-USen-US",
        "(",
        ")",
    }
    cleaned_tokens = [token for token in raw_tokens if token.strip() and token not in skip_tokens]
    # Drop column headers that repeat on every page
    header = [
        "編",
        "號",
        "分",
        "類",
        "店家名稱",
        "聯絡電話",
        "縣市",
        "區域",
        "地址",
        "提供之優",
        "惠",
    ]
    normalized_tokens: List[str] = []
    i = 0
    while i < len(cleaned_tokens):
        if cleaned_tokens[i : i + len(header)] == header:
            i += len(header)
            continue
        normalized_tokens.append(cleaned_tokens[i])
        i += 1

    while normalized_tokens and not normalized_tokens[0].isdigit():
        normalized_tokens.pop(0)

    shops = slice_entries(normalized_tokens)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps([asdict(shop) for shop in shops], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Extracted {len(shops)} shops to {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
