"""Current product identity, declared reference roles and selected reference provenance."""
from pathlib import Path
from starcanvas_adapter import read,sha,check,evidence,path_key

WORKFLOW='detail-flow-direct-v4'
ROLES={'product','model','style','composition'}


def validate_product(manifest,plan):
    ctx=plan.get('product_context',{})
    check(evidence(ctx.get('product_id')) and manifest.get('product_id')==ctx['product_id'],'Product ID differs from the current product brief')
    check(evidence(ctx.get('name')) and evidence(ctx.get('language')) and evidence(ctx.get('ratio_source')),'Product name/language/ratio source required')
    check(type(ctx.get('page_count')) is int and ctx['page_count']==len(plan['pages']),'Product page count differs from approved plan')
    check(ctx.get('aspect_ratio')==plan.get('aspect_ratio'),'Product ratio differs from approved plan')
    base=Path(manifest['approved_plan']['path']).parent
    assets=ctx.get('assets',[]);check(isinstance(assets,list) and assets,'Current product asset inventory required')
    digests=set()
    for asset in assets:
        p=(base/asset['path']).resolve();check(p.is_file() and sha(p)==asset.get('sha256'),'Current product source changed')
        digests.add(asset['sha256'])
    for task in manifest['tasks']:
        check(task.get('language',ctx['language'])==ctx['language'],'Task language differs from current product')
        for ref in task['references']:
            if ref.get('role')=='product':
                authority=ref.get('source_path',ref['path'])
                check(sha(authority) in digests,'Product reference is not from the current product inventory')


def normalized(ref,base):
    value={k:v for k,v in ref.items() if k not in ('sha256','source_sha256')}
    value['path']=path_key(base/ref['path'])
    if ref.get('source_path'):value['source_path']=path_key(base/ref['source_path'])
    return value


def validate_references(manifest):
    if manifest.get('workflow')!=WORKFLOW:return
    policy=manifest.get('reference_policy',{'mode':'text_only'})
    check(policy.get('mode') in ('text_only','mixed'),'Reference policy must be text_only or mixed')
    plan=read(manifest['approved_plan']['path']);base=Path(manifest['approved_plan']['path']).parent
    pages={p['slice_id']:p for p in plan['pages']}
    for task in manifest['tasks']:
        refs=task['references']
        check(refs and refs[0].get('role')=='product','First reference is current product authority')
        visual=False
        for ref in refs:
            role=ref.get('role');check(role in ROLES,'Unknown reference role')
            check(not any(k in ref for k in ('weight','strength','reference_weight')),'Reference roles are not provider weight controls')
            if role!='product':check(evidence(ref.get('purpose')),'Non-product reference needs a purpose')
            if role in ('style','composition'):
                visual=True;check(policy['mode']=='mixed','Visual references require selected mixed mode')
                check(isinstance(ref.get('exclude'),list) and ref['exclude'] and all(evidence(s) for s in ref['exclude']),
                      'Style/composition reference needs explicit content exclusions')
            if 'crop_box' in ref:
                box=ref['crop_box'];check(ref.get('source_path'),'Cropped reference needs original source_path')
                check(isinstance(box,list) and len(box)==4 and all(type(x) in (int,float) for x in box)
                      and min(box[:2])>=0 and min(box[2:])>0 and box[0]+box[2]<=1 and box[1]+box[3]<=1,'Invalid normalized reference crop')
            if ref.get('source_path'):
                source=Path(ref['source_path']);check(source.is_file(),'Reference original source missing')
                if ref.get('source_sha256'):check(sha(source)==ref['source_sha256'],'Reference original source changed')
        if task['kind']=='slice':
            pid=task.get('page_id',task['id'].removeprefix('screen-'));page=pages[pid]
            declared=page.get('reference_images')
            check(isinstance(declared,list) and [normalized(r,base) for r in declared]==[normalized(r,Path.cwd()) for r in refs],
                  'Actual references/order/roles differ from approved page reference_images')
            for approved in declared:
                original=(base/approved['path']).resolve()
                check(original.is_file() and sha(original)==approved.get('sha256'),'Approved reference image changed or missing its hash')
                if approved.get('source_path'):
                    original_source=(base/approved['source_path']).resolve()
                    check(original_source.is_file() and sha(original_source)==approved.get('source_sha256'),'Approved reference original source changed')
            prompt=Path(task['prompt_path']).read_text(encoding='utf-8')
            for ref in refs:
                if ref.get('role')!='product':
                    check(ref['purpose'] in prompt,'Reference purpose missing from prompt')
                    for item in ref.get('exclude',[]):check(item in prompt,'Reference exclusion missing from prompt')
        if visual:check(policy['mode']=='mixed','Mixed reference policy required')
