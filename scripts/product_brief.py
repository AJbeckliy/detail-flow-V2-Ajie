"""Start a product-specific planning draft without inheriting another product's settings."""
import argparse,json,uuid
from pathlib import Path
from starcanvas_adapter import check,sha


def create(name,assets,*,ratio=None,pages=8,language='zh-CN',ratio_evidence=None):
    check(isinstance(pages,int) and not isinstance(pages,bool) and pages>0,'Positive page count required')
    check(bool(name.strip()) and bool(language.strip()),'Product name and language required')
    check(ratio is None or (isinstance(ratio_evidence,str) and ratio_evidence.strip()),'Explicit ratio needs its current-product or reusable-preference evidence')
    files=[]
    for asset in assets:
        path=Path(asset).resolve();check(path.is_file(),'Product asset missing')
        files.append({'path':str(path),'sha256':sha(path)})
    check(files,'Product assets required')
    context={'product_id':uuid.uuid4().hex,'name':name,'page_count':pages,'language':language,
             'aspect_ratio':ratio or '9:16','ratio_source':ratio_evidence or 'Default for this new product; no previous-product inheritance',
             'assets':files}
    return {'title':name,'aspect_ratio':context['aspect_ratio'],'product_context':context,'pages':[]}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('name');p.add_argument('output',type=Path)
    p.add_argument('--assets',type=Path,nargs='+',required=True);p.add_argument('--ratio');p.add_argument('--ratio-evidence')
    p.add_argument('--pages',type=int,default=8);p.add_argument('--language',default='zh-CN');a=p.parse_args()
    check(not a.output.exists(),'Preserve existing product draft')
    value=create(a.name,a.assets,ratio=a.ratio,pages=a.pages,language=a.language,ratio_evidence=a.ratio_evidence)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'product_id':value['product_context']['product_id'],'draft':str(a.output),'generation_authorized':False},ensure_ascii=False))

if __name__=='__main__':main()
