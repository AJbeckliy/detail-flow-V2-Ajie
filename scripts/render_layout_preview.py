"""Render an Agent-authored layout plan; no planning, generation, or network calls.

Requires Pillow. See references/layout-preview.md for the small layout schema.
The input plan and exact copy are never modified. Errors block image rendering.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps
from scene_sketch import prepare_scene, draw_scene


TYPES = {"text", "image", "placeholder", "annotation", "sketch"}
FONTS = [Path("C:/Windows/Fonts/msyh.ttc"),
         Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")]


def leaves(value, prefix=""):
    if isinstance(value, str):
        return {prefix: value}
    result = {}
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        items = enumerate(value)
    else:
        raise ValueError("text_exact must contain only strings, objects, or lists")
    for key, item in items:
        if "." in str(key):
            raise ValueError("text_exact keys cannot contain dots")
        path = f"{prefix}.{key}" if prefix else str(key)
        result.update(leaves(item, path))
    return result


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def box_valid(box):
    return (isinstance(box, list) and len(box) == 4 and all(number(x) for x in box)
            and box[0] >= 0 and box[1] >= 0 and box[2] > 0 and box[3] > 0
            and box[0] + box[2] <= 1.000001 and box[1] + box[3] <= 1.000001)


def pixel_box(box, width, height):
    x, y, w, h = box
    return (round(x * width), round(y * height),
            round((x + w) * width), round((y + h) * height))


def wrap_copy(text, font, width):
    """Wrap without rewriting, stripping whitespace, truncating, or shrinking."""
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for char in paragraph:
            if current and font.getlength(current + char) > width:
                lines.append(current)
                current = char
            else:
                current += char
        lines.append(current)
    return lines


def intersect(a, b):
    return (min(a[0] + a[2], b[0] + b[2]) > max(a[0], b[0]) + 1e-8
            and min(a[1] + a[3], b[1] + b[3]) > max(a[1], b[1]) + 1e-8)


def choose_font(requested=None):
    if requested:
        path = Path(requested)
        if not path.is_file():
            raise ValueError(f"Font missing: {path}")
        return path
    for path in FONTS:
        if path.is_file():
            return path
    raise ValueError("Supply --font with a local font supporting the plan's language")


def normalize_color(value):
    rgb = ImageColor.getrgb(value)
    if len(rgb) != 3:
        raise ValueError('Text colors must be opaque RGB colors')
    return '#%02x%02x%02x' % rgb


def audit_plan(plan, source_dir, width, font_path):
    issues, prepared, ids = [], [], set()

    def issue(code, page, block, message, severity="error"):
        issues.append(dict(code=code, page=page, block=block, message=message, severity=severity))

    pages = plan.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("pages must be a nonempty list")
    design_width = plan.get("design_width", 720)
    if not number(design_width) or design_width <= 0:
        raise ValueError("design_width must be positive")
    fingerprints = {}
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("Every page must be an object")
        sid = str(page.get("slice_id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_-]+", sid) or sid in ids:
            issue("PAGE_ID", sid, None, "slice_id must be unique and filename-safe")
        ids.add(sid)
        ratio = page.get("aspect_ratio", plan.get("aspect_ratio"))
        if not isinstance(ratio, str) or not re.fullmatch(r"[1-9]\d*:[1-9]\d*", ratio):
            issue("RATIO", sid, None, "Provide the planned aspect_ratio; no inferred default")
            continue
        rw, rh = map(int, ratio.split(":"))
        height = round(width * rh / rw)
        if not 64 <= height <= 12000:
            issue("CANVAS_SIZE", sid, None, "Preview height must be 64..12000 pixels")
            continue
        exact = leaves(page.get("text_exact", {}))
        layout = page.get("layout", {})
        blocks = layout.get("blocks") if isinstance(layout, dict) else None
        if isinstance(blocks, list) and not blocks:
            issue("EMPTY_PAGE", sid, None, "Page is an incomplete draft. Add content or obtain approval to remove the page; its count is preserved.")
            continue
        if not isinstance(blocks, list):
            issue("MISSING_LAYOUT", sid, None, "Agent must supply blocks; renderer does not choose a template")
            continue
        local, used = {}, Counter()
        for block in blocks:
            if not isinstance(block, dict):
                issue("BLOCK_GEOMETRY", sid, None, "Every block must be an object")
                continue
            bid = block.get("id")
            typ = block.get("type")
            if not isinstance(bid, str) or not bid or bid in local:
                issue("BLOCK_ID", sid, str(bid), "Block IDs must be nonempty and unique")
                continue
            if typ not in TYPES or not box_valid(block.get("box")):
                issue("BLOCK_GEOMETRY", sid, bid, "Unknown type or box outside normalized canvas")
                continue
            item = dict(block)
            item["rect"] = pixel_box(block["box"], width, height)
            local[bid] = item
            if not isinstance(block.get("overlap_with", []), list):
                issue("OVERLAP_DECLARATION", sid, bid, "overlap_with must be a list of block IDs")
                item["overlap_with"] = []
            if typ in {"text", "annotation"}:
                key = block.get("copy_key")
                if key not in exact:
                    issue("UNKNOWN_COPY", sid, bid, "copy_key must reference one text_exact string")
                    continue
                used[key] += 1
                size = block.get("font_size", 32)
                if not number(size) or not 8 <= size <= 180:
                    issue("FONT_SIZE", sid, bid, "font_size must be 8..180 design pixels")
                    continue
                size = max(1, round(size * width / design_width))
                font = ImageFont.truetype(str(font_path), size)
                x0, y0, x1, y1 = item["rect"]
                lines = wrap_copy(exact[key], font, x1 - x0)
                line_height = math.ceil(size * 1.45)
                need = (len(lines) - 1) * line_height + math.ceil(size * 1.25)
                if need > y1 - y0 or any(font.getlength(line) > x1 - x0 for line in lines):
                    issue("TEXT_OVERFLOW", sid, bid, f"Copy needs about {need}px height; box has {y1-y0}px. Agent must revise geometry or approved copy; no auto-truncation.")
                item.update(text=exact[key], font=font, lines=lines, line_height=line_height)
                if block.get('align', 'left') not in ('left', 'center', 'right'):
                    issue('ALIGN', sid, bid, 'align must be left, center or right')
                try:
                    item['color'] = normalize_color(block.get("color", "#183B56"))
                except (ValueError, TypeError, AttributeError):
                    issue("COLOR", sid, bid, "Invalid text color")
            elif typ == "sketch":
                try:
                    item["scene_components"] = prepare_scene(block)
                except (ValueError, TypeError, KeyError) as exc:
                    issue("SKETCH_GEOMETRY", sid, bid, str(exc))
            elif typ == "image":
                raw = block.get("path", "")
                if not isinstance(raw, str) or not raw or re.match(r"https?://", raw):
                    issue("IMAGE_PATH", sid, bid, "image requires a local file; use placeholder for absent assets")
                    continue
                path = Path(raw)
                if not path.is_absolute():
                    path = source_dir / path
                try:
                    with Image.open(path) as im:
                        im.load()
                        oriented = ImageOps.exif_transpose(im)
                        if 'A' in oriented.getbands() or 'transparency' in oriented.info:
                            rgba = oriented.convert('RGBA')
                            image = Image.new('RGB',rgba.size,'#E1EAF2')
                            image.paste(rgba,mask=rgba.getchannel('A'))
                        else:
                            image = oriented.convert('RGB')
                    crop = block.get("crop")
                    if crop is not None:
                        if not box_valid(crop):
                            raise ValueError("crop must be a normalized box inside source image")
                        image = image.crop(pixel_box(crop, image.width, image.height))
                    x0, y0, x1, y1 = item["rect"]
                    scale = min((x1-x0)/image.width, (y1-y0)/image.height)
                    iw, ih = max(1, round(image.width*scale)), max(1, round(image.height*scale))
                    ix, iy = x0 + ((x1-x0)-iw)//2, y0 + ((y1-y0)-ih)//2
                    item.update(image=image, content_rect=(ix, iy, ix+iw, iy+ih), resolved_path=str(path.resolve()))
                except (OSError, ValueError) as exc:
                    issue("IMAGE_READ", sid, bid, str(exc))
        for key in exact:
            if used[key] == 0:
                issue("UNPLACED_COPY", sid, None, f"text_exact.{key} has no layout block")
            elif used[key] > 1:
                issue("DUPLICATE_COPY", sid, None, f"text_exact.{key} appears {used[key]} times")
        for bid, item in local.items():
            for other in item.get("overlap_with", []):
                if other not in local or other == bid:
                    issue("OVERLAP_DECLARATION", sid, bid, "overlap_with references an unknown/self block")
            if item["type"] == "annotation":
                target = item.get("target", {})
                dest = local.get(target.get("block_id")) if isinstance(target, dict) else None
                uv = target.get("uv") if isinstance(target, dict) else None
                if (not dest or dest["type"] not in {"image", "placeholder", "sketch"}
                        or not isinstance(uv, list) or len(uv) != 2
                        or not all(number(x) and 0 <= x <= 1 for x in uv)):
                    issue("ANNOTATION_TARGET", sid, bid, "Target must be a visual block and normalized uv point")
                    continue
                tx0, ty0, tx1, ty1 = dest.get("content_rect", dest["rect"])
                item["target_point"] = (round(tx0+uv[0]*(tx1-tx0)), round(ty0+uv[1]*(ty1-ty0)))
        items = list(local.values())
        for i, item in enumerate(items):
            for other in items[i+1:]:
                if (intersect(item["box"], other["box"])
                        and other["id"] not in item.get("overlap_with", [])
                        and item["id"] not in other.get("overlap_with", [])):
                    issue("UNDECLARED_OVERLAP", sid, item["id"], f"Overlaps {other['id']}; move boxes or declare an intentional overlap")
        signature = tuple(sorted((b["type"], tuple(b["box"])) for b in local.values()))
        if signature in fingerprints:
            issue("REPEATED_GEOMETRY", sid, None, f"Same block geometry as {fingerprints[signature]}; Agent should check whether repetition serves a purpose", "warning")
        fingerprints[signature] = sid
        prepared.append(dict(page=page, id=sid, width=width, height=height, blocks=items, exact=exact))
    return prepared, issues


def draw_page(page, font_path):
    im = Image.new("RGB", (page["width"], page["height"]), "#F2F6FA")
    draw = ImageDraw.Draw(im)
    meta_font = ImageFont.truetype(str(font_path), max(12, round(page["width"]*.023)))
    # The visual placeholders and source-image placements are planning marks.
    for b in page["blocks"]:
        if b["type"] == "sketch":
            draw_scene(draw, b["rect"], b["scene_components"])
            continue
        if b["type"] not in {"image", "placeholder"}:
            continue
        rect = b["rect"]
        draw.rounded_rectangle(rect, radius=12, fill="#E1EAF2", outline="#9AB0C2", width=2)
        if b["type"] == "image":
            x0, y0, x1, y1 = b["content_rect"]
            im.paste(b["image"].resize((x1-x0, y1-y0), Image.Resampling.LANCZOS), (x0,y0))
        else:
            x0,y0,x1,y1=rect
            draw.line((x0+12,y0+12,x1-12,y1-12), fill="#C7D4DF", width=2)
            draw.line((x1-12,y0+12,x0+12,y1-12), fill="#C7D4DF", width=2)
        label = b.get("label", "原图位置" if b["type"] == "image" else "视觉占位")
        draw.text((rect[0]+10,rect[1]+8), label, font=meta_font, fill="#516C82", anchor="lt")
    for b in page["blocks"]:
        if b["type"] == "annotation":
            x0,y0,x1,y1=b["rect"]
            p=b["target_point"]
            anchors=[(x0,(y0+y1)//2),(x1,(y0+y1)//2),((x0+x1)//2,y0),((x0+x1)//2,y1)]
            start=min(anchors,key=lambda q:(q[0]-p[0])**2+(q[1]-p[1])**2)
            draw.line((start,p),fill="#607F96",width=2)
            draw.ellipse((p[0]-4,p[1]-4,p[0]+4,p[1]+4),fill="#607F96")
    for b in page["blocks"]:
        if b["type"] not in {"text", "annotation"}:
            continue
        x0,y0,x1,y1=b["rect"]
        for j,line in enumerate(b["lines"]):
            x=x0
            if b.get("align") == "center":
                x=x0+((x1-x0)-b["font"].getlength(line))/2
            elif b.get('align') == 'right':
                x=x1-b['font'].getlength(line)
            draw.text((x,y0+j*b["line_height"]),line,font=b["font"],fill=b.get("color","#183B56"),anchor="lt")
    return im


def render_plan(plan_path, output_dir, width=720, font_path=None, columns=3):
    plan_path, output_dir = Path(plan_path), Path(output_dir)
    if output_dir.exists():
        raise ValueError("Output folder already exists; use a new revision folder")
    if not isinstance(width,int) or not 240 <= width <= 2400:
        raise ValueError("width must be 240..2400")
    if not isinstance(columns,int) or not 1 <= columns <= 4:
        raise ValueError("columns must be 1..4")
    source_bytes=plan_path.read_bytes()
    plan=json.loads(source_bytes.decode("utf-8-sig"))
    font_path=choose_font(font_path)
    pages,issues=audit_plan(plan,plan_path.parent,width,font_path)
    report={"artifact_kind":"planning_wireframe", "status":"layout_ready_for_review",
            "is_generated_image":False,"generation_authorized":False,
            "source_plan_sha256":hashlib.sha256(source_bytes).hexdigest(),
            "font":str(font_path),"issues":issues,"pages":[]}
    if any(x["severity"]=="error" for x in issues):
        report["status"]="layout_needs_revision"
    output_dir.mkdir(parents=True)
    if report["status"]=="layout_ready_for_review":
        drawings=[]
        for page in pages:
            image=draw_page(page,font_path)
            target=output_dir/f"page_{page['id']}_layout.png"
            image.save(target)
            report["pages"].append({"slice_id":page["id"],"path":str(target.resolve()),
                                    "dimensions":[image.width,image.height],
                                    "text_exact":page["exact"],
                                    "annotation_points":{b["id"]:b["target_point"] for b in page["blocks"] if b["type"]=="annotation"}})
            drawings.append((page,image))
        cols=min(columns,len(drawings));tw=320;gap=24;header=104
        th=max(round(im.height*tw/im.width) for _,im in drawings);ch=th+90
        rows=math.ceil(len(drawings)/cols)
        board=Image.new("RGB",(gap+(tw+gap)*cols,header+gap+rows*ch),"#EBF0F5")
        d=ImageDraw.Draw(board);big=ImageFont.truetype(str(font_path),26);small=ImageFont.truetype(str(font_path),17)
        title=plan.get("title","详情页布局预览")
        for j,line in enumerate(wrap_copy(title,big,board.width-2*gap)[:2]):
            d.text((gap,14+j*32),line,font=big,fill="#183B56",anchor="lt")
        d.text((gap,78),"布局预览 · 图片与占位框仅用于讨论位置 · 待确认",font=small,fill="#667B8B",anchor="lt")
        for i,(page,im) in enumerate(drawings):
            x=gap+(i%cols)*(tw+gap);y=header+gap+(i//cols)*ch
            d.text((x,y),f"第 {page['id']} 屏 · {page['page'].get('module_label','布局')}",font=small,fill="#36566E",anchor="lt")
            thumb=im.resize((tw,round(im.height*tw/im.width)),Image.Resampling.LANCZOS)
            board.paste(thumb,(x,y+32))
            d.text((x,y+th+44),"占位区与线条仅用于讨论布局",font=small,fill="#667B8B",anchor="lt")
        target=output_dir/"layout_board.png";board.save(target);report["board_path"]=str(target.resolve())
    (output_dir/"layout_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path);parser.add_argument("output",type=Path)
    parser.add_argument("--font",type=Path);parser.add_argument("--width",type=int,default=720)
    parser.add_argument("--columns",type=int,default=3)
    args=parser.parse_args()
    try:
        result=render_plan(args.plan,args.output,args.width,args.font,args.columns)
    except (OSError,ValueError,TypeError,KeyError) as exc:
        parser.exit(2,f"Layout preview failed: {exc}\n")
    print(json.dumps({"status":result["status"],"board_path":result.get("board_path"),"issues":result["issues"]},ensure_ascii=False,indent=2))
    return 0 if result["status"]=="layout_ready_for_review" else 2


if __name__=="__main__":
    raise SystemExit(main())
