#!/usr/bin/env python3
"""
Extract partner shop data from the official Taoyuan Metro partner shop PDF.

The script produces a JSON array under ``data/shops.json`` with fields:
``id``, ``category``, ``name``, ``phone``, ``city``, ``district``,
``address``, and ``offers``.
"""

from __future__ import annotations

import binascii
import json
import re
import zlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List


PDF_PATH = Path("桃園市政府員工卡特約商店名單及優惠措施一覽表(1217更新).pdf")
OUTPUT_PATH = Path("data/shops.json")


@dataclass
class Shop:
    id: int
    category: str
    name: str
    phone: str
    city: str
    district: str
    address: str
    offers: str


def _parse_cmap(data: bytes) -> Dict[int, int]:
    """Parse a minimal ToUnicode CMap and return a codepoint lookup."""

    mapping: Dict[int, int] = {}
    lines = data.decode("latin1").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.endswith("beginbfchar"):
            count = int(line.split()[0])
            for j in range(1, count + 1):
                match = re.match(r"<([0-9A-Fa-f]+)>\s+<([0-9A-Fa-f]+)>", lines[i + j].strip())
                if match:
                    mapping[int(match.group(1), 16)] = int(match.group(2), 16)
            i += count + 1
            continue

        if line.endswith("beginbfrange"):
            count = int(line.split()[0])
            for j in range(1, count + 1):
                segment = lines[i + j].strip()
                match = re.match(r"<([0-9A-Fa-f]+)>\s+<([0-9A-Fa-f]+)>\s+(.+)", segment)
                if not match:
                    continue

                start = int(match.group(1), 16)
                end = int(match.group(2), 16)
                rest = match.group(3)
                if rest.startswith("["):
                    vals = [int(x, 16) for x in re.findall(r"<([0-9A-Fa-f]+)>", rest)]
                    for offset, val in enumerate(vals):
                        mapping[start + offset] = val
                else:
                    dest = int(rest.strip("<>"), 16)
                    for code in range(start, end + 1):
                        mapping[code] = dest + (code - start)
            i += count + 1
            continue

        i += 1

    return mapping


def _decode_text_objects(pdf_bytes: bytes) -> List[str]:
    """Decode text content for each page using ToUnicode CMaps."""

    cmap_maps: Dict[int, Dict[int, int]] = {}
    for cmap_match in re.finditer(rb"/ToUnicode\s+(\d+)\s+0\s+R", pdf_bytes):
        obj_num = int(cmap_match.group(1))
        obj_re = re.compile(rb"%d 0 obj(.*?)endobj" % obj_num, re.S)
        obj_data = obj_re.search(pdf_bytes).group(1)

        stream_match = re.search(rb"stream\r?\n", obj_data)
        start = stream_match.end()
        end = obj_data.find(b"endstream", start)
        stream_data = obj_data[start:end]
        if stream_data.startswith(b"\r\n"):
            stream_data = stream_data[2:]
        elif stream_data.startswith(b"\n"):
            stream_data = stream_data[1:]
        cmap_maps[obj_num] = _parse_cmap(zlib.decompress(stream_data))

    font_cmap: Dict[int, Dict[int, int]] = {}
    for font_match in re.finditer(rb"(\d+) 0 obj\s*<</Type/Font(.*?)>>", pdf_bytes, re.S):
        obj_num = int(font_match.group(1))
        body = font_match.group(2)
        to_unicode = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", body)
        if to_unicode:
            font_cmap[obj_num] = cmap_maps.get(int(to_unicode.group(1)), {})

    page_pattern = re.compile(
        rb"(\d+) 0 obj\s*<</Type/Page(.*?)/Contents\s+(\[.*?\]|\d+\s+0\s+R)",
        re.S,
    )
    pages = []
    for page_match in page_pattern.finditer(pdf_bytes):
        contents_ref = page_match.group(3).strip()
        resources = page_match.group(2)
        fonts: Dict[str, int] = {}
        fonts_match = re.search(rb"/Font\s*<<(.*?)>>", resources, re.S)
        if fonts_match:
            for fm in re.finditer(rb"/(F\d+)\s+(\d+)\s+0\s+R", fonts_match.group(1)):
                fonts[fm.group(1).decode()] = int(fm.group(2))
        pages.append({"contents": contents_ref, "fonts": fonts})

    def decode_bytes(data: bytes, cmap: Dict[int, int] | None) -> str:
        if cmap:
            size = 2 if any(k > 0xFF for k in cmap.keys()) else 1
            chars = []
            for i in range(0, len(data), size):
                chunk = data[i : i + size]
                if len(chunk) < size:
                    continue
                code = int.from_bytes(chunk, "big")
                chars.append(chr(cmap.get(code, code)))
            return "".join(chars)
        return data.decode("latin1", errors="ignore")

    def parse_literal(literal: str) -> bytes:
        result = bytearray()
        i = 0
        while i < len(literal):
            ch = literal[i]
            if ch == "\\" and i + 1 < len(literal):
                i += 1
                esc = literal[i]
                if esc in "nrtbf":
                    result.append({"n": 10, "r": 13, "t": 9, "b": 8, "f": 12}[esc])
                elif esc in "()\\":
                    result.append(ord(esc))
                elif esc.isdigit():
                    oct_digits = esc
                    for _ in range(2):
                        if i + 1 < len(literal) and literal[i + 1].isdigit():
                            i += 1
                            oct_digits += literal[i]
                    result.append(int(oct_digits, 8))
                else:
                    result.append(ord(esc))
            else:
                result.append(ord(ch))
            i += 1
        return bytes(result)

    text_pattern = re.compile(
        r"/(F\d+)\s+[\d\.]+\s+Tf|\(([^()]*?(?:\([^)]*\)[^()]*)*)\)\s*Tj|<([0-9A-Fa-f]+)>\s*Tj|\[(.*?)\]\s*TJ",
        re.S,
    )

    pages_text: List[str] = []
    for page in pages:
        if page["contents"].startswith(b"["):
            refs = [int(x) for x in re.findall(rb"(\d+)\s+0\s+R", page["contents"])]
        else:
            refs = [int(page["contents"].split()[0])]

        stream_bytes = b""
        for ref in refs:
            obj_re = re.compile(rb"%d 0 obj(.*?)endobj" % ref, re.S)
            obj_data = obj_re.search(pdf_bytes).group(1)
            stream_match = re.search(rb"stream\r?\n", obj_data)
            start = stream_match.end()
            end = obj_data.find(b"endstream", start)
            comp = obj_data[start:end]
            if comp.startswith(b"\r\n"):
                comp = comp[2:]
            elif comp.startswith(b"\n"):
                comp = comp[1:]
            stream_bytes += zlib.decompress(comp)

        content = stream_bytes.decode("latin1")
        current_font = None
        page_text: List[str] = []

        for match in text_pattern.finditer(content):
            if match.group(1):
                current_font = match.group(1)
                continue

            cmap = font_cmap.get(page["fonts"].get(current_font, 0), {}) if current_font else None
            if match.group(2) is not None:
                data = parse_literal(match.group(2))
                page_text.append(decode_bytes(data, cmap))
            elif match.group(3) is not None:
                data = binascii.unhexlify(match.group(3))
                page_text.append(decode_bytes(data, cmap))
            elif match.group(4) is not None:
                for part in re.findall(r"<([0-9A-Fa-f]+)>|\(([^()]*?(?:\([^)]*\)[^()]*)*)\)", match.group(4)):
                    hex_part, lit_part = part
                    data = binascii.unhexlify(hex_part) if hex_part else parse_literal(lit_part)
                    page_text.append(decode_bytes(data, cmap))

        pages_text.append("".join(page_text))

    return pages_text


def _collect_entries(pages_text: Iterable[str]) -> List[str]:
    bodies = [
        text.split("提供之優惠", 1)[1] if "提供之優惠" in text else text for text in pages_text
    ]
    combined = re.sub(r"\s+", " ", " ".join(bodies)).strip()

    entries: List[str] = []
    idx = 0
    expected = 1
    while True:
        current = re.search(rf"\b{expected}\s", combined[idx:])
        if not current:
            break

        start = idx + current.start()
        next_match = re.search(rf"\b{expected + 1}\s", combined[start + len(str(expected)) + 1 :])
        if next_match:
            end = start + len(str(expected)) + 1 + next_match.start()
        else:
            end = len(combined)

        entries.append(combined[start:end].strip())
        idx = end
        expected += 1

    return entries


def _parse_entries(entries: Iterable[str]) -> List[Shop]:
    phone_pattern = re.compile(r"(?:\(0?\d+\)|0?\d{2,4}|09\d{2}|0800)[\d#\-]+")
    shops: List[Shop] = []

    for entry in entries:
        entry = entry.strip()
        shop_id, rest = entry.split(" ", 1)
        category, rest = rest.split(" ", 1)

        city_match = re.search(r"([\u4e00-\u9fa5]{2,3}[市縣])\s+([\u4e00-\u9fa5]{1,3}[區市鎮鄉])", rest)
        if not city_match:
            raise ValueError(f"Unable to parse city/district for entry: {entry}")

        city, district = city_match.group(1), city_match.group(2)
        before_city = rest[: city_match.start()].strip()
        after_district = rest[city_match.end() :].strip()

        phone_match = phone_pattern.search(before_city)
        if phone_match:
            name = before_city[: phone_match.start()].strip()
            phone = before_city[phone_match.start() :].strip()
        else:
            name = before_city
            phone = ""

        if " " in after_district:
            address, offers = after_district.split(" ", 1)
        else:
            address, offers = after_district, ""

        shops.append(
            Shop(
                id=int(shop_id),
                category=category,
                name=name,
                phone=phone,
                city=city,
                district=district,
                address=address,
                offers=offers.strip(),
            )
        )

    return shops


def main() -> None:
    if not PDF_PATH.exists():
        raise SystemExit(f"Missing PDF file at {PDF_PATH}")

    pdf_bytes = PDF_PATH.read_bytes()
    pages_text = _decode_text_objects(pdf_bytes)
    entries = _collect_entries(pages_text)
    shops = _parse_entries(entries)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps([asdict(s) for s in shops], ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {len(shops)} shops to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
