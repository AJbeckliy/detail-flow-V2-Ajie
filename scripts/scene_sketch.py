"""Portable Pillow relationship sketches. Components are symbolic, not product truth."""
import math

KINDS = {'person_seated', 'sofa', 'neck_product', 'window', 'polyline'}
ANCHORS = {'person_seated': {'neck': (.40, .245), 'hand': (.68, .48)}}


def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def unit_point(p):
    return isinstance(p, list) and len(p) == 2 and all(finite(x) and 0 <= x <= 1 for x in p)


def valid_box(b):
    return (isinstance(b, list) and len(b) == 4 and all(finite(v) for v in b)
            and min(b[:2]) >= 0 and min(b[2:]) > 0
            and b[0]+b[2] <= 1.000001 and b[1]+b[3] <= 1.000001)


def prepare_scene(block):
    """Resolve declared anchor attachments; reject cycles and unsupported geometry."""
    raw = block.get('components')
    if not isinstance(raw, list) or not raw:
        raise ValueError('sketch requires nonempty components')
    indexed = {}
    for c in raw:
        if not isinstance(c, dict) or not isinstance(c.get('id'), str) or not c['id'] or c['id'] in indexed:
            raise ValueError('Sketch component IDs must be nonempty and unique')
        if c.get('kind') not in KINDS:
            raise ValueError('Unknown sketch component kind')
        if c.get('facing', 'right') not in {'left', 'right'}:
            raise ValueError('facing must be left or right')
        if c['kind'] == 'polyline':
            points = c.get('points')
            if not isinstance(points, list) or len(points) < 2 or not all(unit_point(p) for p in points):
                raise ValueError('polyline requires at least two normalized points')
        indexed[c['id']] = c
    resolved, visiting = {}, set()

    def resolve(cid):
        if cid in resolved:
            return resolved[cid]
        if cid in visiting or cid not in indexed:
            raise ValueError('Cyclic or missing sketch attachment target')
        visiting.add(cid)
        c = dict(indexed[cid])
        attachment = c.get('attach_to')
        if attachment is not None:
            if 'box' in c or not isinstance(attachment, dict):
                raise ValueError('Use either box or attach_to with size')
            parent = resolve(attachment.get('component'))
            anchor = parent['anchors'].get(attachment.get('anchor'))
            size = c.get('size')
            if anchor is None or not unit_point(size) or min(size) <= 0:
                raise ValueError('Unknown attachment anchor or invalid size')
            c['box'] = [anchor[0]-size[0]/2, anchor[1]-size[1]/2, *size]
        if not valid_box(c.get('box')):
            raise ValueError('Sketch component box must stay inside scene')
        x, y, w, h = c['box']
        c['anchors'] = {k: [x+(1-u if c.get('facing') == 'left' else u)*w, y+v*h]
                        for k, (u, v) in ANCHORS.get(c['kind'], {}).items()}
        resolved[cid] = c
        visiting.remove(cid)
        return c

    # Original order is the drawing order, even when attachments resolve forward.
    return [resolve(cid) for cid in indexed]


def draw_scene(draw, rect, components):
    x0, y0, x1, y1 = rect
    sw, sh = x1-x0, y1-y0
    stroke = max(2, round(sw/190))
    for c in components:
        x, y, w, h = c['box']
        def p(u, v):
            if c.get('facing') == 'left':
                u = 1-u
            return (round(x0+(x+u*w)*sw), round(y0+(y+v*h)*sh))
        color = '#D48B52' if c['kind'] == 'neck_product' else '#758C9A'
        def line(points, ink=color, weight=stroke):
            draw.line([p(*q) for q in points], fill=ink, width=weight, joint='curve')
        def ellipse(box, fill=None):
            a, b = p(box[0], box[1]), p(box[2], box[3])
            draw.ellipse((min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1])),
                         outline=color, width=stroke, fill=fill)
        kind = c['kind']
        if kind == 'polyline':
            line(c['points'], '#C5D0D7', max(1, stroke-1))
        elif kind == 'window':
            line([(0,1),(0,0),(1,0),(1,1)], '#C5D0D7')
            line([(.5,0),(.5,1)], '#C5D0D7')
            line([(0,.5),(1,.5)], '#C5D0D7')
        elif kind == 'sofa':
            line([(.08,.57),(.08,.13),(.13,.05),(.88,.05),(.93,.13),(.93,.57)])
            line([(.08,.39),(0,.39),(0,.87),(1,.87),(1,.39),(.93,.39)])
            line([(.08,.39),(.08,.66),(.93,.66),(.93,.39)])
            line([(.08,.76),(.93,.76)])
            line([(.08,.87),(.06,1)])
            line([(.92,.87),(.94,1)])
        elif kind == 'person_seated':
            # Head, neck, torso, bent arms, lap and bent legs; no facial identity.
            draw.polygon([p(*q) for q in [(.35,.19),(.46,.19),(.46,.25),(.57,.29),
                         (.68,.44),(.68,.48),(.50,.53),(.75,.61),(.82,.80),(.96,.86),
                         (.94,.95),(.81,.95),(.77,.99),(.61,.99),(.47,.91),(.50,.70),
                         (.31,.62),(.18,.53),(.23,.29),(.35,.25)]], fill='#F2F6FA')
            ellipse((.29,.015,.51,.205), '#F2F6FA')
            line([(.35,.20),(.35,.25),(.23,.29),(.18,.53),(.31,.62)])
            line([(.46,.20),(.46,.25),(.57,.29),(.68,.44),(.68,.48)])
            line([(.27,.32),(.30,.46),(.62,.50),(.68,.48)])
            line([(.53,.34),(.50,.53),(.75,.61),(.82,.80),(.96,.86)])
            line([(.31,.62),(.62,.65),(.64,.87),(.81,.95),(.94,.95)])
            line([(.41,.62),(.50,.70),(.47,.91),(.61,.99),(.77,.99)])
            line([(.30,.46),(.27,.54),(.39,.60)])
        elif kind == 'neck_product':
            # Symbol for a neck-worn object only, never an asserted product silhouette.
            line([(.14,.16),(.05,.38),(.13,.68),(.34,.84),(.66,.84),(.87,.68),(.95,.38),(.86,.16)],
                 color, stroke+2)
            ellipse((.05,.44,.26,.78), '#F3D9C4')
            ellipse((.74,.44,.95,.78), '#F3D9C4')
