"""Read-only local-sample word ranking benchmark; no messages/authors are printed."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1]))
from app.database import Repository
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--bvid', required=True)
    args = parser.parse_args()
    def connect():
        conn = sqlite3.connect(args.database.resolve().as_uri()+'?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    data = Repository(SimpleNamespace(connect=connect)).text_dashboard_data(args.bvid)
    rows = [{'text': r['text']} for r in data['danmaku'] if r['origin']=='public']
    script = Path(__file__).parents[1] / 'app/reports/templates/word_tokenizer.js'
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            page=browser.new_page()
            page.add_script_tag(content=script.read_text(encoding='utf-8'))
            result=page.evaluate('''rows => {
              const start=performance.now(),t=new BllaSampleWords.Tokenizer();
              const result=t.rank(rows),cold=performance.now()-start;
              const again=performance.now();t.rank(rows);const warm=performance.now()-again;
              const cache=new Map([['scope',result]]);
              const cached=performance.now();for(let i=0;i<10000;i++)cache.get('scope');
              const cachedMean=(performance.now()-cached)/10000;
              const oldStart=performance.now(),counts=new Map();
              for(const row of rows)for(const phrase of row.text.match(/[\\u4e00-\\u9fff]{2,}/g)||[])
                for(let i=0;i<phrase.length-1;i++) {const w=phrase.slice(i,i+2);counts.set(w,(counts.get(w)||0)+1);}
              const oldMs=performance.now()-oldStart;
              return {samples:rows.length,cold_ms:cold,warm_recount_ms:warm,cached_lookup_mean_ms:cachedMean,
                old_bigram_ms:oldMs,cache_entries:t.cache.size,cache_character_units:t.cacheUnits,
                semantic_top:result.items,old_bigram_top:[...counts].sort((a,b)=>b[1]-a[1]).slice(0,12)};
            }''',rows)
            print(json.dumps(result,ensure_ascii=False,indent=2))
        finally:
            browser.close()


if __name__=='__main__':
    main()
