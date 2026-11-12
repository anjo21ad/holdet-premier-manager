# -*- coding: utf-8 -*-
"""HENT: al dataindsamling til model.py - holdet, FotMob, odds og RotoWire.

  python hent.py holdet             priser/klubber -> holdet-DDMM.json; kampplan og resultater -> holdet-pl-schedule.json
  python hent.py fotmob             aarets PL-kampe -> fm-liga-PL-2026.json + fm-m-<kamp>.json (cache; kun nye kampe hentes)
  python hent.py fotmob historik    2024 og 2025 i PL og de fire andre topligaer (een gang; til Marcel-raten)
  python hent.py odds <runde>       Pinnacle: 1X2 og over/under 2,5 for rundens kampe -> od-r<N>.json
  python hent.py odds historik <N>  spillede runder 1..N fra football-data.co.uk (gennemsnitlige odds foer kampen)
  python hent.py rotowire <runde>   forudsagte opstillinger + skader -> rw-r<N>.json

Alt gemmes i input/. Repoet indeholder ingen data, og du er selv ansvarlig for at bruge kilderne efter
deres vilkaar. Del ikke de hentede filer videre.

holdet-API'et ligger under /api/fantasy/. Forkerte stier giver 200 eller 404 med en
HTML-skal, saa svaret skal vaere JSON med de forventede noegler (stopper ellers). Bank og rang ligger bag login.

Faelderne er bygget ind som porte: FotMob- og Pinnacle-svar skal vaere JSON med de forventede felter, en FotMob-kamp
skal have 22 startere og spillerstatistik, og en oddsfil skal have alle rundens kampe. RotoWire-blokke tildeles den
klub, hvis SPILLERE dominerer dem (parringen af klubnavne glider).
"""
import collections, gzip, html, io, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request

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


def _http(url, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def holdet():
    """Spillere (pris, startpris, klub, position) og kampplan (deadlines og resultater) fra holdet.dk's fantasy-API.
    Kampplanen overskrives som holdet-pl-schedule.json, som model.py vaelger (sorterer efter de daterede filer)."""
    ud = []
    for sti, fn, noegler in (("games/%d/players?page.size=1000" % GAME_ID, "holdet-%s.json" % time.strftime("%d%m"), ("items", "_embedded")),
                             ("schedules/%d" % GAME_ID, "holdet-pl-schedule.json", ("rounds", "events"))):
        raw = _http("https://www.holdet.dk/api/fantasy/" + sti)
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


# ---------- FotMob: kampe, starter, minutter, xG, xA, positioner og skud ----------
FM_LIGA = {"PL": 47, "L1": 53, "BL": 54, "SA": 55, "LL": 87}          # Premier League + de fire andre topligaer
FM_SAESON = {"2024": "2024/2025", "2025": "2025/2026", "2026": "2026/2027"}


def _fm(sti):
    req = urllib.request.Request("https://www.fotmob.com/api/data/" + sti, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    try:
        d = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise DataFejl("FotMob %s: ikke JSON (%d bytes) - flyttet sti?" % (sti, len(raw)))
    if not isinstance(d, dict):
        raise DataFejl("FotMob %s: uventet svar" % sti)
    return d


def fotmob_liga(liga, saeson):
    """Ligaens kampliste -> fm-liga-<liga>-<saeson>.json: id, runde, tid (UTC), faerdig, hold."""
    d = _fm("leagues?id=%d&season=%s" % (FM_LIGA[liga], urllib.parse.quote(FM_SAESON[saeson])))
    ms = d.get("fixtures", {}).get("allMatches") or []
    if not ms:
        raise DataFejl("FotMob %s %s: ingen kampe" % (liga, saeson))
    ud = [{"id": str(m["id"]), "runde": m.get("round"), "tid": m["status"].get("utcTime"), "faerdig": bool(m["status"].get("finished")),
           "aflyst": bool(m["status"].get("cancelled")), "h": m["home"]["name"], "a": m["away"]["name"],
           "h_id": str(m["home"]["id"]), "a_id": str(m["away"]["id"])} for m in ms]
    json.dump(ud, io.open(os.path.join(SP, "fm-liga-%s-%s.json" % (liga, saeson)), "w", encoding="utf-8"), ensure_ascii=False)
    return ud


def fotmob_kamp(mid):
    """Kompakt kamp -> fm-m-<id>.json (cache; en faerdig kamp aendrer sig ikke). Starter fra opstillingen,
    minutter, xG og xA fra spillerstatistikken, skud med situation (straffe) fra skudkortet."""
    fn = os.path.join(SP, "fm-m-%s.json" % mid)
    if os.path.exists(fn):
        return json.load(io.open(fn, encoding="utf-8"))
    md = _fm("matchDetails?matchId=%s" % mid)
    g, c = md.get("general", {}), md.get("content", {})
    hid, aid = str(g.get("homeTeam", {}).get("id")), str(g.get("awayTeam", {}).get("id"))
    lu, ps = c.get("lineup") or {}, c.get("playerStats") or {}
    start, pos = {}, {}
    for side, t in (("h", lu.get("homeTeam") or {}), ("a", lu.get("awayTeam") or {})):
        for p in t.get("starters") or []:
            start[str(p["id"])], pos[str(p["id"])] = side, p.get("positionId")
    if len(start) != 22 or not ps:
        raise DataFejl("FotMob kamp %s: %d startere, %d spillerstatistikker - mangler data" % (mid, len(start), len(ps)))
    spillere = []
    for pid, p in ps.items():
        top = {}
        for blok in p.get("stats") or []:
            for k, v in (blok.get("stats") or {}).items():
                top.setdefault(k, (v.get("stat") or {}).get("value"))
        side = "h" if str(p.get("teamId")) == hid else "a" if str(p.get("teamId")) == aid else None
        if side is None or not top.get("Minutes played"):
            continue
        spillere.append({"id": str(pid), "navn": p.get("name"), "hold": side, "start": str(pid) in start, "pos": pos.get(str(pid)),
                         "min": int(top.get("Minutes played") or 0), "xg": float(top.get("Expected goals (xG)") or 0),
                         "xa": float(top.get("Expected assists (xA)") or 0)})
    skud = [{"id": str(s.get("playerId")), "hold": "h" if str(s.get("teamId")) == hid else "a", "xg": float(s.get("expectedGoals") or 0),
             "sit": s.get("situation"), "type": s.get("eventType"), "selvmaal": bool(s.get("isOwnGoal"))}
            for s in (c.get("shotmap") or {}).get("shots") or []]
    ud = {"id": str(mid), "tid": g.get("matchTimeUTCDate"), "h": g.get("homeTeam", {}).get("name"), "a": g.get("awayTeam", {}).get("name"),
          "h_id": hid, "a_id": aid, "spillere": spillere, "skud": skud}
    json.dump(ud, io.open(fn, "w", encoding="utf-8"), ensure_ascii=False)
    time.sleep(0.3)  # hoeflig mod serveren
    return ud


def fotmob(ligaer, saesoner):
    """Kamplister og alle faerdige kampe; returnerer (hentet, fra cache, fejl)."""
    n_ny = n_cache = 0; fejl = []
    for liga in ligaer:
        for saeson in saesoner:
            for m in fotmob_liga(liga, saeson):
                if not m["faerdig"] or m["aflyst"]:
                    continue
                if os.path.exists(os.path.join(SP, "fm-m-%s.json" % m["id"])):
                    n_cache += 1
                    continue
                try:
                    fotmob_kamp(m["id"]); n_ny += 1
                except Exception as e:
                    fejl.append((liga, saeson, m["id"], str(e)[:100]))
            print("  %s %s faerdig: %d nye, %d i cache, %d fejl" % (liga, saeson, n_ny, n_cache, len(fejl)), flush=True)
    return n_ny, n_cache, fejl


# ---------- odds: Pinnacle (naeste runde) og football-data.co.uk (spillede runder) ----------
KODE = dict(UK, **{"Coventry City": "COV", "Hull City": "HUL", "Ipswich Town": "IPS", "Leeds United": "LEE", "Tottenham Hotspur": "TOT",
                   "Brighton and Hove Albion": "BHA", "Brighton & Hove Albion": "BHA", "AFC Bournemouth": "BOU", "Man City": "MCI",
                   "Man United": "MUN", "Man Utd": "MUN", "Newcastle": "NEW", "Nott'm Forest": "NFO", "Nottm Forest": "NFO", "Spurs": "TOT"})


def _odds_fil(runde, kilde, kampe):
    """od-r<N>.json: pr. kamp P(hjemme/uafgjort/ude) og P(over 2,5 maal), begge uden margin."""
    ud = {"runde": runde, "kilde": kilde, "hentet": time.strftime("%Y-%m-%dT%H:%M"), "kampe": kampe}
    fn = os.path.join(SP, "od-r%d.json" % runde)
    json.dump(ud, io.open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return fn, len(kampe)


def _rundens_par(runde):
    import model as M
    return set(M.kampplan()[0].get(runde, []))


def pinnacle(runde):
    """Rundens kampe fra Pinnacles aabne guest-API: moneyline og total 2,5 (hovedlinje eller alternativ)."""
    g = lambda s: json.loads(_http("https://guest.api.arcadia.pinnacle.com/0.1/" + s).decode("utf-8"))
    mu, mk = g("leagues/1980/matchups"), g("leagues/1980/markets/straight")
    par, kampe = _rundens_par(runde), {}
    for m in mu:
        if m.get("type") != "matchup" or len(m.get("participants", [])) != 2:
            continue
        side = {p["alignment"]: KODE.get(p["name"]) for p in m["participants"]}
        if (side.get("home"), side.get("away")) in par:
            kampe[m["id"]] = {"h": side["home"], "a": side["away"], "tid": m.get("startTime")}
    dec = lambda am: 1 + (am / 100.0 if am > 0 else 100.0 / -am)
    for m in mk:
        k = kampe.get(m["matchupId"])
        if not k or m.get("period") != 0:
            continue
        pr = {p["designation"]: 1 / dec(p["price"]) for p in m.get("prices", [])}
        if m.get("type") == "moneyline" and not m.get("isAlternate") and {"home", "draw", "away"} <= set(pr):
            s = sum(pr.values()); k.update(pH=pr["home"] / s, pD=pr["draw"] / s, pA=pr["away"] / s)
        if m.get("type") == "total" and m["prices"][0].get("points") == 2.5 and {"over", "under"} <= set(pr):
            k["pOver25"] = pr["over"] / (pr["over"] + pr["under"])
    hele = [k for k in kampe.values() if "pH" in k and "pOver25" in k]
    if len(hele) < len(par):
        raise DataFejl("Pinnacle R%d: %d af %d kampe med 1X2 og total 2,5" % (runde, len(hele), len(par)))
    return _odds_fil(runde, "pinnacle", hele)


def odds_historik(runder, saeson="2627"):
    """Spillede runder fra football-data.co.uk: gennemsnitlige odds foer kampen (ikke lukkeodds) for 1X2 og over/under 2,5."""
    import csv
    raw = _http("https://www.football-data.co.uk/mmz4281/%s/E0.csv" % saeson).decode("utf-8-sig", "replace")
    rk = {(KODE.get(r["HomeTeam"]), KODE.get(r["AwayTeam"])): r for r in csv.DictReader(io.StringIO(raw))}
    ud = []
    for runde in runder:
        kampe = []
        for h, a in sorted(_rundens_par(runde)):
            r = rk.get((h, a))
            try:
                q = {x: 1 / float(r[k]) for x, k in (("H", "AvgH"), ("D", "AvgD"), ("A", "AvgA"), ("O", "Avg>2.5"), ("U", "Avg<2.5"))}
            except (TypeError, ValueError, KeyError):
                raise DataFejl("football-data R%d: mangler odds for %s-%s" % (runde, h, a))
            s = q["H"] + q["D"] + q["A"]
            kampe.append({"h": h, "a": a, "tid": r["Date"] + " " + r.get("Time", ""), "pH": q["H"] / s, "pD": q["D"] / s, "pA": q["A"] / s,
                          "pOver25": q["O"] / (q["O"] + q["U"])})
        ud.append(_odds_fil(runde, "football-data (gennemsnit foer kampen)", kampe))
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
    elif a[:1] == ["fotmob"]:
        hist = a[1:2] == ["historik"]
        ny_, cache, fejl = fotmob(list(FM_LIGA) if hist else ["PL"], ["2024", "2025"] if hist else ["2026"])
        print("FotMob: %d hentet, %d fra cache, %d fejl" % (ny_, cache, len(fejl)))
        for f in fejl[:20]:
            print("  fejl:", f)
    elif a[:1] == ["odds"]:
        if a[1:2] == ["historik"]:
            for fn_, n in odds_historik(range(1, int(a[2]) + 1)):
                print("skrevet %s (%d kampe)" % (fn_, n))
        else:
            print("skrevet %s (%d kampe)" % pinnacle(int(a[1])))
    elif a[:1] == ["rotowire"]:
        fn, ud = rotowire(int(a[1]))
        print("skrevet %s: %d af 20 klubber" % (fn, len(ud)))
        for k in sorted(ud):
            print("  %-4s %-5s %s OUT %d QUES %d" % (k, ud[k]["sikkerhed"], "bekraeftet" if ud[k]["bekraeftet"] else "forudsagt ", len(ud[k]["out"]), len(ud[k]["ques"])))
    else:
        print(__doc__)
