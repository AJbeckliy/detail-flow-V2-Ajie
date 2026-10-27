"""Compose existing images in explicit reading order; no generation, seam repair or approval."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw


def compose(manifest_path, output_dir, width=600):
    manifest_path, output_dir = Path(manifest_path), Path(output_dir)
    if output_dir.exists():
        raise ValueError('Use a new output directory; previews and originals are preserved')
    if not isinstance(width, int) or isinstance(width, bool) or not 120 <= width <= 1600:
        raise ValueError('width must be 120..1600')
    raw = manifest_path.read_bytes()
    items = json.loads(raw.decode('utf-8-sig')).get('images')
    if not isinstance(items, list) or not items:
        raise ValueError('Provide a nonempty images list in reading order')
    prepared, records, ids, paths = [], [], set(), set()
    total = 0
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Every image entry must be an object')
        sid, value = item.get('id'), item.get('path')
        if not isinstance(sid, str) or not sid.strip() or sid in ids:
            raise ValueError('Image ids must be nonempty and unique')
        if not isinstance(value, str) or not value:
            raise ValueError('Image path is required')
        p = Path(value)
        if not p.is_absolute(): p = manifest_path.parent / p
        p = p.resolve()
        key = str(p).casefold()
        if key in paths: raise ValueError('Duplicate image path in ordered preview')
        ids.add(sid); paths.add(key)
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        with Image.open(p) as source:
            source.load()
            source = ImageOps.exif_transpose(source)
            w, h = source.size
            target_h = max(1, round(h * width / w))
            if total + target_h > 100000 or (total + target_h) * width > 100000000:
                raise ValueError('Preview is too large; reduce width or review a smaller batch')
            if 'A' in source.getbands():
                rgba = source.convert('RGBA')
                im = Image.new('RGB', source.size, 'white'); im.paste(rgba, mask=rgba.getchannel('A'))
            else: im = source.convert('RGB')
            prepared.append(im.resize((width, target_h), Image.Resampling.LANCZOS))
        records.append(dict(id=sid, path=str(p), sha256=digest, original_size=[w,h],
                            preview_size=[width,target_h], y=total))
        total += target_h
    board = Image.new('RGB', (width,total), 'white')
    for im, record in zip(prepared, records): board.paste(im, (0,record['y']))
    for record in records:
        if hashlib.sha256(Path(record['path']).read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Source changed during composition; rebuild from a stable revision')
    output_dir.mkdir(parents=True)
    target = output_dir/'vertical-preview.png'; board.save(target)
    groups=[]
    for offset in range(0,len(prepared),4):
        subset=prepared[offset:offset+4];rows=(len(subset)+1)//2
        cell_h=max(im.height for im in subset)+32
        group=Image.new('RGB',(width*min(2,len(subset)),cell_h*rows),'white');draw=ImageDraw.Draw(group)
        for j,im in enumerate(subset):
            x=(j%2)*width;y=(j//2)*cell_h
            draw.text((x+10,y+8),str(offset+j+1).zfill(2),fill='black')
            group.paste(im,(x,y+32))
        path=output_dir/f'group-{offset//4+1:02d}.png';group.save(path)
        groups.append({'path':str(path.resolve()),'ids':[r['id'] for r in records[offset:offset+4]]})
    report = dict(status='needs_agent_visual_review', generation_authorized=False,
                  seam_repair=False, original_files_modified=False, width=width,height=total,
                  preview_path=str(target.resolve()), manifest_sha256=hashlib.sha256(raw).hexdigest(),
                  images=records,review_groups=groups)
    (output_dir/'preview-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path); parser.add_argument('output',type=Path)
    parser.add_argument('--width',type=int,default=600)
    args = parser.parse_args()
    try:
        report = compose(args.manifest,args.output,args.width)
        print(json.dumps({'status':report['status'],'preview_path':report['preview_path']},ensure_ascii=False))
    except (OSError,ValueError,TypeError,KeyError) as exc:
        parser.exit(2, str(exc)+'\n')
