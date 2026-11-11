// Read-only browser regression for the local annotation page; never submits labels.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const root=fileURLToPath(new URL('../../../',import.meta.url));
const base=process.env.ANNOTATION_BASE_URL||'http://127.0.0.1:8770';
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname));
const browser=await chromium.launch({headless:true});
const errors=[];
async function ready(page){
  await page.waitForFunction(()=>/\d+\/\d+ đã duyệt/.test(document.getElementById('progress')?.textContent||''),{},{timeout:12000});
  assert.equal(await page.locator('#error').textContent(),'');
}
try{
  const first=await browser.newPage(),second=await browser.newPage();
  for(const page of [first,second])page.on('pageerror',e=>errors.push(e.message));
  await Promise.all([first.goto(base,{waitUntil:'domcontentloaded'}),second.goto(base,{waitUntil:'domcontentloaded'})]);
  await Promise.all([ready(first),ready(second)]);
  const progress=await first.locator('#progress').textContent();
  assert.match(progress,/\/100 đã duyệt/);
  const recovery=await browser.newPage();
  recovery.on('pageerror',e=>errors.push(e.message));
  await recovery.route('**/api/items',async route=>{
    await new Promise(done=>setTimeout(done,10000));
    await route.abort().catch(()=>{});
  });
  await recovery.goto(base,{waitUntil:'domcontentloaded'});
  await recovery.locator('#retry').waitFor({state:'visible',timeout:12000});
  assert.equal(await recovery.locator('#progress').textContent(),'Chưa kết nối được');
  assert.equal(await recovery.locator('#save').isDisabled(),true);
  await recovery.unroute('**/api/items');
  await Promise.all([recovery.waitForNavigation({waitUntil:'domcontentloaded'}),recovery.locator('#retry').click()]);
  await ready(recovery);
  assert.deepEqual(errors,[]);
  const output=resolve(root,'.local/evidence/annotation-ui');
  await mkdir(output,{recursive:true});
  await writeFile(resolve(output,'report.json'),JSON.stringify({parallel_pages_loaded:true,progress,
    hung_request_timeout_shown:true,retry_recovered:true,labels_submitted:false,browser_errors:errors},null,2));
  console.log(JSON.stringify({parallel_pages_loaded:true,retry_recovered:true,labels_submitted:false}));
}finally{await browser.close();}
