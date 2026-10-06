(() => {
  const root = document.querySelector('#text-inspection');
  const data = JSON.parse(document.querySelector('#text-panel-data').textContent);
  const $ = id => root.querySelector(`#${id}`);
  if (!data.comments) { root.textContent = '面板已更新。请退出程序后重新启动，加载新的检视服务。'; return; }
  const number = n => n === null || n === undefined ? '未知' : Number(n).toLocaleString('zh-CN');
  const position = value => value === null ? '位置未知' : `${String(Math.floor(value/60)).padStart(2,'0')}:${String(Math.floor(value%60)).padStart(2,'0')}`;
  const time = value => {
    if (!value) return '时间未知';
    const d = new Date(typeof value === 'number' ? value * 1000 : value);
    return Number.isNaN(d.getTime()) ? '时间未知' : d.toLocaleString('zh-CN', {year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
  };
  const make = (tag, text, className) => { const e=document.createElement(tag); if(text !== undefined) e.textContent=text; if(className) e.className=className; return e; };
  let channel='danmaku', keywords=[], page=0, range=null, listed=[];
  const pageSize=50;
  for (const c of ['comments','danmaku']) root.querySelector(`[data-count=${c}]`).textContent=number(data[c].length);
  for (const part of data.parts) {
    const option=make('option', `${part.page ? `P${part.page} · ` : ''}${part.name} · CID ${part.cid}`);
    option.value=String(part.cid); $('text-part').append(option);
  }
  if (!data.parts.length) { const option=make('option','尚未采样'); option.value='null'; $('text-part').append(option); }
  const publicPart = data.danmaku.find(r => r.origin === 'public');
  if (publicPart) $('text-part').value=String(publicPart.cid);
  function sourceRows() {
    const origin=$('text-origin').value;
    return data[channel].filter(r => (origin === 'all' || r.origin === origin) && ($('text-visibility').value==='all'||(r.visibility||'unknown')===$('text-visibility').value) && (channel === 'comments' || String(r.cid) === $('text-part').value));
  }
  function matches(row) { const text=row.text.toLocaleLowerCase(); return !keywords.length || ( $('text-match').value === 'all' ? keywords.every(k=>text.includes(k)) : keywords.some(k=>text.includes(k)) ); }
  const dictionaryKey=`blla-word-dictionary-${root.dataset.bvid}`;
  let customTerms=[];
  try { customTerms=window.BllaSampleWords.parseDictionary(localStorage.getItem(dictionaryKey)||''); }
  catch (_) { $('text-dictionary-status').textContent='保存的专名词典无法读取，当前使用默认词典。'; }
  $('text-dictionary').value=customTerms.join('\n');
  let tokenizer=new window.BllaSampleWords.Tokenizer(customTerms);
  const rankings=new Map();
  function showWords(rows) {
    const key=JSON.stringify([channel,$('text-part').value,$('text-origin').value,$('text-visibility').value]);
    if(!rankings.has(key)) {
      if(rankings.size>=12) rankings.delete(rankings.keys().next().value);
      rankings.set(key,tokenizer.rank(rows));
    }
    const result=rankings.get(key);
    $('text-words').replaceChildren();
    for (const {word,count} of result.items) {
      const b=make('button'); b.type='button'; b.append(make('span',word),make('span',number(count)));
      b.addEventListener('click',()=>{ $('text-keyword').value=word; apply(); }); $('text-words').append(b);
    }
    if(!result.items.length) $('text-words').append(make('p',rows.length?'暂无可排行词语':'暂无文本样本','empty'));
    $('text-word-status').textContent=`${result.native?'中文分词＋专名保护':'当前内核不支持中文分词，仅显示受保护专名和英文词'}；${result.relaxed?'样本较少，显示出现 1 次的词':'仅列出现至少 2 次的词'}。同一条内重复出现会重复计数；点击词语按原文包含关系筛选。`;
  }
  $('text-dictionary-form').addEventListener('submit',event=>{
    event.preventDefault();
    let terms;
    try { terms=window.BllaSampleWords.parseDictionary($('text-dictionary').value); }
    catch(error) { $('text-dictionary-status').textContent=error.message; return; }
    tokenizer=new window.BllaSampleWords.Tokenizer(terms);rankings.clear();
    let saved=true;
    try { localStorage.setItem(dictionaryKey,terms.join('\n')); } catch (_) { saved=false; }
    $('text-dictionary-status').textContent=saved?`已保存 ${terms.length} 个专名，仅用于本视频、当前设备的词语排行。`:'专名已应用，但当前浏览器无法保存；刷新后失效。';
    render();
  });
  function kpi(title,value,note) { const e=make('div',undefined,'inspection-kpi');e.append(make('span',title),make('strong',value),make('small',note));return e; }
  function showDensity(rows) {
    const valid=rows.filter(r => r.position !== null);
    const part=data.parts.find(p=>String(p.cid)===$('text-part').value);
    const end=Math.max(Number(part?.duration)||0,...valid.map(r=>r.position),0);
    const bucket=Math.max(30,Math.ceil(end/120/30)*30);
    const bins=Array.from({length:valid.length ? Math.ceil((end+1)/bucket) : 0},(_,i)=>({start:i*bucket,total:0,hits:0}));
    for (const row of valid) { const b=bins[Math.floor(row.position/bucket)]; b.total++; if(matches(row)) b.hits++; }
    const peaks=[...bins].filter(b=>b.total).sort((a,b)=>b.total-a.total || a.start-b.start).slice(0,3);
    const max=Math.max(1,...bins.map(b=>b.total));
    $('text-bars').replaceChildren();$('text-peaks').replaceChildren();
    $('text-bucket-label').textContent=`每 ${bucket} 秒一段 · 已知位置 ${number(valid.length)} 条`;
    const choose = b => { range={start:b.start,end:b.start+bucket}; page=0; render(); };
    bins.forEach((b,i)=> {
      const button=make('button');button.type='button';button.style.setProperty('--bar-height', `${Math.max(2,b.total/max*100)}%`);
      button.style.setProperty('--hit-height', `${b.total ? b.hits/b.total*100 : 0}%`);
      button.title=`${position(b.start)}–${position(b.start+bucket)}：样本 ${b.total} 条，命中 ${b.hits} 条`;
      button.setAttribute('aria-label',button.title);button.setAttribute('aria-pressed',String(range?.start===b.start));
      if (i%Math.max(1,Math.ceil(bins.length/8))===0) button.append(make('span',position(b.start)));
      button.addEventListener('click',()=>choose(b));$('text-bars').append(button);
    });
    peaks.forEach((b,i)=>{const button=make('button', `#${i+1} ${position(b.start)}–${position(b.start+bucket)} · ${b.total} 条`);button.type='button';button.addEventListener('click',()=>choose(b));$('text-peaks').append(button);});
    if (!valid.length) $('text-bars').append(make('p','尚无已知视频位置的弹幕样本','empty'));
    return {peak:peaks[0],bucket,unknown:rows.length-valid.length};
  }
  function highlight(element,text) {
    if (!keywords.length) { element.textContent=text; return; }
    const lower=text.toLocaleLowerCase(); let i=0;
    while(i<text.length) {
      let start=text.length,word='';
      for(const k of keywords) { const at=lower.indexOf(k,i); if(at>=0 && (at<start || (at===start && k.length>word.length))) {start=at;word=k;} }
      element.append(document.createTextNode(text.slice(i,start)));
      if(!word) break;
      element.append(make('mark',text.slice(start,start+word.length))); i=start+word.length;
    }
  }
  function showList() {
    const maxPage=Math.max(0,Math.ceil(listed.length/pageSize)-1);page=Math.min(page,maxPage);
    $('text-list').replaceChildren();
    for(const row of listed.slice(page*pageSize,(page+1)*pageSize)) {
      const card=make('article',undefined,'inspection-item');
      const meta = channel==='danmaku' ? `${position(row.position)} · 发送 ${time(row.sent)}` : `${row.author} · ${row.parent ? '回复' : '主评论'} · 点赞 ${number(row.likes)} · 回复数 ${number(row.replies)} · 发布 ${time(row.sent)}`;
      const visibility=row.origin==='local'?'本地文本':row.visibility==='observed'?'上次采集可见':row.visibility==='placeholder'?'疑似已删除（接口占位）':'当前可见性未核验';
      card.append(make('div',`${visibility}${row.checked?` · 核验 ${time(row.checked)}`:''}`,'inspection-meta'));
      card.append(make('div',`${meta} · ${row.origin==='local' ? '本地导入／演示' : '公开采样'}`,'inspection-meta'));
      const body=make('p');highlight(body,row.text);card.append(body);$('text-list').append(card);
    }
    if(!listed.length) $('text-list').append(make('p','当前条件下没有样本。可采样文本，或调整关键词、来源与分 P。','empty'));
    $('text-page').textContent=`${listed.length ? page+1 : 0} / ${listed.length ? maxPage+1 : 0} 页 · 每页 ${pageSize} 条`;
    $('text-prev').disabled=page===0; $('text-next').disabled=page>=maxPage;
    $('text-list').scrollTop=0;
  }
  function render() {
    $('text-collect-cid').value=/^\d+$/.test($('text-part').value) ? $('text-part').value : '';
    const rows=sourceRows(), hits=rows.filter(matches), dm=channel==='danmaku';
    $('text-density').hidden=!dm;$('text-part-filter').hidden=!dm;
    const info=dm ? showDensity(rows) : null;
    const liked=dm ? null : [...hits].sort((a,b)=>b.likes-a.likes)[0];
    $('text-kpis').replaceChildren(kpi('本通道样本',number(rows.length),dm ? '当前分 P · 当前来源' : '当前来源 · 含附带回复'),
      kpi('关键词命中',number(hits.length),keywords.length ? `${keywords.length} 个筛选词` : '未设置关键词，查看全部'),
      kpi('样本命中率',rows.length ? `${(hits.length/rows.length*100).toFixed(1)}%` : '—','分母为本通道样本'),
      kpi(dm ? '样本最密片段' : '样本最高点赞',dm ? (info.peak ? position(info.peak.start) : '—') : (liked ? number(liked.likes) : '—'),dm ? (info.peak ? `${info.peak.total} 条 / ${info.bucket} 秒` : '无已知位置样本') : '仅比较当前命中评论'));
    const origin=$('text-origin').value;
    const prefix=origin==='public' ? '公开样本' : origin==='local' ? '本地导入／演示样本' : '混合来源样本';
    $('text-conclusion').textContent=rows.length ? (dm ? `${prefix}中，${info.peak ? `${position(info.peak.start)}–${position(info.peak.start+info.bucket)} 最集中，${info.peak.total} 条，占本通道样本 ${(info.peak.total/rows.length*100).toFixed(1)}%。` : '没有已知视频位置，不能定位峰值。'}关键词命中 ${hits.length} 条。${info.unknown ? `${info.unknown} 条位置未知，未计入分布。` : ''}这是样本热点，不能据此判断全量弹幕的峰值或新增量。` : `${prefix}中，主评论 ${rows.filter(r=>!r.parent).length} 条、附带回复 ${rows.filter(r=>r.parent).length} 条；关键词命中 ${hits.length} 条${liked ? `，命中样本最高点赞 ${liked.likes}` : ''}。单页及附带回复有选择偏差，不能推断整体观点或情绪。`) : '尚无可分析样本。采样后将展示命中率、片段峰值和原文证据；不会自动生成结论。';
    showWords(rows);
    listed=hits.filter(r=>!range || !dm || (r.position !== null && r.position>=range.start && r.position<range.end));
    const sort=$('text-sort').value;
    listed.sort((a,b)=>sort==='likes' && !dm ? b.likes-a.likes : sort==='position' && dm ? (a.position ?? Infinity)-(b.position ?? Infinity) : (b.sent||0)-(a.sent||0));
    $('text-list-scope').textContent=`${range && dm ? `${position(range.start)}–${position(range.end)} · ` : ''}符合条件 ${number(listed.length)} 条，分页检视。图表及命中统计使用本通道全部已加载样本。`;
    $('text-clear-range').hidden=!range || !dm;showList();
  }
  function apply() { keywords=[...new Set($('text-keyword').value.toLocaleLowerCase().split(/[\s,，]+/).filter(Boolean))].slice(0,12);page=0;range=null;render(); }
  $('text-filter').addEventListener('submit',event=>{event.preventDefault();apply();});
  for(const id of ['text-origin','text-part','text-match','text-sort','text-visibility']) $(id).addEventListener('change',apply);
  $('text-reset').addEventListener('click',()=>{ $('text-keyword').value='';$('text-match').value='any';$('text-origin').value='public';$('text-visibility').value='all';$('text-sort').value='position';apply(); });
  $('text-clear-range').addEventListener('click',()=>{range=null;page=0;render();});
  $('text-prev').addEventListener('click',()=>{page=Math.max(0,page-1);showList();});$('text-next').addEventListener('click',()=>{page++;showList();});
  const tabs=[...root.querySelectorAll('[data-channel]')];
  for(const tab of tabs) {
    tab.addEventListener('click',()=>{channel=tab.dataset.channel;page=0;range=null;for(const t of tabs){t.setAttribute('aria-selected',String(t===tab));t.tabIndex=t===tab?0:-1;}$('text-channel').setAttribute('aria-labelledby',tab.id);render();window.bllaMotion?.enter($('text-channel'));});
    tab.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();const next=tabs.find(t=>t!==tab);next.focus();next.click();}});
  }
  render();
})();
