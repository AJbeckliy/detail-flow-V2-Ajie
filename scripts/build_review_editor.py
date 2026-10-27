"""Build a standalone, offline copy-review HTML from an existing layout plan."""
import argparse
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
from render_layout_preview import audit_plan, choose_font, draw_page, normalize_color


def build_editor(source, output, font=None):
    source, output = Path(source), Path(output)
    if output.exists():
        raise ValueError('Use a new HTML path; existing reviews are preserved')
    raw = source.read_bytes()
    plan = json.loads(raw.decode('utf-8-sig'))
    font = choose_font(font)
    pages, issues = audit_plan(plan, source.parent, 720, font)
    if any(i['severity']=='error' for i in issues):
        raise ValueError('Fix layout errors before building editor: '+json.dumps(issues,ensure_ascii=False))
    backgrounds = []
    visual_layers = []
    for page in pages:
        # Text and annotation leaders are live layers; do not bake their old positions.
        background = dict(page)
        background['blocks'] = []
        layers = {}
        for block in page['blocks']:
            if block['type'] in {'text','annotation'}: continue
            single = dict(page, blocks=[block])
            tile = draw_page(single, font).crop(block['rect'])
            data = io.BytesIO(); tile.save(data, format='PNG')
            layers[block['id']] = 'data:image/png;base64,' + base64.b64encode(data.getvalue()).decode('ascii')
        visual_layers.append(layers)
        image = draw_page(background, font)
        buf = io.BytesIO(); image.save(buf,format='PNG')
        backgrounds.append('data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode('ascii'))
    # Exported JSON may be downloaded elsewhere: retain resolvable original asset paths.
    portable = copy.deepcopy(plan)
    for page in portable['pages']:
        for block in page['layout']['blocks']:
            if block['type'] in {'text', 'annotation'} and 'color' in block:
                block['color'] = normalize_color(block['color'])
            if block['type']=='image':
                p=Path(block['path'])
                block['path']=str((source.parent/p).resolve()) if not p.is_absolute() else str(p)
    targets = [{b['id']: [b['target_point'][0]/page['width'],
                         b['target_point'][1]/page['height']]
                for b in page['blocks'] if b['type']=='annotation'} for page in pages]
    payload={'plan':portable,'backgrounds':backgrounds,'annotation_targets':targets,'visual_layers':visual_layers,
             'source_hash':hashlib.sha256(raw).hexdigest()}
    from planning_checks import audit_plan as audit_design
    payload['planning_warnings']=audit_design(portable)
    encoded=json.dumps(payload,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=(Path(__file__).resolve().parents[1]/'references/review-editor.html').read_text(encoding='utf-8')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(template.replace('/*__PAYLOAD__*/',encoded),encoding='utf-8')
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('plan',type=Path); p.add_argument('output',type=Path); p.add_argument('--font',type=Path)
    a=p.parse_args()
    try: print(build_editor(a.plan,a.output,a.font))
    except (OSError,ValueError,TypeError,KeyError) as e: p.exit(2,str(e)+'\n')
