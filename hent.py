# -*- coding: utf-8 -*-
"""HENT: al dataindsamling til model.py - holdet, understat, Betfair og RotoWire.

  python hent.py holdet             priser/klubber -> holdet-DDMM.json; kampplan -> holdet-pl-schedule.json
  python hent.py liga [saeson]      understat-ligadata (default 2026; model.py bruger ogsaa 2025)
  python hent.py betfair <runde>    Match Odds + BTTS for PL -> bf-r<N>-MATCH_ODDS.json / -BOTH_TEAMS_TO_SCORE.json
  python hent.py rotowire <runde>   forudsagte opstillinger + skader -> rw-r<N>.json

Alt gemmes i input/. Repoet indeholder ingen data, og du er selv ansvarlig for at bruge kilderne efter
deres vilkaar. Del ikke de hentede filer videre.

holdet-API'et er aabent for spillerlisten og kampplanen. Forkerte stier giver 200 med en HTML-skal,
saa svaret skal vaere JSON med de forventede noegler (stopper ellers). Bank og rang ligger bag login.

Faelderne er bygget ind som porte: understat uden 'X-Requested-With: XMLHttpRequest' svarer 404-HTML paa
461 bytes (stopper); Betfair hentes med locale=en (dansk giver 'Uafgjort'/'Nej' og bryder parseren);
RotoWire-blokke tildeles den klub, hvis SPILLERE dominerer dem (parringen af klubnavne glider).
Kampdata (getMatchData) hentes af facit_alle.kamp().
"""
import collections, gzip, html, io, json, os, re, sys, time, unicodedata, urllib.request

SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "input")   # al data (gitignoreret)
os.makedirs(SP, exist_ok=True)
GAME_ID = 624            # holdet.dk Premier Manager Efteraar 2026; ret til naeste saesons spil
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36"
UK = {"Arsenal": "ARS", "Aston Villa": "AVL", "Bournemouth": "BOU", "Brentford": "BRE", "Brighton": "BHA",
      "Chelsea": "CHE", "Coventry": "COV", "Crystal Palace": "CRY", "Everton": "EVE", "Fulham": "FUL",
      "Hull": "HUL", "Ipswich": "IPS", "Leeds": "LEE", "Liverpool": "LIV", "Manchester City": "MCI",
      "Manchester United": "MUN", "Newcastle United": "NEW", "Nottingham Forest": "NFO",
      "Sunderland": "SUN", "Tottenham": "TOT"}


class DataFejl(Exception):
    pass


def hent_json(sti, noegler):
    req = urllib.request.Request("https://understat.com/" + sti, headers={
        "User-Agent": UA, "X-Requested-With": "XMLHttpRequest", "Accept-Encoding": "gzip",
        "Referer": "https://understat.com/league/EPL"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    if len(raw) < 1000 or raw[:1] != b"{":
        raise DataFejl("understat %s: %d bytes, ikke JSON (manglende XHR-header?)" % (sti, len(raw)))
    d = json.loads(raw.decode("utf-8"))
    mangler = [k for k in noegler if k not in d]
    if mangler:
        raise DataFejl("understat %s: mangler noegler %s" % (sti, mangler))
    return d


def spiller(pid, max_timer=24.0):
    """getPlayerData/<pid>, cachet i SP. Genhentes hvis cachen er aeldre end max_timer."""
    fn = os.path.join(SP, "us-p-%s.json" % pid)
    if os.path.exists(fn) and (time.time() - os.path.getmtime(fn)) / 3600 < max_timer:
        return json.load(io.open(fn, encoding="utf-8"))
    d = hent_json("getPlayerData/%s" % pid, ("matches", "groups", "shots"))
    json.dump(d, io.open(fn, "w", encoding="utf-8"), ensure_ascii=False)
    time.sleep(0.5)  # hoeflig mod serveren
    return d


def hold_pr_saeson(d):
    ud = {}
    for g in d["groups"]["season"]:
        ud.setdefault(g["season"], set()).add(g["team"])
    return ud


def egen_og_modstander(m, hold):
    """Spillerens hold og modstander i en kamp (matches-posterne siger ikke selv, hvem han spillede for)."""
    t = hold.get(m["season"], set())
    if m["h_team"] in t:
        return m["h_team"], m["a_team"]
    if m["a_team"] in t:
        return m["a_team"], m["h_team"]
    return None, None


def liga(saeson=2026):
    d = hent_json("getLeagueData/EPL/%d" % saeson, ("teams", "players", "dates"))
    fn = os.path.join(SP, "us-league-%d.json" % saeson)
    json.dump(d, io.open(fn, "w", encoding="utf-8"), ensure_ascii=False)
    return fn, sum(1 for x in d["dates"] if x["isResult"])


# ---------- Betfair (boersens midtpunkt = sandsynlighed uden margin) ----------
def bf_noegle():
    """Betfairs offentlige web-endpoints kraever en app-noegle (_ak). Repoet indeholder ingen; saet BETFAIR_AK."""
    ak = os.environ.get("BETFAIR_AK")
    if not ak:
        raise DataFejl("Betfair: saet miljoevariablen BETFAIR_AK (app-noeglen, som betfair.com's egen side bruger)")
    return ak


def _http(url, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def holdet():
    """Spillere (pris, startpris, klub, position) og kampplan fra holdet.dk. Kampplanen overskrives som
    holdet-pl-schedule.json, som model.py vaelger (sorterer efter de daterede filer)."""
    ud = []
    for sti, fn, noegler in (("games/%d/players?page.size=1000" % GAME_ID, "holdet-%s.json" % time.strftime("%d%m"), ("items", "_embedded")),
                             ("schedules/%d" % GAME_ID, "holdet-pl-schedule.json", ("rounds", "events"))):
        raw = _http("https://www.holdet.dk/api/season/" + sti)
        try:
            d = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise DataFejl("holdet %s: ikke JSON (%d bytes) - HTML-skal paa forkert sti?" % (sti, len(raw)))
        mangler = [k for k in noegler if k not in d]
        if mangler:
            raise DataFejl("holdet %s: mangler noegler %s" % (sti, mangler))
        json.dump(d, io.open(os.path.join(SP, fn), "w", encoding="utf-8"), ensure_ascii=False)
        ud.append((fn, len(d.get("items") or d.get("events") or [])))
    return ud


def betfair(runde):
    """Markeds-id'er via facet-soegning (EPL = 10932509), derefter priser. Begge markedstyper til samme runde."""
    ud, BF_AK = [], bf_noegle()
    for kode in ("MATCH_ODDS", "BOTH_TEAMS_TO_SCORE"):
        # markedstypen SKAL staa i hovedfiltret: i facettens 'next'-filter ignoreres den, og svaret bliver Match Odds
        # for begge typer - uden fejl, saa runden falder stille ud af holdstyrken (kvalitet.py stopper nu)
        body = {"filter": {"marketBettingTypes": ["ODDS"], "productTypes": ["EXCHANGE"], "contentGroup": {"language": "en", "regionCode": "UK"},
                           "selectBy": "RANK", "maxResults": 0, "eventTypeIds": [1], "competitionIds": [10932509],
                           "marketTypeCodes": [kode]},
                "facets": [{"type": "EVENT", "maxValues": 40, "skipValues": 0, "applyNextTo": 0,
                            "next": {"type": "MARKET", "maxValues": 4, "skipValues": 0}}],
                "currencyCode": "DKK", "locale": "en_GB"}
        fac = json.loads(_http("https://scan-inbf.betfair.com/www/sports/navigation/facet/v1/search?_ak=%s&alt=json" % BF_AK,
                               json.dumps(body).encode()))
        mids = [m["key"]["marketId"] for v in fac["facets"][0]["values"] for m in v.get("next", {}).get("values", [])[:1]]
        if not mids:
            raise DataFejl("Betfair: ingen %s-markeder fundet" % kode)
        raw = _http("https://ero.betfair.com/www/sports/exchange/readonly/v1/bymarket?_ak=%s&alt=json&currencyCode=GBP&locale=en"
                    "&marketIds=%s&types=EVENT,MARKET_STATE,MARKET_DESCRIPTION,RUNNER_DESCRIPTION,RUNNER_EXCHANGE_PRICES_BEST"
                    % (BF_AK, ",".join(mids[:40])))
        d = json.loads(raw)
        navne = {r["description"]["runnerName"] for et in d.get("eventTypes", []) for e in et["eventNodes"] for m in e["marketNodes"] for r in m["runners"]}
        if navne & {"Uafgjort", "Ja", "Nej"}:
            raise DataFejl("Betfair svarede paa dansk - parseren forventer engelske runner-navne")
        typer = {m["description"].get("marketType") for et in d.get("eventTypes", []) for e in et["eventNodes"] for m in e["marketNodes"]}
        if typer != {kode}:
            raise DataFejl("Betfair svarede med markedstyperne %s, ikke kun %s" % (sorted(typer), kode))
        fn = os.path.join(SP, "bf-r%d-%s.json" % (runde, kode))
        json.dump(d, io.open(fn, "w", encoding="utf-8"), ensure_ascii=False)
        ud.append((fn, len(mids)))
    return ud


# ---------- RotoWire ----------
def _norm(x):
    return "".join(c for c in unicodedata.normalize("NFD", x or "") if unicodedata.category(c) != "Mn").lower()


def rotowire(runde):
    """lineups.php -> {klub: {xi, out, ques, sikkerhed}}. Klubben for en blok = den klub, hvis spillere dominerer den
    (efternavne slaas op i holdet-filen via model.holdet()); blokke med under 6 genkendte spillere kasseres."""
    import model as M
    s = _http("https://www.rotowire.com/soccer/lineups.php").decode("utf-8", "replace")
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " | ", s)))
    pos = "GK|DL|DC|DR|DML|DMC|DMR|ML|MC|MR|AML|AMC|AMR|FWL|FWR|FW"
    re_xi = re.compile(r"\| (?:" + pos + r") \| \| ([^|]+?) \|")
    re_inj = re.compile(r"\| ([^|]+?) \| \| (OUT|QUES) \|")
    H = M.holdet()
    pers, teams = H["_embedded"]["persons"], H["_embedded"]["teams"]
    efter = collections.defaultdict(set)
    for it in H["items"]:
        efter[_norm(pers[str(it["personId"])].get("lastName") or "").split(" ")[-1]].add(M.H2F[teams[str(it["teamId"])]["abbreviation"]])
    def klub(navne):
        c = collections.Counter(kl for n in navne for kl in efter.get(_norm(n).split()[-1], ()))
        return c.most_common(1)[0] if c else (None, 0)
    pl = [m.start() for m in re.finditer("Predicted Lineup|Confirmed Lineup", t)]
    ud = {}
    for i, a in enumerate(pl):
        lineup, _, rest = t[a:pl[i + 1] if i + 1 < len(pl) else len(t)].partition("Injuries")
        xi = [x.strip() for x in re_xi.findall(lineup)][:11]
        kl, n = klub(xi) if len(xi) >= 8 else (None, 0)
        if kl is None or n < 6 or kl in ud:
            continue
        inj = re_inj.findall(rest)
        ud[kl] = {"xi": xi, "sikkerhed": "%d/%d" % (n, len(xi)), "bekraeftet": "Confirmed" in t[a:a + 20],
                  "out": [x.strip() for x, k in inj if k == "OUT"], "ques": [x.strip() for x, k in inj if k == "QUES"]}
    fn = os.path.join(SP, "rw-r%d.json" % runde)
    json.dump(ud, io.open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return fn, ud


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["holdet"]:
        for fn, n in holdet():
            print("skrevet %s (%d poster)" % (fn, n))
    elif a[:1] == ["liga"]:
        print("skrevet %s (%d kampe spillet)" % liga(int(a[1]) if len(a) > 1 else 2026))
    elif a[:1] == ["betfair"]:
        for fn, n in betfair(int(a[1])):
            print("skrevet %s (%d markeder)" % (fn, n))
    elif a[:1] == ["rotowire"]:
        fn, ud = rotowire(int(a[1]))
        print("skrevet %s: %d af 20 klubber" % (fn, len(ud)))
        for k in sorted(ud):
            print("  %-4s %-5s %s OUT %d QUES %d" % (k, ud[k]["sikkerhed"], "bekraeftet" if ud[k]["bekraeftet"] else "forudsagt ", len(ud[k]["out"]), len(ud[k]["ques"])))
    else:
        print(__doc__)
