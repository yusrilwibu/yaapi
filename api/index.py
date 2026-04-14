from http.server import BaseHTTPRequestHandler
import urllib.request, json, re, ssl
from urllib.parse import urlparse, parse_qs

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,*/*",
        "Accept-Language": "id-ID,id;q=0.9",
        "Referer": "https://otakudesu.cloud/"
    })
    with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
        return r.read().decode("utf-8", errors="ignore")

def parse_cards(html):
    items = []
    re_pat = re.compile(r'href="https://otakudesu\.cloud/anime/([^/]+)/"[\s\S]*?<img[^>]+src="([^"]+)"[\s\S]*?<h2[^>]*>([^<]+)</h2>', re.IGNORECASE)
    for m in re_pat.finditer(html):
        items.append({"animeId": m.group(1), "poster": m.group(2), "title": m.group(3).strip()})
    return items

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        page = qs.get("page", ["1"])[0]
        path = parsed.path

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            if "/ongoing" in path:
                html = fetch(f"https://otakudesu.cloud/ongoing-anime/page/{page}/")
                data = {"animeList": parse_cards(html)}
            elif "/completed" in path or "/complete" in path:
                html = fetch(f"https://otakudesu.cloud/complete-anime/page/{page}/")
                data = {"animeList": parse_cards(html)}
            elif "/search" in path:
                q = qs.get("q", [""])[0]
                html = fetch(f"https://otakudesu.cloud/?s={urllib.parse.quote(q)}&post_type=anime")
                data = {"animeList": parse_cards(html)}
            elif "/home" in path:
                html = fetch("https://otakudesu.cloud/")
                data = {"animeList": parse_cards(html)[:20]}
            elif "/schedule" in path:
                html = fetch("https://otakudesu.cloud/jadwal-rilis/")
                result = {}
                for day in ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]:
                    sec = re.search(f"<h2[^>]*>{day}</h2>([\s\S]*?)(?=<h2|$)", html, re.IGNORECASE)
                    if sec:
                        animes = [{"animeId": m.group(1), "title": m.group(2).strip()} for m in re.finditer(r'href="https://otakudesu\.cloud/anime/([^/]+)/"[^>]*>([^<]+)</a>', sec.group(1))]
                        if animes: result[day.lower()] = animes
                data = result
            elif "/genre" in path and re.search(r"/genre/([^/?]+)", path):
                gid = re.search(r"/genre/([^/?]+)", path).group(1)
                html = fetch(f"https://otakudesu.cloud/genres/{gid}/page/{page}/")
                data = {"animeList": parse_cards(html)}
            elif "/genre" in path:
                html = fetch("https://otakudesu.cloud/genre-list/")
                genres = [{"genreId": m.group(1), "name": m.group(2).strip()} for m in re.finditer(r'href="https://otakudesu\.cloud/genres/([^/]+)/"[^>]*>([^<]+)</a>', html)]
                data = {"genreList": genres}
            elif re.search(r"/anime/([^/?]+)", path):
                aid = re.search(r"/anime/([^/?]+)", path).group(1)
                html = fetch(f"https://otakudesu.cloud/anime/{aid}/")
                tM = re.search(r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>([^<]+)</h1>', html)
                pM = re.search(r'class="[^"]*fotoanime[^"]*"[\s\S]*?<img[^>]+src="([^"]+)"', html)
                sM = re.search(r'class="[^"]*sinopc[^"]*"[^>]*>([\s\S]*?)</div>', html)
                eps = [{"episodeId": m.group(1), "episodeNum": m.group(2)} for m in re.finditer(r'href="https://otakudesu\.cloud/episode/([^/]+)/"[^>]*>\s*Episode\s+(\d+)', html)]
                data = {"info": {"title": tM.group(1).strip() if tM else aid, "poster": pM.group(1) if pM else "", "synopsis": re.sub(r"<[^>]+>","",sM.group(1)).strip() if sM else "", "totalEpisodes": str(len(eps))}, "episodeList": list(reversed(eps))}
            elif re.search(r"/episode/([^/?]+)", path):
                eid = re.search(r"/episode/([^/?]+)", path).group(1)
                html = fetch(f"https://otakudesu.cloud/episode/{eid}/")
                tM = re.search(r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>([^<]+)</h1>', html)
                servers = []
                for m in re.finditer(r'data-video="([^"]+)"', html):
                    u = m.group(1)
                    if u.startswith("//"): u = "https:" + u
                    if u.startswith("/"): u = "https://otakudesu.cloud" + u
                    servers.append({"serverName": f"Server {len(servers)+1}", "qualities": [{"quality": "SD", "url": u}]})
                pM = re.search(r'href="https://otakudesu\.cloud/episode/([^/]+)/"[^>]*>[^<]*(?:Prev|laquo)', html, re.IGNORECASE)
                nM = re.search(r'href="https://otakudesu\.cloud/episode/([^/]+)/"[^>]*>[^<]*(?:Next|raquo)', html, re.IGNORECASE)
                data = {"title": tM.group(1).strip() if tM else eid, "streamingLink": servers, "prevEpisode": pM.group(1) if pM else None, "nextEpisode": nM.group(1) if nM else None}
            else:
                data = {"message": "Otakudesu API", "endpoints": ["/api/ongoing", "/api/completed", "/api/search?q=", "/api/home", "/api/anime?id=", "/api/episode?id=", "/api/schedule", "/api/genre"]}

            self.wfile.write(json.dumps({"statusCode": 200, "statusMessage": "OK", "data": data}).encode())
        except Exception as e:
            self.wfile.write(json.dumps({"statusCode": 500, "error": str(e)}).encode())
