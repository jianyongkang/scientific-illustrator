#!/usr/bin/env python3
"""Parse a Master SVG once into an immutable Illustrator playback geometry cache.

The cache is intentionally stdlib-only and targets solid-fill/stroke scientific SVGs.
It normalizes supported SVG primitives and path commands into native path/text atoms,
preserves document paint order, and writes deterministic batch JSON files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

PARSER_VERSION = "2.0.0"
KAPPA = 0.5522847498307936
NUM_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
TOKEN_RE = re.compile(r"[AaCcHhLlMmQqSsTtVvZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
TRANSFORM_RE = re.compile(r"([A-Za-z]+)\s*\(([^)]*)\)")
STYLE_SPLIT_RE = re.compile(r"\s*;\s*")
CSS_COLOR_NAMES = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0),
    "green": (0, 128, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0),
    "cyan": (0, 255, 255), "aqua": (0, 255, 255), "magenta": (255, 0, 255),
    "fuchsia": (255, 0, 255), "gray": (128, 128, 128), "grey": (128, 128, 128),
    "silver": (192, 192, 192), "maroon": (128, 0, 0), "olive": (128, 128, 0),
    "lime": (0, 255, 0), "teal": (0, 128, 128), "navy": (0, 0, 128),
    "purple": (128, 0, 128), "orange": (255, 165, 0), "transparent": None,
}
NON_RENDERED = {"defs", "metadata", "title", "desc", "clipPath", "mask", "marker", "symbol"}
UNSUPPORTED_VISIBLE = {
    "image", "foreignObject", "use", "pattern", "linearGradient", "radialGradient",
    "meshgradient", "filter", "script", "switch", "textPath",
}
PRESENTATION_ATTRS = {
    "fill", "fill-opacity", "fill-rule", "stroke", "stroke-opacity", "stroke-width",
    "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "opacity", "display",
    "visibility", "font-family", "font-size", "font-weight", "font-style", "text-anchor",
}


def lname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_number(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    m = NUM_RE.search(str(value))
    return float(m.group(0)) if m else default


def parse_points(value: str) -> list[tuple[float, float]]:
    nums = [float(x) for x in NUM_RE.findall(value or "")]
    if len(nums) % 2:
        raise ValueError("points attribute contains an odd number of coordinates")
    return list(zip(nums[0::2], nums[1::2]))


Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def mmul(m1: Matrix, m2: Matrix) -> Matrix:
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def mapply(m: Matrix, p: tuple[float, float]) -> tuple[float, float]:
    a, b, c, d, e, f = m
    x, y = p
    return (a * x + c * y + e, b * x + d * y + f)


def matrix_scale(m: Matrix) -> float:
    a, b, c, d, _, _ = m
    sx = math.hypot(a, b)
    sy = math.hypot(c, d)
    if sx <= 0 and sy <= 0:
        return 1.0
    if sx <= 0:
        return sy
    if sy <= 0:
        return sx
    return math.sqrt(sx * sy)


def parse_transform(value: str | None) -> Matrix:
    if not value:
        return IDENTITY
    out = IDENTITY
    for name, raw_args in TRANSFORM_RE.findall(value):
        nums = [float(x) for x in NUM_RE.findall(raw_args)]
        name = name.lower()
        if name == "matrix" and len(nums) == 6:
            t: Matrix = tuple(nums)  # type: ignore[assignment]
        elif name == "translate" and nums:
            t = (1, 0, 0, 1, nums[0], nums[1] if len(nums) > 1 else 0)
        elif name == "scale" and nums:
            sy = nums[1] if len(nums) > 1 else nums[0]
            t = (nums[0], 0, 0, sy, 0, 0)
        elif name == "rotate" and nums:
            ang = math.radians(nums[0])
            c, s = math.cos(ang), math.sin(ang)
            r: Matrix = (c, s, -s, c, 0, 0)
            if len(nums) >= 3:
                cx, cy = nums[1], nums[2]
                t = mmul(mmul((1, 0, 0, 1, cx, cy), r), (1, 0, 0, 1, -cx, -cy))
            else:
                t = r
        elif name == "skewx" and nums:
            t = (1, 0, math.tan(math.radians(nums[0])), 1, 0, 0)
        elif name == "skewy" and nums:
            t = (1, math.tan(math.radians(nums[0])), 0, 1, 0, 0)
        else:
            raise ValueError(f"unsupported or malformed transform: {name}({raw_args})")
        out = mmul(out, t)
    return out


def parse_style_attr(value: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    if not value:
        return result
    for part in STYLE_SPLIT_RE.split(value.strip()):
        if not part or ":" not in part:
            continue
        key, val = part.split(":", 1)
        result[key.strip()] = val.strip()
    return result


def parse_css_rules(root: ET.Element) -> list[tuple[str, dict[str, str]]]:
    rules: list[tuple[str, dict[str, str]]] = []
    for node in root.iter():
        if lname(node.tag) != "style" or not node.text:
            continue
        text = re.sub(r"/\*.*?\*/", "", node.text, flags=re.S)
        for selector_blob, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
            props = parse_style_attr(body)
            for selector in selector_blob.split(","):
                selector = selector.strip()
                if selector and re.fullmatch(r"(?:[A-Za-z][\w-]*)?(?:\.[\w-]+|#[\w-]+)?", selector):
                    rules.append((selector, props))
    return rules


def css_match(elem: ET.Element, selector: str) -> bool:
    tag = lname(elem.tag)
    elem_id = elem.attrib.get("id", "")
    classes = set(elem.attrib.get("class", "").split())
    if selector.startswith("."):
        return selector[1:] in classes
    if selector.startswith("#"):
        return selector[1:] == elem_id
    if "." in selector:
        t, c = selector.split(".", 1); return tag == t and c in classes
    if "#" in selector:
        t, i = selector.split("#", 1); return tag == t and i == elem_id
    return tag == selector


def merged_style(parent: dict[str, str], elem: ET.Element, css_rules: list[tuple[str, dict[str, str]]] | None = None) -> dict[str, str]:
    style = dict(parent)
    for selector, props in (css_rules or []):
        if css_match(elem, selector):
            style.update(props)
    for key in PRESENTATION_ATTRS:
        if key in elem.attrib:
            style[key] = elem.attrib[key]
    style.update(parse_style_attr(elem.attrib.get("style")))
    parent_opacity = float(parent.get("__effective_opacity", "1"))
    own_opacity = parse_number(style.get("opacity"), 1.0)
    style["__effective_opacity"] = str(max(0.0, min(1.0, parent_opacity * own_opacity)))
    return style


def color_to_rgb(value: str | None, *, default_black: bool = False) -> list[int] | None:
    if value is None or value == "":
        return [0, 0, 0] if default_black else None
    s = value.strip().lower()
    if s == "none":
        return None
    if s.startswith("url(") or s.startswith("var(") or s == "currentcolor":
        raise ValueError(f"unsupported paint value: {value}")
    if s in CSS_COLOR_NAMES:
        rgb = CSS_COLOR_NAMES[s]
        return list(rgb) if rgb is not None else None
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            return [int(ch * 2, 16) for ch in h]
        if len(h) == 6:
            return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    m = re.fullmatch(r"rgba?\(([^)]*)\)", s)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        if len(parts) >= 3:
            out = []
            for p in parts[:3]:
                if p.endswith("%"):
                    out.append(round(float(p[:-1]) * 2.55))
                else:
                    out.append(round(float(p)))
            return [max(0, min(255, x)) for x in out]
    raise ValueError(f"unsupported color: {value}")


def style_payload(style: dict[str, str], transform: Matrix, *, text: bool = False) -> dict:
    effective_opacity = float(style.get("__effective_opacity", "1"))
    fill_opacity = parse_number(style.get("fill-opacity"), 1.0)
    stroke_opacity = parse_number(style.get("stroke-opacity"), 1.0)
    fill = color_to_rgb(style.get("fill"), default_black=True)
    stroke = color_to_rgb(style.get("stroke"), default_black=False)
    if text and fill is None:
        fill = [0, 0, 0]
    return {
        "fill_rgb": fill,
        "stroke_rgb": stroke,
        "stroke_width": max(0.0, parse_number(style.get("stroke-width"), 1.0) * matrix_scale(transform)),
        "opacity": effective_opacity,
        "fill_opacity": max(0.0, min(1.0, fill_opacity)),
        "stroke_opacity": max(0.0, min(1.0, stroke_opacity)),
        "fill_rule": style.get("fill-rule", "nonzero").lower(),
        "linecap": style.get("stroke-linecap", "butt").lower(),
        "linejoin": style.get("stroke-linejoin", "miter").lower(),
    }


@dataclass
class SubpathBuilder:
    points: list[dict]
    closed: bool = False

    @classmethod
    def start(cls, p: tuple[float, float]) -> "SubpathBuilder":
        return cls(points=[{"anchor": p, "left": p, "right": p}])

    @property
    def current(self) -> tuple[float, float]:
        return tuple(self.points[-1]["anchor"])  # type: ignore[return-value]

    @property
    def first(self) -> tuple[float, float]:
        return tuple(self.points[0]["anchor"])  # type: ignore[return-value]

    def line_to(self, p: tuple[float, float]) -> None:
        self.points[-1]["right"] = self.current
        self.points.append({"anchor": p, "left": p, "right": p})

    def cubic_to(self, c1: tuple[float, float], c2: tuple[float, float], p: tuple[float, float]) -> None:
        self.points[-1]["right"] = c1
        self.points.append({"anchor": p, "left": c2, "right": p})


def reflect(p: tuple[float, float], around: tuple[float, float]) -> tuple[float, float]:
    return (2 * around[0] - p[0], 2 * around[1] - p[1])


def vec_angle(u: tuple[float, float], v: tuple[float, float]) -> float:
    dot = u[0] * v[0] + u[1] * v[1]
    det = u[0] * v[1] - u[1] * v[0]
    return math.atan2(det, dot)


def arc_to_cubics(
    p0: tuple[float, float], rx: float, ry: float, angle_deg: float,
    large_arc: int, sweep: int, p1: tuple[float, float],
) -> list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]]:
    if p0 == p1:
        return []
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0:
        return [(p0, p1, p1)]
    phi = math.radians(angle_deg % 360.0)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)
    dx2 = (p0[0] - p1[0]) / 2.0
    dy2 = (p0[1] - p1[1]) / 2.0
    x1p = cos_phi * dx2 + sin_phi * dy2
    y1p = -sin_phi * dx2 + cos_phi * dy2
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx *= s
        ry *= s
    rx2, ry2 = rx * rx, ry * ry
    num = max(0.0, rx2 * ry2 - rx2 * y1p * y1p - ry2 * x1p * x1p)
    den = rx2 * y1p * y1p + ry2 * x1p * x1p
    coef = 0.0 if den == 0 else math.sqrt(num / den)
    if bool(large_arc) == bool(sweep):
        coef = -coef
    cxp = coef * (rx * y1p / ry)
    cyp = coef * (-ry * x1p / rx)
    cx = cos_phi * cxp - sin_phi * cyp + (p0[0] + p1[0]) / 2.0
    cy = sin_phi * cxp + cos_phi * cyp + (p0[1] + p1[1]) / 2.0
    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    theta1 = vec_angle((1, 0), (ux, uy))
    delta = vec_angle((ux, uy), (vx, vy))
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    elif sweep and delta < 0:
        delta += 2 * math.pi
    segments = max(1, int(math.ceil(abs(delta) / (math.pi / 2))))
    step = delta / segments

    def point(theta: float) -> tuple[float, float]:
        ct, st = math.cos(theta), math.sin(theta)
        return (
            cx + rx * cos_phi * ct - ry * sin_phi * st,
            cy + rx * sin_phi * ct + ry * cos_phi * st,
        )

    def deriv(theta: float) -> tuple[float, float]:
        ct, st = math.cos(theta), math.sin(theta)
        return (
            -rx * cos_phi * st - ry * sin_phi * ct,
            -rx * sin_phi * st + ry * cos_phi * ct,
        )

    out = []
    for i in range(segments):
        t0 = theta1 + i * step
        t1 = t0 + step
        p_start = point(t0)
        p_end = point(t1)
        d0, d1 = deriv(t0), deriv(t1)
        alpha = 4.0 / 3.0 * math.tan(step / 4.0)
        c1 = (p_start[0] + alpha * d0[0], p_start[1] + alpha * d0[1])
        c2 = (p_end[0] - alpha * d1[0], p_end[1] - alpha * d1[1])
        out.append((c1, c2, p_end))
    return out


def tokenize_path(d: str) -> list[str]:
    return TOKEN_RE.findall(d or "")


def path_to_subpaths(d: str) -> list[SubpathBuilder]:
    tokens = tokenize_path(d)
    i = 0
    cmd: str | None = None
    current = (0.0, 0.0)
    current_sub: SubpathBuilder | None = None
    subpaths: list[SubpathBuilder] = []
    last_cubic_c2: tuple[float, float] | None = None
    last_quad_c: tuple[float, float] | None = None
    last_cmd = ""

    def is_cmd(tok: str) -> bool:
        return len(tok) == 1 and tok.isalpha()

    def need(n: int) -> list[float]:
        nonlocal i
        if i + n > len(tokens) or any(is_cmd(t) for t in tokens[i:i + n]):
            raise ValueError(f"malformed SVG path near token {i}: command {cmd}")
        vals = [float(x) for x in tokens[i:i + n]]
        i += n
        return vals

    def abspt(x: float, y: float, rel: bool) -> tuple[float, float]:
        return (current[0] + x, current[1] + y) if rel else (x, y)

    while i < len(tokens):
        if is_cmd(tokens[i]):
            cmd = tokens[i]
            i += 1
        if cmd is None:
            raise ValueError("SVG path data must begin with a command")
        rel = cmd.islower()
        op = cmd.upper()
        if op == "Z":
            if current_sub:
                current_sub.closed = True
                current = current_sub.first
            last_cubic_c2 = None
            last_quad_c = None
            last_cmd = op
            cmd = None
            continue
        if op == "M":
            x, y = need(2)
            current = abspt(x, y, rel)
            current_sub = SubpathBuilder.start(current)
            subpaths.append(current_sub)
            last_cubic_c2 = None
            last_quad_c = None
            last_cmd = op
            cmd = "l" if rel else "L"
            continue
        if current_sub is None:
            raise ValueError(f"path command {op} encountered before moveto")
        if op == "L":
            x, y = need(2)
            p = abspt(x, y, rel)
            current_sub.line_to(p); current = p
            last_cubic_c2 = last_quad_c = None
        elif op == "H":
            x = need(1)[0]
            p = (current[0] + x, current[1]) if rel else (x, current[1])
            current_sub.line_to(p); current = p
            last_cubic_c2 = last_quad_c = None
        elif op == "V":
            y = need(1)[0]
            p = (current[0], current[1] + y) if rel else (current[0], y)
            current_sub.line_to(p); current = p
            last_cubic_c2 = last_quad_c = None
        elif op == "C":
            x1, y1, x2, y2, x, y = need(6)
            c1 = abspt(x1, y1, rel); c2 = abspt(x2, y2, rel); p = abspt(x, y, rel)
            current_sub.cubic_to(c1, c2, p); current = p
            last_cubic_c2, last_quad_c = c2, None
        elif op == "S":
            x2, y2, x, y = need(4)
            c1 = reflect(last_cubic_c2, current) if last_cmd in {"C", "S"} and last_cubic_c2 else current
            c2 = abspt(x2, y2, rel); p = abspt(x, y, rel)
            current_sub.cubic_to(c1, c2, p); current = p
            last_cubic_c2, last_quad_c = c2, None
        elif op == "Q":
            qx, qy, x, y = need(4)
            q = abspt(qx, qy, rel); p = abspt(x, y, rel)
            c1 = (current[0] + 2 / 3 * (q[0] - current[0]), current[1] + 2 / 3 * (q[1] - current[1]))
            c2 = (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]))
            current_sub.cubic_to(c1, c2, p); current = p
            last_quad_c, last_cubic_c2 = q, None
        elif op == "T":
            x, y = need(2)
            q = reflect(last_quad_c, current) if last_cmd in {"Q", "T"} and last_quad_c else current
            p = abspt(x, y, rel)
            c1 = (current[0] + 2 / 3 * (q[0] - current[0]), current[1] + 2 / 3 * (q[1] - current[1]))
            c2 = (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]))
            current_sub.cubic_to(c1, c2, p); current = p
            last_quad_c, last_cubic_c2 = q, None
        elif op == "A":
            rx, ry, rot, large, sweep, x, y = need(7)
            p = abspt(x, y, rel)
            cubics = arc_to_cubics(current, rx, ry, rot, int(large != 0), int(sweep != 0), p)
            if not cubics:
                current = p
            else:
                for c1, c2, end in cubics:
                    current_sub.cubic_to(c1, c2, end)
                    current = end
            last_cubic_c2 = cubics[-1][1] if cubics else None
            last_quad_c = None
        else:
            raise ValueError(f"unsupported path command: {cmd}")
        last_cmd = op
    return subpaths


def transform_subpaths(subpaths: Iterable[SubpathBuilder], m: Matrix) -> list[dict]:
    out = []
    for sp in subpaths:
        if sp.closed and len(sp.points) > 1:
            first = tuple(sp.points[0]["anchor"])
            last = tuple(sp.points[-1]["anchor"])
            if math.hypot(first[0] - last[0], first[1] - last[1]) < 1e-8:
                sp.points[0]["left"] = sp.points[-1]["left"]
                sp.points.pop()
        points = []
        for p in sp.points:
            points.append({
                "anchor": [round(v, 6) for v in mapply(m, tuple(p["anchor"]))],
                "left": [round(v, 6) for v in mapply(m, tuple(p["left"]))],
                "right": [round(v, 6) for v in mapply(m, tuple(p["right"]))],
            })
        if len(points) >= 2:
            out.append({"closed": bool(sp.closed), "points": points})
    return out


def primitive_subpaths(elem: ET.Element) -> list[SubpathBuilder]:
    name = lname(elem.tag)
    if name == "path":
        return path_to_subpaths(elem.attrib.get("d", ""))
    if name == "line":
        p1 = (parse_number(elem.attrib.get("x1")), parse_number(elem.attrib.get("y1")))
        p2 = (parse_number(elem.attrib.get("x2")), parse_number(elem.attrib.get("y2")))
        sp = SubpathBuilder.start(p1); sp.line_to(p2); return [sp]
    if name in {"polyline", "polygon"}:
        pts = parse_points(elem.attrib.get("points", ""))
        if len(pts) < 2:
            return []
        sp = SubpathBuilder.start(pts[0])
        for p in pts[1:]: sp.line_to(p)
        sp.closed = name == "polygon"
        return [sp]
    if name == "rect":
        x = parse_number(elem.attrib.get("x")); y = parse_number(elem.attrib.get("y"))
        w = parse_number(elem.attrib.get("width")); h = parse_number(elem.attrib.get("height"))
        if w <= 0 or h <= 0: return []
        rx = max(0.0, parse_number(elem.attrib.get("rx"), 0.0)); ry = max(0.0, parse_number(elem.attrib.get("ry"), 0.0))
        if rx and not ry: ry = rx
        if ry and not rx: rx = ry
        rx, ry = min(rx, w / 2), min(ry, h / 2)
        if rx == 0 and ry == 0:
            sp = SubpathBuilder.start((x, y)); sp.line_to((x + w, y)); sp.line_to((x + w, y + h)); sp.line_to((x, y + h)); sp.closed = True; return [sp]
        sp = SubpathBuilder.start((x + rx, y))
        sp.line_to((x + w - rx, y))
        for c1, c2, p in arc_to_cubics(sp.current, rx, ry, 0, 0, 1, (x + w, y + ry)): sp.cubic_to(c1, c2, p)
        sp.line_to((x + w, y + h - ry))
        for c1, c2, p in arc_to_cubics(sp.current, rx, ry, 0, 0, 1, (x + w - rx, y + h)): sp.cubic_to(c1, c2, p)
        sp.line_to((x + rx, y + h))
        for c1, c2, p in arc_to_cubics(sp.current, rx, ry, 0, 0, 1, (x, y + h - ry)): sp.cubic_to(c1, c2, p)
        sp.line_to((x, y + ry))
        for c1, c2, p in arc_to_cubics(sp.current, rx, ry, 0, 0, 1, (x + rx, y)): sp.cubic_to(c1, c2, p)
        sp.closed = True; return [sp]
    if name in {"circle", "ellipse"}:
        cx = parse_number(elem.attrib.get("cx")); cy = parse_number(elem.attrib.get("cy"))
        rx = parse_number(elem.attrib.get("r")) if name == "circle" else parse_number(elem.attrib.get("rx"))
        ry = rx if name == "circle" else parse_number(elem.attrib.get("ry"))
        if rx <= 0 or ry <= 0: return []
        sp = SubpathBuilder.start((cx + rx, cy))
        sp.cubic_to((cx + rx, cy + KAPPA * ry), (cx + KAPPA * rx, cy + ry), (cx, cy + ry))
        sp.cubic_to((cx - KAPPA * rx, cy + ry), (cx - rx, cy + KAPPA * ry), (cx - rx, cy))
        sp.cubic_to((cx - rx, cy - KAPPA * ry), (cx - KAPPA * rx, cy - ry), (cx, cy - ry))
        sp.cubic_to((cx + KAPPA * rx, cy - ry), (cx + rx, cy - KAPPA * ry), (cx + rx, cy))
        sp.closed = True; return [sp]
    raise ValueError(f"unsupported primitive: {name}")


def text_rotation(m: Matrix) -> float:
    a, b, _, _, _, _ = m
    return math.degrees(math.atan2(b, a)) if (a or b) else 0.0


def extract_text_atoms(elem: ET.Element, style: dict[str, str], transform: Matrix, source_id: str, css_rules: list[tuple[str, dict[str, str]]] | None = None) -> list[dict]:
    atoms = []
    base_x = parse_number(elem.attrib.get("x"), 0.0)
    base_y = parse_number(elem.attrib.get("y"), 0.0)
    children = [c for c in list(elem) if lname(c.tag) == "tspan"]
    runs: list[tuple[ET.Element, str, float, float, dict[str, str], Matrix]] = []
    if children:
        cursor_x, cursor_y = base_x, base_y
        if elem.text and elem.text.strip():
            runs.append((elem, elem.text, cursor_x, cursor_y, style, transform))
        for child in children:
            cstyle = merged_style(style, child, css_rules)
            cm = mmul(transform, parse_transform(child.attrib.get("transform")))
            if "x" in child.attrib: cursor_x = parse_number(child.attrib.get("x"), cursor_x)
            if "y" in child.attrib: cursor_y = parse_number(child.attrib.get("y"), cursor_y)
            cursor_x += parse_number(child.attrib.get("dx"), 0.0)
            cursor_y += parse_number(child.attrib.get("dy"), 0.0)
            txt = "".join(child.itertext())
            if txt:
                runs.append((child, txt, cursor_x, cursor_y, cstyle, cm))
    else:
        txt = "".join(elem.itertext())
        if txt:
            runs.append((elem, txt, base_x, base_y, style, transform))

    for idx, (run_elem, text, x, y, run_style, run_m) in enumerate(runs):
        if not text:
            continue
        p = mapply(run_m, (x, y))
        font_size = parse_number(run_style.get("font-size"), 16.0) * matrix_scale(run_m)
        atoms.append({
            "type": "text",
            "source_id": run_elem.attrib.get("id") or source_id,
            "text": text,
            "position": [round(p[0], 6), round(p[1], 6)],
            "rotation": round(text_rotation(run_m), 6),
            "font_size": round(max(0.1, font_size), 6),
            "font_family": run_style.get("font-family", "Arial").strip(" '\"") or "Arial",
            "font_weight": run_style.get("font-weight", "normal"),
            "font_style": run_style.get("font-style", "normal"),
            "text_anchor": run_style.get("text-anchor", "start").lower(),
            "style": style_payload(run_style, run_m, text=True),
            "run_index": idx,
        })
    return atoms


def build_atoms(root: ET.Element) -> tuple[list[dict], list[str]]:
    atoms: list[dict] = []
    warnings: list[str] = []
    seq = 0
    css_rules = parse_css_rules(root)

    def walk(elem: ET.Element, parent_style: dict[str, str], parent_m: Matrix, group_path: list[str]) -> None:
        nonlocal seq
        name = lname(elem.tag)
        style = merged_style(parent_style, elem, css_rules)
        display = style.get("display", "").lower()
        visibility = style.get("visibility", "").lower()
        if display == "none" or visibility == "hidden":
            return
        m = mmul(parent_m, parse_transform(elem.attrib.get("transform")))
        elem_id = elem.attrib.get("id", "")
        next_group = group_path + ([elem_id] if name == "g" and elem_id else [])
        if name in NON_RENDERED:
            return
        if name in UNSUPPORTED_VISIBLE:
            raise ValueError(f"unsupported visible SVG element for native playback: <{name}>")
        if name in {"svg", "g"}:
            for child in list(elem):
                walk(child, style, m, next_group)
            return
        if name == "text":
            for atom in extract_text_atoms(elem, style, m, elem_id, css_rules):
                seq += 1
                atom["id"] = f"atom_{seq:06d}"
                atom["paint_index"] = seq - 1
                atom["group_path"] = next_group
                atoms.append(atom)
            return
        if name in {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}:
            subpaths = transform_subpaths(primitive_subpaths(elem), m)
            if not subpaths:
                warnings.append(f"empty_or_degenerate:{elem_id or name}")
                return
            payload_style = style_payload(style, m, text=False)
            if len(subpaths) > 1 and payload_style.get("fill_rgb") is not None:
                raise ValueError(f"filled multi-subpath path is not fidelity-safe for native playback; split it into explicit solid shapes: {elem_id or name}")
            seq += 1
            atoms.append({
                "id": f"atom_{seq:06d}",
                "type": "path",
                "source_id": elem_id,
                "paint_index": seq - 1,
                "group_path": next_group,
                "subpaths": subpaths,
                "style": payload_style,
            })
            return
        if list(elem) or (elem.text and elem.text.strip()):
            raise ValueError(f"unsupported SVG element for native playback: <{name}>")

    walk(root, {}, IDENTITY, [])
    return atoms, warnings


def atom_complexity(atom: dict) -> int:
    if atom["type"] == "text":
        return max(1, len(atom.get("text", "")) // 16)
    return sum(len(sp.get("points", [])) for sp in atom.get("subpaths", []))


def make_batches(atoms: list[dict], batch_size: int, complex_threshold: int) -> list[list[dict]]:
    if not 20 <= batch_size <= 50:
        raise ValueError("batch size must be between 20 and 50")
    batches: list[list[dict]] = []
    current: list[dict] = []
    for atom in atoms:
        if atom_complexity(atom) >= complex_threshold:
            if current:
                batches.append(current); current = []
            batches.append([atom])
            continue
        current.append(atom)
        if len(current) >= batch_size:
            batches.append(current); current = []
    if current:
        if batches and len(current) < 20 and len(batches[-1]) > 1 and len(batches[-1]) + len(current) <= 50:
            batches[-1].extend(current)
        else:
            batches.append(current)
    return batches


def read_viewbox(root: ET.Element) -> tuple[float, float, float, float]:
    raw = root.attrib.get("viewBox")
    if not raw:
        raise ValueError("Master SVG must have viewBox before geometry caching")
    nums = [float(x) for x in NUM_RE.findall(raw)]
    if len(nums) != 4 or nums[2] <= 0 or nums[3] <= 0:
        raise ValueError("invalid SVG viewBox")
    return tuple(nums)  # type: ignore[return-value]


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse one Master SVG into immutable native Illustrator playback batches.")
    ap.add_argument("master_svg")
    ap.add_argument("--cache-dir", help="Output cache directory; default: <master parent>/cache")
    ap.add_argument("--batch-size", type=int, default=30, help="Ordinary atom batch size, 20-50 (default 30)")
    ap.add_argument("--complex-threshold", type=int, default=180, help="Point-count threshold for singleton complex atoms")
    ap.add_argument("--replace", action="store_true", help="Replace an existing cache directory")
    args = ap.parse_args()

    master = Path(args.master_svg).expanduser().resolve()
    if not master.exists():
        print(f"CACHE_FAIL|reason=missing_master|path={master}")
        return 1
    cache_dir = Path(args.cache_dir).expanduser().resolve() if args.cache_dir else master.parent / "cache"
    if cache_dir.exists():
        if not args.replace:
            print(f"CACHE_FAIL|reason=cache_exists|path={cache_dir}|hint=use_--replace_after_master_change")
            return 1
        shutil.rmtree(cache_dir)
    cache_dir.mkdir(parents=True)

    try:
        root = ET.parse(master).getroot()
        if lname(root.tag) != "svg":
            raise ValueError("root element is not <svg>")
        viewbox = read_viewbox(root)
        source_sha = sha256_file(master)
        atoms, warnings = build_atoms(root)
        if not atoms:
            raise ValueError("Master SVG produced zero drawable atoms")
        batches = make_batches(atoms, args.batch_size, args.complex_threshold)
    except (ET.ParseError, ValueError) as exc:
        shutil.rmtree(cache_dir, ignore_errors=True)
        print(f"CACHE_FAIL|reason=parse_or_contract|detail={str(exc).replace('|', '/')}|master={master}")
        return 1

    cache_seed = json.dumps({
        "parser": PARSER_VERSION,
        "source_sha256": source_sha,
        "viewbox": viewbox,
        "batch_size": args.batch_size,
        "complex_threshold": args.complex_threshold,
        "atom_ids": [a["id"] for a in atoms],
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    cache_id = hashlib.sha256(cache_seed).hexdigest()

    batch_meta = []
    for index, batch_atoms in enumerate(batches):
        file_name = f"batches/batch_{index:06d}.json"
        payload = {
            "schema": 2,
            "cache_id": cache_id,
            "source_sha256": source_sha,
            "batch_index": index,
            "atom_count": len(batch_atoms),
            "paint_start": batch_atoms[0]["paint_index"],
            "paint_end": batch_atoms[-1]["paint_index"],
            "atoms": batch_atoms,
        }
        write_json(cache_dir / file_name, payload)
        batch_meta.append({
            "index": index,
            "file": file_name,
            "atom_count": len(batch_atoms),
            "paint_start": payload["paint_start"],
            "paint_end": payload["paint_end"],
            "singleton_complex": len(batch_atoms) == 1 and atom_complexity(batch_atoms[0]) >= args.complex_threshold,
        })

    manifest = {
        "schema": 2,
        "parser_version": PARSER_VERSION,
        "cache_id": cache_id,
        "source": {
            "master_svg": str(master),
            "sha256": source_sha,
            "viewBox": list(viewbox),
            "width": root.attrib.get("width", ""),
            "height": root.attrib.get("height", ""),
        },
        "contract": {
            "immutable": True,
            "paint_order": "ascending paint_index",
            "ordinary_batch_size": args.batch_size,
            "complex_threshold": args.complex_threshold,
            "playback_atom_types": ["path", "text"],
        },
        "stats": {
            "atoms": len(atoms),
            "paths": sum(a["type"] == "path" for a in atoms),
            "texts": sum(a["type"] == "text" for a in atoms),
            "batches": len(batches),
            "warnings": warnings,
        },
        "batches": batch_meta,
    }
    write_json(cache_dir / "geometry-cache.json", manifest)
    write_json(cache_dir / "atoms.json", {"schema": 2, "cache_id": cache_id, "atoms": atoms})
    print(
        f"CACHE_OK|cache={cache_dir}|cache_id={cache_id}|source_sha256={source_sha}"
        f"|atoms={len(atoms)}|paths={manifest['stats']['paths']}|texts={manifest['stats']['texts']}|batches={len(batches)}"
        f"|warnings={len(warnings)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
