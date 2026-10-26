// Offline JS-to-Python handoff fixtures; no browser or generation requests.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const template=fs.readFileSync(path.join(__dirname,'../references/review-editor.html'),'utf8');
const ctx=vm.createContext({});vm.runInContext(template.split('/* MODEL_START */')[1].split('/* MODEL_END */')[0]+';globalThis.api={importPlan,deleteText,makeExport};',ctx);
const {importPlan,deleteText,makeExport}=ctx.api,clone=x=>JSON.parse(JSON.stringify(x));
const out=process.argv[2];if(out)fs.mkdirSync(out,{recursive:false});
const base={title:'Handoff regression',aspect_ratio:'9:16',pages:[{slice_id:'01',review_annotations:[],text_exact:{title:'标题',label:'细节'},layout:{blocks:[
 {id:'visual',type:'placeholder',box:[.1,.2,.8,.5]},
 {id:'title',type:'text',copy_key:'title',box:[.15,.25,.6,.1],font_size:24,overlap_with:['visual']},
 {id:'label',type:'annotation',copy_key:'label',box:[.1,.8,.7,.1],font_size:24,target:{block_id:'visual',uv:[.5,.5]}}
]}}]};
const deleted=clone(base);deleteText(base.pages[0],deleted.pages[0],'visual');
assert.deepEqual(deleted.pages[0].layout.blocks[0].overlap_with,[]);
assert.equal(deleted.pages[0].layout.blocks.length,1);
const restored=clone(importPlan(base,makeExport(deleted,'fixture',0,0),'fixture'));
assert.deepEqual(restored,clone(deleted));
// Old same-source export with a deleted overlap target is canonicalized.
const old=clone(makeExport(deleted,'fixture',0,0));old.pages[0].layout.blocks[0].overlap_with=['visual'];
assert.deepEqual(clone(importPlan(base,old,'fixture')).pages[0].layout.blocks[0].overlap_with,[]);
const tampered=clone(makeExport(base,'fixture',0,0));tampered.pages[0].layout.blocks[1].overlap_with=['label'];
assert.throws(()=>importPlan(base,tampered,'fixture'));
const dangling=clone(makeExport(base,'fixture',0,0));dangling.pages[0].layout.blocks=dangling.pages[0].layout.blocks.filter(b=>b.id!=='visual');
assert.throws(()=>importPlan(base,dangling,'fixture'));
const empty=clone(deleted);deleteText(base.pages[0],empty.pages[0],'title');
const exported=clone(makeExport(empty,'fixture',0,0));assert.deepEqual(exported.review_state.empty_page_ids,['01']);
assert.equal(importPlan(base,exported,'fixture').pages.length,1);
// Retained legacy color names can round-trip; new blocks remain constrained.
const named=clone(base);named.pages[0].layout.blocks[1].color='red';assert.doesNotThrow(()=>importPlan(named,makeExport(named,'c',0,0),'c'));
if(process.argv[3]){
 const html=fs.readFileSync(process.argv[3],'utf8');const payload=JSON.parse(html.split('<script id="data" type="application/json">')[1].split('</script>')[0]);
 assert.doesNotThrow(()=>importPlan(payload.plan,makeExport(payload.plan,payload.source_hash,0,0),payload.source_hash));
}
if(out){fs.writeFileSync(path.join(out,'deleted.json'),JSON.stringify(restored));fs.writeFileSync(path.join(out,'empty.json'),JSON.stringify(exported));}
console.log('PASS: deletion cleanup, cascade, legacy cleanup, live-target immutability, empty-page draft, retained colors and optional built-editor self-roundtrip.');
