/**
 * 블로그 노출점수 측정 프록시 (Cloudflare Worker)
 * - 네이버 검색 API는 시크릿 노출/CORS 때문에 브라우저에서 직접 못 부릅니다.
 *   이 Worker가 중계해서 안전하게 호출합니다.
 *
 * 환경변수(Secrets) 2개를 반드시 설정하세요:
 *   NAVER_ID      = 네이버 애플리케이션 Client ID
 *   NAVER_SECRET  = 네이버 애플리케이션 Client Secret
 *
 * 호출: GET https://<worker>.workers.dev/?blogId=블로그아이디
 */
export default {
  async fetch(req, env) {
    const cors = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };
    if (req.method === 'OPTIONS') return new Response(null, { headers: cors });

    const url = new URL(req.url);
    const blogId = (url.searchParams.get('blogId') || '').trim().replace(/^@/, '').replace(/\s/g, '');
    if (!blogId) return json({ error: 'blogId 파라미터가 필요합니다.' }, 400, cors);
    if (!env.NAVER_ID || !env.NAVER_SECRET) {
      return json({ error: '서버에 네이버 키(NAVER_ID/NAVER_SECRET)가 설정되지 않았습니다.' }, 500, cors);
    }

    try {
      // 1) 블로그 RSS에서 최근 글 제목 수집
      const rssRes = await fetch('https://rss.blog.naver.com/' + encodeURIComponent(blogId) + '.xml', {
        headers: { 'User-Agent': 'Mozilla/5.0 (compatible; blogscore/1.0)' },
      });
      if (!rssRes.ok) {
        return json({ error: '블로그를 찾을 수 없거나 RSS가 비공개입니다. 아이디를 확인하세요.' }, 404, cors);
      }
      const xml = await rssRes.text();
      const items = parseRss(xml).slice(0, 8);
      if (!items.length) {
        return json({ error: '최근 글을 찾지 못했어요. (글이 없거나 RSS 비공개)' }, 404, cors);
      }

      // 2) 각 글 제목으로 블로그 검색 → 순위 측정 (병렬)
      const details = await Promise.all(items.map(async (it) => {
        const q = cleanQuery(it.title);
        const rank = q ? await searchRank(q, blogId, env) : 0;
        return { keyword: q, title: it.title, rank };
      }));

      // 3) 점수 환산
      const score = calcScore(details);
      return json({ blogId, score, checked: details.length, details }, 200, cors);
    } catch (e) {
      return json({ error: '측정 중 오류: ' + (e && e.message ? e.message : e) }, 500, cors);
    }
  },
};

function json(obj, status, cors) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...cors },
  });
}

function parseRss(xml) {
  const out = [];
  const re = /<item>([\s\S]*?)<\/item>/g;
  let m;
  while ((m = re.exec(xml)) && out.length < 15) {
    const block = m[1];
    const t = (block.match(/<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/title>/) || [])[1] || '';
    const l = (block.match(/<link>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/link>/) || [])[1] || '';
    if (t.trim()) out.push({ title: decodeEnt(t.trim()), link: l.trim() });
  }
  return out;
}
function decodeEnt(s) {
  return s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
}
function cleanQuery(t) {
  let q = t.replace(/\[[^\]]*\]/g, ' ').replace(/[^가-힣a-zA-Z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
  return q.split(' ').filter(Boolean).slice(0, 6).join(' ');
}
async function searchRank(query, blogId, env) {
  const api = 'https://openapi.naver.com/v1/search/blog.json?display=30&sort=sim&query=' + encodeURIComponent(query);
  const r = await fetch(api, {
    headers: { 'X-Naver-Client-Id': env.NAVER_ID, 'X-Naver-Client-Secret': env.NAVER_SECRET },
  });
  if (!r.ok) return 0;
  const d = await r.json();
  const items = d.items || [];
  const needle = 'blog.naver.com/' + blogId;
  for (let i = 0; i < items.length; i++) {
    const link = (items[i].link || '') + ' ' + (items[i].bloggerlink || '');
    if (link.indexOf(needle) >= 0) return i + 1;
  }
  return 0; // 상위 30위 안에 없음
}
function calcScore(details) {
  if (!details.length) return 0;
  let sum = 0;
  for (const d of details) {
    const r = d.rank;
    let s;
    if (r === 0) s = 8;
    else if (r === 1) s = 100;
    else if (r <= 3) s = 90;
    else if (r <= 7) s = 78;
    else if (r <= 10) s = 65;
    else if (r <= 20) s = 45;
    else s = 30;
    sum += s;
  }
  return Math.round(sum / details.length);
}
