"""Empirical browser checks for semantic boundaries, noise and bounded caching."""
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get('BILIBILI_MONITOR_HEADLESS_TEST') != '1',
    reason='opt-in headless rendering',
)
SCRIPT = Path(__file__).parents[1] / 'app/reports/templates/word_tokenizer.js'


@pytest.fixture
def page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.add_script_tag(content=SCRIPT.read_text(encoding='utf-8'))
        yield page
        browser.close()


def test_screenshot_regression_and_english_names(page):
    result = page.evaluate('''() => {
      const t=new BllaSampleWords.Tokenizer();
      return t.rank(Array.from({length:3},()=>({text:'原神六周年快乐！温迪生日快乐，绫华生日快乐，ChatGPT OpenAI API AI GPU CPU 666哈哈哈哈 https://example.com BV1xx411c7mD'})),50);
    }''')
    counts = {item['word']: item['count'] for item in result['items']}
    assert counts['生日快乐'] == 6
    assert all(word in counts for word in ['原神','六周年','温迪','绫华','ChatGPT','OpenAI','API','AI','GPU','CPU'])
    assert not set(['年快','六周','华生','日快','神六','666','哈哈哈哈','example','BV1xx411c7mD']) & counts.keys()


def test_original_boundaries_and_small_sample(page):
    result = page.evaluate('''() => {
      const t=new BllaSampleWords.Tokenizer(['歧路星遥','𠮷野家']);
      const texts=['生日','快乐','流光拾遗','之旅','生日，快乐','歧路星遥𠮷野家İ原神','training'];
      return {words:texts.map(text=>({text,words:t.tokenize(text)})),
        rank:t.rank([{text:'温迪'}])};
    }''')
    for row in result['words']:
        assert all(word in row['text'] for word in row['words'])
        assert '生日快乐' not in row['words']
        assert '流光拾遗之旅' not in row['words']
    assert '歧路星遥' in result['words'][5]['words']
    assert '𠮷野家' in result['words'][5]['words']
    assert 'AI' not in result['words'][6]['words']
    assert result['rank']['relaxed']


def test_validation_cache_and_fallback(page):
    result = page.evaluate(r'''() => {
      const errors=[];
      for(const s of ['a','1234','坏 词',Array(202).fill(0).map((_,i)=>'专名'+i).join('\n'),'原'.repeat(10001)]) {
        try { BllaSampleWords.parseDictionary(s); errors.push(false); } catch(_) { errors.push(true); }
      }
      const t=new BllaSampleWords.Tokenizer();
      for(let i=0;i<3000;i++) t.tokenize('温迪生日快乐 '+i);
      const before=t.cacheUnits;
      const a=t.rank([{text:'ChatGPT chatgpt'}]);
      const b=t.rank([{text:'ChatGPT chatgpt'}]);
      const native=Intl.Segmenter;Intl.Segmenter=undefined;
      const fallback=new BllaSampleWords.Tokenizer().rank([{text:'歧路星遥温迪 ChatGPT'}]);
      Intl.Segmenter=native;
      return {errors,size:t.cache.size,units:before,a,b,fallback};
    }''')
    assert all(result['errors'])
    assert result['size'] <= 2048 and result['units'] <= 500000
    assert result['a'] == result['b']
    assert result['a']['items'] == [{'word':'ChatGPT','count':2}]
    assert not result['fallback']['native']
    assert not {'歧路','路星','星遥'} & {item['word'] for item in result['fallback']['items']}
