/* Word boundaries are native ICU; protected phrases always occur contiguously in the input.
 * No cross-record concatenation, virtual-character splitting or synthesized suffixes. */
window.BllaSampleWords = (() => {
  const VERSION='native-words-1';
  const DEFAULT_WORDS=`周年 周年庆 六周年 生日快乐 快乐 好看 好帅 好听 前排 泪目 爷青回
    原神 米哈游 米游社 提瓦特 崩坏 绝区零 鸣潮 明日方舟 星穹铁道 三角洲行动
    炉石传说 王者荣耀 英雄联盟 塞尔达 黑神话 悟空
    蒙德 璃月 至冬 须弥 纳塔 枫丹 蒙德城 璃月港
    温迪 绫华 神里绫华 绫人 神里绫人 钟离 雷电将军 纳西妲 芙宁娜 巴巴托斯
    风神 岩神 雷神 草神 水神 火神 冰神 神之眼 元素反应 元素共鸣
    增幅反应 剧变反应 蒸发 融化 感电 超导 绽放 烈绽放 超绽放 深渊 尘歌壶
    幻想真境剧诗 抽卡 手游 龙脊雪山 流光拾遗之旅 神女劈观
    ChatGPT OpenAI Bilibili WebView2 GitHub AI GPU CPU API`.split(/\s+/);
  const STOP=new Set(`这个 那个 一个 一些 一下 一样 可以 不是 就是 还是 已经 正在
    我们 你们 他们 她们 它们 大家 现在 目前 今天 昨天 明天 时候 之后 以前 以后 之前
    因为 所以 但是 如果 虽然 什么 怎么 为什么 哪里 哪个 感觉 觉得 真的 非常 其实
    哈哈 呵呵 ok`.split(/\s+/));
  const ascii=c=>Boolean(c && /[a-z0-9_]/i.test(c));
  const fold=value=>value.replace(/[A-Z]/g,c=>c.toLowerCase());
  function parseDictionary(value){
    if(typeof value!=='string')throw Error('专名词典必须是文本');
    if(value.length>10000)throw Error('专名词典最多 10,000 字符');
    const terms=[...new Set(value.split(/[\r\n,，]+/).map(w=>w.trim()).filter(Boolean))];
    if(terms.length>200)throw Error('专名词典最多 200 个词');
    if(terms.some(w=>w.length<2||w.length>30||!/[\p{L}]/u.test(w)||!/^[\p{L}\p{N}_]+$/u.test(w)))
      throw Error('每词 2–30 字，可用中文、字母、数字、下划线；每行一个词');
    return terms;
  }
  class Tokenizer{
    constructor(extra=[]){
      this.segmenter=typeof Intl.Segmenter==='function'?new Intl.Segmenter('zh',{granularity:'word'}):null;
      this.cache=new Map();this.cacheUnits=0;this.trie=new Map();this.version=VERSION;
      for(const term of [...DEFAULT_WORDS,...extra]){
        let node=this.trie;
        for(const c of fold(term).split('')){if(!node.has(c))node.set(c,new Map());node=node.get(c);}
        node.term=term;
      }
    }
    valid(word){return word.length>=2 && /\p{L}/u.test(word) && !STOP.has(word.toLocaleLowerCase()) && !/^([哈呵啊哦嘿嘻])\1{2,}$/u.test(word);}
    tokenize(original){
      if(this.cache.has(original)){const hit=this.cache.get(original);this.cache.delete(original);this.cache.set(original,hit);return hit.words;}
      const words=[];
      // URLs and video IDs are noise, but removing them never joins surrounding text.
      for(const text of original.split(/https?:\/\/[^\s]+|www\.[^\s]+|\bBV[a-zA-Z0-9]{10}\b/gu)){
        const lower=fold(text);let position=0,plainStart=0;
        const plain=(start,end)=>{
          const fragment=text.slice(start,end);
          if(this.segmenter){for(const part of this.segmenter.segment(fragment))if(part.isWordLike&&this.valid(part.segment))words.push(part.segment);}
          else for(const word of fragment.match(/[a-zA-Z][a-zA-Z0-9_]+/g)||[])if(this.valid(word))words.push(word);
        };
        while(position<text.length){
          let node=this.trie,match=null;
          for(let end=position;end<lower.length&&node.has(lower[end]);end++){
            node=node.get(lower[end]);
            if(node.term){
              const candidate=text.slice(position,end+1);
              if(!/^[a-z0-9_]+$/i.test(candidate)||(!ascii(text[position-1])&&!ascii(text[end+1])))match={end:end+1,word:candidate};
            }
          }
          if(match){plain(plainStart,position);if(this.valid(match.word))words.push(match.word);position=match.end;plainStart=position;}
          else position++;
        }
        plain(plainStart,text.length);
      }
      const units=original.length+words.reduce((n,w)=>n+w.length,0);
      if(units<=500000){
        while(this.cache.size&&(this.cache.size>=2048||this.cacheUnits+units>500000)){
          const key=this.cache.keys().next().value;this.cacheUnits-=this.cache.get(key).units;this.cache.delete(key);
        }
        this.cache.set(original,{words,units});this.cacheUnits+=units;
      }
      return words;
    }
    rank(rows,limit=12,minCount=2){
      const counts=new Map();
      for(const row of rows)for(const word of this.tokenize(row.text)){
        const key=word.toLocaleLowerCase();const previous=counts.get(key);
        if(previous)previous.count++;else counts.set(key,{word,count:1});
      }
      const sorted=[...counts.values()].sort((a,b)=>b.count-a.count||a.word.localeCompare(b.word,'zh'));
      const common=sorted.filter(w=>w.count>=minCount),relaxed=!common.length&&sorted.length>0;
      return {items:(relaxed?sorted:common).slice(0,limit),relaxed,totalTerms:counts.size,native:Boolean(this.segmenter)};
    }
  }
  return {Tokenizer,parseDictionary,VERSION};
})();
