/**
 * 메이플통신 블로그 글 생성기 - 블로그 크롤링용 무료 프록시 (Cloudflare Workers)
 *
 * 역할: 네이버/티스토리/워드프레스 등의 RSS 피드를 서버에서 대신 가져와
 *       CORS 헤더를 붙여 돌려준다. (브라우저 CORS 차단 + 네이버 봇차단 우회)
 *
 * 사용: https://<내워커주소>.workers.dev/?url=https://rss.blog.naver.com/아이디.xml
 */
export default {
  async fetch(request) {
    const cors = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': '*',
    };
    if (request.method === 'OPTIONS') return new Response(null, { headers: cors });

    const target = new URL(request.url).searchParams.get('url');
    if (!target) {
      return new Response('사용법: ?url=가져올주소', { status: 400, headers: cors });
    }
    try {
      const r = await fetch(target, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; BlogReader/1.0)',
          'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        },
      });
      const body = await r.arrayBuffer();
      const ct = r.headers.get('content-type') || 'text/xml; charset=utf-8';
      return new Response(body, { status: r.status, headers: { ...cors, 'content-type': ct } });
    } catch (e) {
      return new Response('proxy error: ' + e.message, { status: 502, headers: cors });
    }
  },
};
