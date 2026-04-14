from http.server import BaseHTTPRequestHandler
import urllib.request, json, re, ssl
from urllib.parse import urlparse, parse_qs, quote

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
        "Accept": "text/html,*/*",
        "Accept-Language": "id-ID,id;q=0.9",
        "Referer": "https://otakudesu.cloud/"
    })
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        return r.read().decode("utf-8", errors="ignore")

def parse_cards(html):
    items = []
    seen = set()
    # Pattern for anime cards on otakudesu
    for m in re.finditer(r'href="https://otakudesu\.cloud/anime/([^/"]+)/"', html):
        aid = m.group(1)
        if aid in seen: continue
        seen.add(aid)
        # Find poster near this link
        start = max(0, m.start()-500)
        end = min(len(html), m.end()+500)
        chunk = html[start:end]
        pm = re.search(r'<img[^>]+src="(https://[^"]+(?:jpg|jpeg|png|webp)[^"]*)"', chunk)
        tm = re.search(r'<h2[^>]*>([^<]+)</h2>', chunk)
        em = re.search(r'class="[^"]*epz[^"]*"[^>]*>([^<]+)<', chunk)
        items.append({
            "animeId": aid,
            "poster": pm.group(1) if pm else "",
            "title": tm.group(1).strip() if tm else aid,
            "episodes": em.group(1).strip() if em else None
        })
    return items

class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

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
                html = fetch("https://otakudesu.cloud/ongoing-anime/page/" + page + "/")
                data = {"animeList": parse_cards(html)}
            elif "/completed" in path or "/complete" in path:
                html = fetch("https://otakudesu.cloud/complete-anime/page/" + page + "/")
                data = {"animeList": parse_cards(html)}
            elif "/search" in path:
                q = qs.get("q", [""])[0]
                html = fetch("https://otakudesu.cloud/?s=" + quote(q) + "&post_type=anime")
                data = {"animeList": parse_cards(html)}
            elif "/home" in path:
                html = fetch("https://otakudesu.cloud/")
                data = {"animeList": parse_cards(html)[:20]}
            elif "/schedule" in path:
                html = fetch("https://otakudesu.cloud/jadwal-rilis/")
                result = {}
                for day in ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]:
                    sec = re.search("<h2[^>]*>" + day + "</h2>([\\s\\S]*?)(?=<h2|$)", html, re.IGNORECASE)
                    if sec:
                        animes = []
                        for m in re.finditer(r'href="https://otakudesu\.cloud/anime/([^/"]+)/"[^>]*>([^<]+)</a>', sec.group(1)):
                            animes.append({"animeId": m.group(1), "title": m.group(2).strip(), "poster": ""})
                        if animes: result[day.lower()] = animes
                data = result
            elif re.search(r"/genre/([^/?]+)", path):
                gid = re.search(r"/genre/([^/?]+)", path).group(1)
                html = fetch("https://otakudesu.cloud/genres/" + gid + "/page/" + page + "/")
                data = {"animeList": parse_cards(html)}
            elif "/genre" in path:
                html = fetch("https://otakudesu.cloud/genre-list/")
                genres = []
                for m in re.finditer(r'href="https://otakudesu\.cloud/genres/([^/"]+)/"[^>]*>([^<]+)</a>', html):
                    genres.append({"genreId": m.group(1), "name": m.group(2).strip()})
                data = {"genreList": genres}
            elif re.search(r"/anime/([^/?]+)", path):
                aid = re.search(r"/anime/([^/?]+)", path).group(1)
                html = fetch("https://otakudesu.cloud/anime/" + aid + "/")
                tM = re.search(r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>([^<]+)</h1>', html)
                pM = re.search(r'class="[^"]*fotoanime[^"]*"[\\s\\S]*?<img[^>]+src="([^"]+)"', html)
                sM = re.search(r'class="[^"]*sinopc[^"]*"[^>]*>([\\s\\S]*?)</div>', html)
                eps = []
                for m in re.finditer(r'href="https://otakudesu\.cloud/episode/([^/"]+)/"[^>]*>\\s*Episode\\s+(\\d+)', html):
                    eps.append({"episodeId": m.group(1), "episodeNum": m.group(2)})
                data = {
                    "info": {
                        "title": tM.group(1).strip() if tM else aid,
                        "poster": pM.group(1) if pM else "",
                        "synopsis": re.sub(r"<[^>]+>","",sM.group(1)).strip() if sM else "",
                        "totalEpisodes": str(len(eps))
                    },
                    "episodeList": list(reversed(eps))
                }
            elif re.search(r"/episode/([^/?]+)", path):
                eid = re.search(r"/episode/([^/?]+)", path).group(1)
                html = fetch("https://otakudesu.cloud/episode/" + eid + "/")
                tM = re.search(r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>([^<]+)</h1>', html)
                servers = []
                for m in re.finditer(r'data-video="([^"]+)"', html):
                    u = m.group(1)
                    if u.startswith("//"): u = "https:" + u
                    if u.startswith("/"): u = "https://otakudesu.cloud" + u
                    servers.append({"serverName": "Server " + str(len(servers)+1), "qualities": [{"quality": "SD", "url": u}]})
                pM = re.search(r'href="https://otakudesu\.cloud/episode/([^/"]+)/"[^>]*>[^<]*(?:Prev|laquo)', html, re.IGNORECASE)
                nM = re.search(r'href="https://otakudesu\.cloud/episode/([^/"]+)/"[^>]*>[^<]*(?:Next|raquo)', html, re.IGNORECASE)
                data = {
                    "title": tM.group(1).strip() if tM else eid,
                    "streamingLink": servers,
                    "prevEpisode": pM.group(1) if pM else None,
                    "nextEpisode": nM.group(1) if nM else None
                }
            else:
                data = {"message": "Otakudesu API Sub Indo", "routes": ["/api/index/ongoing", "/api/index/completed", "/api/index/search?q=naruto", "/api/index/home", "/api/index/anime/one-piece", "/api/index/episode/one-piece-episode-1-sub-indo", "/api/index/schedule", "/api/index/genre"]}

            self.wfile.write(json.dumps({"statusCode": 200, "statusMessage": "OK", "data": data}).encode())
        except Exception as e:
            self.wfile.write(json.dumps({"statusCode": 500, "error": str(e)}).encode())