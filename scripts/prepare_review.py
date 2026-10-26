"""Build the editable first-review artifact and request a browser launch by default."""
import argparse
import hashlib
import json
from pathlib import Path
import webbrowser
from build_review_editor import build_editor


def prepare_review(plan, output, font=None, no_open=False, opener=None):
    plan, output = Path(plan).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Use a new review folder; previous edits are preserved')
    output.mkdir(parents=True)
    html = build_editor(plan, output/'review.html', font)
    payload = json.loads(html.read_text(encoding='utf-8').split('<script id="data" type="application/json">')[1].split('</script>')[0])
    status = 'not_requested' if no_open else 'launch_failed'
    if not no_open:
        try:
            if (opener or webbrowser.open)(html.as_uri(), new=2): status = 'launch_requested'
        except Exception:
            pass  # Some headless/restricted hosts have no opener. The HTML is retained.
    receipt = {'artifact_kind':'editable_html_review','source_plan':str(plan),
               'source_plan_sha256':payload['source_hash'],
               'html_path':str(html),'html_sha256':hashlib.sha256(html.read_bytes()).hexdigest(),
               'open_status':status,'user_open_verified':False,
               'generation_authorized':False,'status':'awaiting_design_review',
               'next_action':'Show this HTML to the user and obtain design confirmation. A PNG is supplementary only.'}
    target = output/'review-receipt.json'
    target.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    return dict(receipt, receipt_path=str(target))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('plan',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--font',type=Path);p.add_argument('--no-open',action='store_true',help='Headless/test only; Agent must still provide/open the HTML through its host')
    a=p.parse_args()
    try:
        print(json.dumps(prepare_review(a.plan,a.output,a.font,a.no_open),ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError,TypeError) as exc:p.exit(2,str(exc)+'\n')
