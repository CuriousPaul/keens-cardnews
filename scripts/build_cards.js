#!/usr/bin/env node
/**
 * build_cards.js — Keens 카드뉴스 범용 빌드 엔진 (도구 중립)
 *
 *   콘텐츠 배치 JSON + 배경 폴더  ──►  카드 PNG(게시물별 폴더)
 *                                   + publish_manifest.json
 *                                   + publish_schedule.csv   (노코드 도구용)
 *
 * 이 엔진은 "발행"을 하지 않습니다. 발행/인게이지먼트는 매니페스트를 읽는
 * 어떤 도구로도(Make·Zapier·Buffer·Later·수동·cron·n8n) 갈아끼울 수 있습니다.
 *
 * 사용법:
 *   npm i puppeteer
 *   node build_cards.js <batch.json> <out_dir> <bg_dir> [options]
 * 옵션:
 *   --template <file>     카드 템플릿 (기본 card_template_keens.html)
 *   --handle <@name>      푸터 핸들 (기본 @KEENSACADEMY)
 *   --base-url <url>      카드 이미지가 호스팅될 공개 URL 베이스 (CSV의 image url 생성)
 *   --start <YYYY-MM-DD>  첫 게시 예약일 (기본: 내일)
 *   --cadence <n>         며칠 간격으로 예약 (기본 1 = 매일)
 *   --skip-weekends       주말 건너뛰기
 *
 * 예:
 *   node build_cards.js us_batch.json out/us mvp/bg_fixed \
 *     --base-url https://cdn.example.com/keens/us --start 2026-06-22 --skip-weekends
 */
const fs = require('fs'), path = require('path');
const puppeteer = require('puppeteer');

function parseArgs(argv){
  const a = { _: [] };
  for (let i=0;i<argv.length;i++){
    const t = argv[i];
    if (t.startsWith('--')){ const k=t.slice(2); const n=argv[i+1];
      if (!n || n.startsWith('--')){ a[k]=true; } else { a[k]=n; i++; } }
    else a._.push(t);
  }
  return a;
}
function ymd(d){ return d.toISOString().slice(0,10); }
function addDays(d,n){ const x=new Date(d); x.setDate(x.getDate()+n); return x; }

function scheduleDates(n, startStr, cadence, skipWeekends){
  const out=[]; let d = startStr ? new Date(startStr) : addDays(new Date(),1);
  while (out.length < n){
    const dow = d.getDay();
    if (!(skipWeekends && (dow===0||dow===6))) out.push(ymd(d));
    d = addDays(d, cadence||1);
  }
  return out;
}

async function build(){
  const args = parseArgs(process.argv.slice(2));
  const [batchPath, outDir, bgDir] = args._;
  if (!batchPath || !outDir){ console.error('usage: node build_cards.js <batch.json> <out_dir> <bg_dir> [options]'); process.exit(1); }
  const templatePath = path.resolve(args.template || 'card_template_keens.html');
  const baseUrl = (args['base-url'] || 'https://REPLACE-WITH-YOUR-HOST/keens').replace(/\/$/,'');
  const handle = args.handle || null;

  const batch = JSON.parse(fs.readFileSync(batchPath,'utf8'));
  // bare 배열 배치(검증배치·boys 등)와 {posts:[...]} 래퍼 배치 모두 허용.
  const posts = Array.isArray(batch) ? batch : (batch.posts || []);
  const bgs = bgDir ? fs.readdirSync(bgDir).filter(f=>f.endsWith('.png')||f.endsWith('.jpg'))
                        .sort().map(f=>'file://'+path.resolve(bgDir,f)) : [];
  fs.mkdirSync(outDir,{recursive:true});

  const dates = scheduleDates(posts.length, args.start, parseInt(args.cadence||'1'), !!args['skip-weekends']);

  const browser = await puppeteer.launch({ headless:'new', args:['--no-sandbox','--disable-setuid-sandbox','--allow-file-access-from-files','--font-render-hinting=none'] });
  const page = await browser.newPage();
  await page.setViewport({ width:1080, height:1350, deviceScaleFactor:2 });
  await page.goto('file://'+templatePath, { waitUntil:'networkidle0' });
  if (handle) await page.evaluate(h => document.documentElement.style.setProperty('--handle', "'"+h+"'"), handle);

  const manifest = { brand:'Keens', generated_at:new Date().toISOString(), base_url:baseUrl, posts:[] };
  let g=0;

  for (let p=0; p<posts.length; p++){
    const post = posts[p];
    post.cards.forEach(c => { if (!c.bg && bgs.length){ c.bg = bgs[g % bgs.length]; g++; } });

    const postDir = path.join(outDir, post.post_id);
    fs.mkdirSync(postDir, { recursive:true });

    await page.evaluate(d => { window.CARD_DATA = d; window.build(); }, post);
    await page.evaluate(() => document.fonts.ready);
    await new Promise(r=>setTimeout(r,300));

    const cards = await page.$$('.card');
    const files=[], urls=[];
    for (let i=0;i<cards.length;i++){
      const name = `${String(i+1).padStart(2,'0')}.png`;
      await cards[i].screenshot({ path: path.join(postDir, name) });
      files.push(path.join(post.post_id, name));
      urls.push(`${baseUrl}/${post.post_id}/${name}`);
    }
    const caption = [post.caption, ''].filter(Boolean).join('\n');
    manifest.posts.push({
      post_id: post.post_id,
      lang: post.lang || batch.lang || 'en',
      status: 'ready',                       // ready -> scheduled -> posted (도구가 갱신)
      scheduled_date: dates[p],
      dm_keyword: post.dm_keyword || batch.dm_keyword || '',
      card_count: files.length,
      caption: post.caption || '',
      image_files: files,
      image_urls: urls,
      local_folder: path.resolve(postDir)
    });
  }
  await browser.close();

  // publish_manifest.json
  fs.writeFileSync(path.join(outDir,'publish_manifest.json'), JSON.stringify(manifest,null,2));

  // publish_schedule.csv  (노코드 도구가 바로 읽는 평면 포맷)
  const esc = s => '"'+String(s==null?'':s).replace(/"/g,'""')+'"';
  const header = ['post_id','status','scheduled_date','dm_keyword','card_count','caption','image_urls'];
  const rows = manifest.posts.map(p => [
    p.post_id, p.status, p.scheduled_date, p.dm_keyword, p.card_count,
    p.caption, p.image_urls.join(' | ')
  ].map(esc).join(','));
  fs.writeFileSync(path.join(outDir,'publish_schedule.csv'), [header.map(esc).join(','), ...rows].join('\n'));

  console.log(`built ${manifest.posts.length} posts -> ${outDir}`);
  console.log(`  publish_manifest.json, publish_schedule.csv`);
}

build().catch(e=>{ console.error(e); process.exit(1); });
