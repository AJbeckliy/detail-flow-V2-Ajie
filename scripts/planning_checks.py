"""Local planning checks, not an automated artistic or product-truth judge."""
import argparse
from collections import Counter
import json
from pathlib import Path
from starcanvas_adapter import read,check,evidence,sha

DISPLAY_TEXT={
 'primary':'本屏以商品为主视觉。',
 'secondary':'本屏商品仅作辅助识别，不得压过本屏主题。',
 'absent':'本屏不展示完整商品或包装，产品图仅用于身份核对。',
}


def audit_plan(plan):
    issues=[];seen={};pages=plan.get('pages',[]);previous_focus=None
    def add(code,sid,message):issues.append({'id':code+':'+sid,'code':code,'page':sid,'message':message})
    for page in pages:
        sid=page['slice_id'];blocks=page.get('layout',{}).get('blocks',[])
        focus=page.get('visual_composition')
        if evidence(focus) and focus==previous_focus:add('repeated_focus',sid,'相邻页面的主视觉指令完全相同，请调整或解释有意重复。')
        previous_focus=focus
        shape=tuple(sorted((b.get('type',''),tuple(b.get('box',[]))) for b in blocks))
        if shape:
            if shape in seen:add('repeated_geometry',sid,'与第'+seen[shape]+'屏几何相同，需说明内容上的合理性或调整。')
            else:seen[shape]=sid
        text=[b for b in blocks if b.get('type') in ('text','annotation')]
        kind=page.get('module_type','').lower()
        if any(x in kind for x in ('numeric','table','step','specification')) and len(text)<=2:
            add('semantic_layout',sid,'数字、表格或步骤尚未落实为可独立编辑的分区。')
        body=page.get('text_exact',{}).get('body') if isinstance(page.get('text_exact'),dict) else None
        if isinstance(body,str) and body.count('\n')>=3 and len(text)<=2:
            add('undivided_copy',sid,'多组文案共用一个正文框，请检查是否需要语义分块。')
    notes=[p.get('reference_style_notes','') for p in pages]
    if plan.get('style_reference') and len(pages)>=3 and len(set(notes))==1:
        add('generic_reference','all','所有页面参考说明相同，尚未交代片段、借鉴目标和对应页面。')
    return issues


def validate_plan(plan):
    decisions=plan.get('planning_review',{}).get('decisions',{})
    check(isinstance(decisions,dict),'planning_review.decisions must be an object')
    for issue in audit_plan(plan):
        decision=decisions.get(issue['id'],{})
        check(decision.get('action')=='keep' and evidence(decision.get('reason')),
              'Unresolved planning warning '+issue['id']+': revise the plan or record a specific reason to keep it')
    for page in plan['pages']:
        check(evidence(page.get('visual_composition')),'Each page needs its actual visual_composition')
        check(page.get('product_display') in DISPLAY_TEXT,'Each page needs product_display: primary, secondary or absent')
    return audit_plan(plan)


def validate_visual_review(review):
    """Inspect an Agent-authored review record, never assign image quality from metadata."""
    allowed={'pass','needs_revision','unverified'}
    check(isinstance(review.get('pages'),list) and review['pages'],'Visual review pages required')
    ids=set();needs=False;unknown=False;routes=[]
    for page in review['pages']:
        sid=page.get('id');check(evidence(sid) and sid not in ids,'Duplicate/missing review page');ids.add(sid)
        image=page.get('image_path')
        check(evidence(image) and Path(image).is_file() and sha(image)==page.get('sha256'),'Reviewed image missing or changed')
        for field in ('technical','copy','product_identity','composition'):
            check(page.get(field) in allowed,'Missing review layer: '+field)
            needs|=page[field]=='needs_revision';unknown|=page[field]=='unverified'
        issues=page.get('issues',[]);check(isinstance(issues,list),'Review issues must be a list')
        if issues:
            check(any(page[k]=='needs_revision' for k in ('copy','product_identity','composition','technical')),
                  'Known issues cannot be reported as all passed')
        for issue in issues:
            check(evidence(issue.get('code')) and evidence(issue.get('description')),'Issue code/description required')
            if issue.get('repeated'):
                check(issue.get('next_strategy') in ('targeted_text_edit','prompt_or_layout_change','request_better_asset','defer')
                      and evidence(issue.get('strategy_reason')),
                      'Repeated issue needs a changed repair strategy or defer, not another identical full-page retry')
            routes.append({'page':sid,'issue':issue['code'],'next_strategy':issue.get('next_strategy','review_before_repair')})
    check(review.get('set_coherence') in allowed,'Whole-set coherence review required')
    needs|=review['set_coherence']=='needs_revision';unknown|=review['set_coherence']=='unverified'
    return {'status':'needs_revision' if needs else 'needs_review' if unknown else 'agent_review_passed',
            'user_accepted':review.get('user_accepted') is True and evidence(review.get('user_evidence')),
            'repair_routes':routes,'generation_authorized':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('kind',choices=('plan','visual'));p.add_argument('input',type=Path)
    a=p.parse_args();data=read(a.input)
    result={'status':'needs_agent_design_review','issues':audit_plan(data)} if a.kind=='plan' else validate_visual_review(data)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
