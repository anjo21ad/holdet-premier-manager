# -*- coding: utf-8 -*-
"""MODEL - holdet.dk Premier Manager, Efteraar 2026. Een fil, tre regler, een pointformel.

Fire kilder, hver med een rolle:
  holdet    pris, klub, position (autoritet)               holdet-*.json (den nyeste vaelges)
  understat starter, minutter, xG, xA, roller              us-m-*.json (i aar), us-p-*.json (2024-25)
  Betfair   holdstyrke (Match Odds + BTTS)                 bf-r<N>-*.json
  RotoWire  opstilling til naeste runde                    rw-r<N>.json
Kampprogram og runder fra holdets egen kampplan (holdet-pl-schedule-*.json).

Tre regler:
  1. RATE (Marcel): g90 = (sum v*xG*90 + K*prior_rolle) / (sum v*min + K) over STARTER i tre saesoner.
     v = 1 / 0,8 / 0,6 efter saeson (5/4/3), x 0,5 for minutter i en anden klub. Samme for a90 med xA.
  2. SPILLETID: naeste runde = RotoWire-status; resten = 1/2 status + 1/2 startandel i klubbens
     seneste 15 kampe med spilleren i klubben (under 5 kampe: kun status).
  3. HOLDSTYRKE: preseason-tier som prior (vaegt 4 runder), opdateret med Betfair-lambda fra hver gemt runde.
Een pointformel (ev_kamp = spillets regler). Dit eget skoen kun via manager_input.json (hoejst ~5 poster).
Kompleksitetsbudget: ingen ny parameter, kilde eller lag uden maalt forbedring i backtest paa >= 2 runder.
Begrundelser og evidens: docs/metode.md.

Brug:  python model.py <runde>          skriver board.json i input/
       model.byg(runde)                 as-of-koersel: kun data fra foer rundens deadline (til backtest)
"""
import collections, glob, io, json, math, os, re, statistics as S, sys, unicodedata
from datetime import date

from hent import SP
VAULT = os.path.dirname(os.path.abspath(__file__))

# ---- konstanter (dokumenteret i docs/metode.md) ----
K = 1000.0                                   # prior-minutter (~11 kampe; FPL Review: < 10 kampe forvraenger)
V_SAESON = {"2026": 1.0, "2025": 0.8, "2024": 0.6}  # Marcel 5/4/3
V_ANDEN_KLUB = 0.5                           # xG-persistens 0,6 -> 0,4 ved klubskifte (Evidently)
PS = {"XI": 0.92, "XI_QUES": 0.70, "QUES": 0.25, "OUT": 0.02, "ANDET": 0.14}
N_ANDEL, N_MIN_ANDEL = 15, 5                 # startandel over klubbens seneste 15 kampe; under 5: kun status
MARKED_PRIOR = 4                             # preseason-tier vejer som 4 markedsrunder
SHRINK_START = 3                             # minutter pr. start og 60-min-andel shrinkes med 3 starter mod rollens norm
HA, LAMSKALA, REDN_PR_XGA = 1.10, 0.5, 1.66  # hjemmebane; holdets angreb -> spillerens; redninger pr. xG imod (R1-R3)
GOALVAL = {"striker": 125, "midfield": 150, "defense": 175, "goalkeeper": 250}
SOT_BASE = {"defense": .25, "midfield": .35, "striker": .45, "goalkeeper": 0}
YEL = {"defense": .22, "midfield": .18, "striker": .12, "goalkeeper": .05}
TIER = {"MCI": (.60, .18, .35), "ARS": (.60, .18, .41), "LIV": (.55, .20, .28), "CHE": (.50, .21, .29),
        "MUN": (.47, .22, .27), "NEW": (.45, .22, .26), "TOT": (.43, .22, .25), "AVL": (.42, .23, .25),
        "BHA": (.40, .23, .25), "CRY": (.38, .24, .27), "NFO": (.38, .24, .25), "BOU": (.36, .24, .22),
        "FUL": (.35, .24, .20), "BRE": (.35, .24, .25), "EVE": (.33, .24, .25), "LEE": (.30, .25, .20),
        "SUN": (.30, .25, .20), "COV": (.22, .25, .16), "IPS": (.22, .25, .16), "HUL": (.18, .24, .12)}
ROLLE = {"GK": "GK", "DC": "CB", "DL": "FB", "DR": "FB", "DML": "FB", "DMR": "FB", "DMC": "CM", "MC": "CM",
         "ML": "AM", "MR": "AM", "AML": "AM", "AMR": "AM", "AMC": "AM", "FW": "FW", "FWL": "FW", "FWR": "FW"}
ROLLE_STD = {"goalkeeper": "GK", "defense": "CB", "midfield": "CM", "striker": "FW"}
H2F = {"ARS": "ARS", "ASV": "AVL", "BOU": "BOU", "BRE": "BRE", "BRI": "BHA", "CHE": "CHE", "COV": "COV",
       "CRP": "CRY", "EVE": "EVE", "FUL": "FUL", "HUL": "HUL", "IPS": "IPS", "LEE": "LEE", "LIV": "LIV",
       "MAU": "MUN", "MCI": "MCI", "NEW": "NEW", "NOT": "NFO", "SUN": "SUN", "TOT": "TOT"}
UK = {"Arsenal": "ARS", "Aston Villa": "AVL", "Bournemouth": "BOU", "Brentford": "BRE", "Brighton": "BHA",
      "Chelsea": "CHE", "Coventry": "COV", "Crystal Palace": "CRY", "Everton": "EVE", "Fulham": "FUL",
      "Hull": "HUL", "Ipswich": "IPS", "Leeds": "LEE", "Liverpool": "LIV", "Manchester City": "MCI",
      "Manchester United": "MUN", "Newcastle United": "NEW", "Nottingham Forest": "NFO",
      "Sunderland": "SUN", "Tottenham": "TOT"}
BF = dict(UK, **{"Newcastle": "NEW", "Man City": "MCI", "Man Utd": "MUN", "Man United": "MUN",
                 "Nottm Forest": "NFO", "Spurs": "TOT"})
def bf_fil(runde):
    """Rundens Betfair-skabelon ('bf-r<N>-{}.json'), eller None hvis runden ikke er gemt."""
    skab = "bf-r%d-{}.json" % runde
    if os.path.exists(os.path.join(SP, skab.format("MATCH_ODDS"))) and os.path.exists(os.path.join(SP, skab.format("BOTH_TEAMS_TO_SCORE"))):
        return skab
    return None
POS = {269: "defense", 270: "goalkeeper", 271: "midfield", 272: "striker"}

J = lambda f: json.load(io.open(os.path.join(SP, f), encoding="utf-8"))


def norm(s):
    s = (s or "").replace("&#039;", "'").translate(str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "ß": "ss", "ł": "l", "ı": "i"}))
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def toks(s):
    return [t for t in re.split(r"[\s\-'.]+", norm(s)) if t]


def match_score(a, b):
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0
    if sa == sb:
        return 100
    if a[-1] == b[-1] and a[0][:1] == b[0][:1]:
        return 85
    if sa <= sb or sb <= sa:
        return 80
    if len(sa & sb) >= 2:
        return 70
    return 65 if a[-1] == b[-1] and len(a[-1]) >= 4 else 0


def us_kort():
    """({navn(norm): us_id}, {us_id: holdet-position}) fra board.json. Koer 'python model.py' foerst."""
    fn = os.path.join(SP, "board.json")
    if not os.path.exists(fn):
        raise SystemExit("board.json mangler i %s - koer 'python model.py <runde>' foerst" % SP)
    b = json.load(io.open(fn, encoding="utf-8"))
    return {norm(r["name"]): str(r["us_id"]) for r in b if r["us_id"]}, {str(r["us_id"]): r["pos"] for r in b if r["us_id"]}


# ---------- spillets regler ----------
def pois(k, l):
    return math.exp(-l) * l ** k / math.factorial(k)


def resultat(lh, la, N=10):
    pw = sum(pois(i, lh) * pois(j, la) for i in range(N) for j in range(N) if i > j)
    pd = sum(pois(i, lh) * pois(i, la) for i in range(N))
    return pw, pd


def ev_kamp(r, lf, lm, pw, pd, hjemme, ps, att_norm):
    """Forventet prisdelta (tkr) i een kamp efter spillets pointregler (docs/pointsystem.md)."""
    pl, pos = 1 - pw - pd, r["pos"]
    sot = r["g90"] * 1.2 + SOT_BASE[pos]
    sk = 1.0 + LAMSKALA * (lf / att_norm - 1.0)
    e = (r["g90"] * GOALVAL[pos] + r["a90"] * 60 + sot * 10 + r["g90"] * 9) * ps * r["bt"] * sk
    e += (pw * 25 + pd * 5 - pl * 8) * ps
    e += ((0 if hjemme else pw * 10) - (pl * 5 if hjemme else 0)) * ps
    e += (lf * 10 - lm * 8) * ps * r["bt"]
    e += 12 * ps - 5 - YEL[pos] * 20 * ps
    if pos == "defense":
        e += math.exp(-lm) * 50 * ps * r["f60"]
    if pos == "goalkeeper":
        e += math.exp(-lm) * 75 * ps * r["f60"] + REDN_PR_XGA * lm * 5 * ps
    return e


def rate(sum_x, n, prior, k=K):
    """Marcel-reglen: vaegtet sum af xG (eller xA) over starter + k minutter af rollens prior."""
    return (sum_x * 90 + k * prior) / (n + k)


def evaluer(r, ctx):
    """ev_neste, ev_rest, ev_tot for een board-raekke. Det ENESTE sted EV beregnes (ogsaa i handel.py)."""
    kl, n6 = r["club"], ctx["naeste"][r["club"]]
    an = ctx["att_norm"][kl]
    r["ev_neste"] = ev_kamp(r, n6[0], n6[1], n6[2], n6[3], n6[4], r["pS_neste"], an) if n6 else 0.0
    pr = ctx["prog"][kl]
    r["ev_rest"] = S.mean(ev_kamp(r, lf, lm, pw, pd, hj, r["pStart"], an) for lf, lm, pw, pd, hj in pr) if pr else 0.0
    r["ev_tot"] = r["ev_neste"] + ctx["rest"] * r["ev_rest"]
    return r


# ---------- data ----------
def holdet():
    """Den holdet-fil med mest prisbevaegelse = den senest hentede. Et forældet filnavn kan ikke snige sig ind
    (en fil fra R2 med gamle klubber gjorde engang en falsk handel robust)."""
    ud = []
    for f in glob.glob(os.path.join(SP, "holdet-*.json")):
        d = json.load(io.open(f, encoding="utf-8"))
        if isinstance(d, dict) and "items" in d and "persons" in d.get("_embedded", {}):
            ud.append((sum(abs(it["price"] - it["startPrice"]) for it in d["items"]), os.path.basename(f), d))
    bev, fn, d = max(ud, key=lambda t: t[0])
    d["_fil"] = fn
    return d


def liga_2026():
    """Den understat-ligafil med flest spillede kampe (et forældet filnavn kan ikke snige sig ind)."""
    filer = [f for f in glob.glob(os.path.join(SP, "us-*.json")) if re.search(r"us-(0\d{3}|league-2026)\.json$", f)]
    return max((json.load(io.open(f, encoding="utf-8")) for f in filer), key=lambda d: sum(x["isResult"] for x in d["dates"]))


def kampe_foer(runde):
    """Kampe i runder < runde (runde = holdets k'te kamp, som facit_alle.py)."""
    import facit_alle as FA
    rd = FA.runder(liga_2026())
    return [(r, x, FA.kamp(x["id"])) for r in sorted(rd) if r < runde for x in rd[r]]


def betfair(runde, fx_par):
    """{klub: (lambda_for, lambda_imod, pW, pD, hjemme, modstander)} fra rundens Betfair-filer."""
    sti = bf_fil(runde)
    if not sti:
        return {}
    def laes(fil):
        ud = {}
        for et in J(fil).get("eventTypes", []):
            for e in et.get("eventNodes", []):
                navn = e.get("event", {}).get("eventName", "?").replace(" - ", " v ")
                for m in e.get("marketNodes", []):
                    rr = {}
                    for run in m.get("runners", []):
                        ex = run.get("exchange", {})
                        bk = (ex.get("availableToBack") or [{}])[0].get("price")
                        ly = (ex.get("availableToLay") or [{}])[0].get("price")
                        if bk and ly:
                            rr[run["description"]["runnerName"]] = (1 / bk + 1 / ly) / 2
                    if rr:
                        ud[navn] = rr
        return ud
    mo, bt = laes(sti.format("MATCH_ODDS")), laes(sti.format("BOTH_TEAMS_TO_SCORE"))
    ud = {}
    for k, rr in mo.items():
        if " v " not in k or k not in bt or "No" not in bt[k]:
            continue
        h, a = k.split(" v ")
        if (BF.get(h), BF.get(a)) not in fx_par:
            continue
        s, bs = sum(rr.values()), sum(bt[k].values())
        lh, la = loes(rr.get(h, 0) / s, bt[k]["No"] / bs)
        ud[BF[h]] = (lh, la, rr.get(h, 0) / s, rr.get("The Draw", 0) / s, True, BF[a])
        ud[BF[a]] = (la, lh, rr.get(a, 0) / s, rr.get("The Draw", 0) / s, False, BF[h])
    return ud


def loes(ph, p_ikke_begge):
    """Poisson-lambdaer der rammer markedets P(hjemmesejr) og P(ikke begge scorer)."""
    pH = lambda lh, la: sum(pois(i, lh) * pois(j, la) for i in range(11) for j in range(11) if i > j)
    btn = lambda lh, la: math.exp(-la) + math.exp(-lh) - math.exp(-lh - la)
    lo, hi = 0.6, 5.0
    for _ in range(50):
        tot = (lo + hi) / 2
        a, b = 0.05, tot - 0.05
        for _ in range(50):
            lh = (a + b) / 2
            a, b = (lh, b) if pH(lh, tot - lh) < ph else (a, lh)
        lo, hi = (tot, hi) if btn(lh, tot - lh) > p_ikke_begge else (lo, tot)
    return lh, tot - lh


def rotowire(runde):
    """{klub: {'xi','out','ques'}} for runden, eller {} hvis ingen opstillingsfil findes."""
    return J("rw-r%d.json" % runde) if os.path.exists(os.path.join(SP, "rw-r%d.json" % runde)) else {}


def kampplan():
    """({runde: [(hjemme, ude)]}, {runde: deadline UTC}) fra holdets egen kampplan. En kamp hoerer til den
    runde, hvis deadline (close) ligger foer kampstart - verificeret: 10 kampe i hver af de 20 runder."""
    d = J(os.path.basename(sorted(glob.glob(os.path.join(SP, "holdet-pl-schedule*.json")))[-1]))
    closes = [r["close"] for r in d["rounds"]]
    hold = {t["id"]: H2F.get(t["abbreviation"], t["abbreviation"]) for t in d["_embedded"]["teams"].values()}
    plan = collections.defaultdict(list)
    for eid in d["events"]:
        e = d["_embedded"]["events"][str(eid)]
        side = {p["type"]: hold[p["teamId"]] for p in e["participants"]}
        plan[sum(1 for c in closes if c <= e["start"])].append((side["home"], side["away"]))
    return dict(plan), {i + 1: c for i, c in enumerate(closes)}


def i_liste(navn, liste):
    t = toks(navn)
    for x in liste:
        e = toks(x)
        if e and (e[-1] == t[-1] or (len(e[-1]) >= 4 and t[-1].endswith(e[-1])) or set(e) <= set(t)):
            return True
    return False


# ---------- modellen ----------
def byg(runde, rundeinfo=True):
    """rundeinfo=False: uden RotoWire og Betfair for selve runden (fair sammenligning med generiske prognoser)."""
    H = holdet()
    pers, teams = H["_embedded"]["persons"], H["_embedded"]["teams"]
    plan, _ = kampplan()
    par = lambda r: set(plan.get(r, []))
    liga, liga25 = liga_2026(), J("us-league-2025.json")

    # 1. understat: aarets starter fra kamprosters (friske), 2024-25 fra spillerfiler (statiske)
    kampe = kampe_foer(runde)
    rk = collections.defaultdict(list)          # us_id -> [(dato, saeson, klub, pos, min, xg, xa)]
    skud = collections.defaultdict(list)        # us_id -> [(xg, situation)] i aar
    klubkampe = collections.defaultdict(list)   # klub -> [(dato, kamp_id)] 2025 + 2026
    for r, x, md in kampe:
        for side in ("h", "a"):
            kl = UK[x[side]["title"]]
            klubkampe[kl].append((x["datetime"], x["id"]))
            for p in md["rosters"][side].values():
                if int(p["time"]) > 0:
                    rk[p["player_id"]].append((x["datetime"], "2026", kl, p["position"], int(p["time"]), float(p["xG"]), float(p["xA"]), x["id"]))
        for s in md["shots"]["h"] + md["shots"]["a"]:
            skud[s["player_id"]].append((float(s["xG"]), s["situation"]))
    for x in liga25["dates"]:
        if x["isResult"]:
            for side in ("h", "a"):
                if x[side]["title"] in UK:
                    klubkampe[UK[x[side]["title"]]].append((x["datetime"], x["id"]))

    # 2. holdet -> understat (2026-ligaen pr. klub; 2025-ligaen for spillere uden minutter i aar)
    idx = collections.defaultdict(list)
    for L in (liga, liga25):
        for p in L["players"]:
            kl = UK.get(p["team_title"].split(",")[-1].strip())
            if kl:
                idx[kl].append((p["id"], toks(p["player_name"])))
    aktive = [it for it in H["items"] if not it.get("isOut")]
    navn = lambda it: ((pers[str(it["personId"])].get("firstName") or "") + " " + (pers[str(it["personId"])].get("lastName") or "")).strip()
    klub = lambda it: H2F[teams[str(it["teamId"])]["abbreviation"]]
    tildel = collections.defaultdict(list)
    for it in aktive:
        sc = sorted(((match_score(toks(navn(it)), t), pid) for pid, t in idx[klub(it)]), reverse=True)
        if sc and sc[0][0] >= 65 and not (len(sc) > 1 and sc[1][0] == sc[0][0] and sc[1][1] != sc[0][1]):
            tildel[sc[0][1]].append((sc[0][0], it["personId"]))
    us_af = {lst[0][1]: pid for pid, lst in ((p, sorted(l, reverse=True)) for p, l in tildel.items())
             if not (len(lst) > 1 and lst[0][0] == lst[1][0])}

    # 3. raa rater pr. spiller (starter, vaegtet) -> rolle -> rollepriorer fra data
    import hent as U
    def raekker(pid, kl):
        ud = list(rk.get(pid, []))
        fn = os.path.join(SP, "us-p-%s.json" % pid)
        if not os.path.exists(fn):
            try:
                U.spiller(pid, max_timer=1e9)       # ny spiller: hent karrieren een gang
            except Exception as e:
                print("  !! understat-spillerfil %s kunne ikke hentes: %r" % (pid, e))
        if os.path.exists(fn):
            d = json.load(io.open(fn, encoding="utf-8"))
            hold = U.hold_pr_saeson(d)
            for m in d["matches"]:
                if m["season"] in ("2025", "2024"):
                    egen = U.egen_og_modstander(m, hold)[0]
                    ud.append((m["date"], m["season"], UK.get(egen, egen), m["position"], int(m["time"]), float(m["xG"]), float(m["xA"]), m["id"]))
        return ud
    spillere = {}
    for it in aktive:
        pid, kl = us_af.get(it["personId"]), klub(it)
        rows = raekker(pid, kl) if pid else []
        st = [x for x in rows if x[3] != "Sub"]
        v = lambda x: V_SAESON[x[1]] * (1.0 if x[2] == kl else V_ANDEN_KLUB)
        n = sum(v(x) * x[4] for x in st)
        roller = collections.Counter()
        for x in st:
            roller[ROLLE.get(x[3], "CM")] += v(x) * x[4]
        spillere[it["personId"]] = {"it": it, "pid": pid, "kl": kl, "rows": rows, "st": st, "n": n,
                                    "xg": sum(v(x) * x[5] for x in st), "xa": sum(v(x) * x[6] for x in st),
                                    "rolle": roller.most_common(1)[0][0] if roller else ROLLE_STD[POS[it["positionId"]]]}
    prior = {}
    for rolle in set(ROLLE.values()):
        et = [s for s in spillere.values() if s["rolle"] == rolle and s["n"] >= 1800]
        prior[rolle] = (S.median(s["xg"] / s["n"] * 90 for s in et), S.median(s["xa"] / s["n"] * 90 for s in et)) if len(et) >= 8 else (0.0, 0.0)
    alle_st = [x for s in spillere.values() for x in s["st"] if x[1] == "2026"]
    norm_bt = {r: S.mean(min(x[4], 90) / 90 for x in alle_st if ROLLE.get(x[3]) == r) for r in set(ROLLE.values())}
    norm_60 = {r: S.mean(1.0 if x[4] >= 60 else 0.0 for x in alle_st if ROLLE.get(x[3]) == r) for r in set(ROLLE.values())}

    # 4. holdstyrke: tier-prior opdateret med markedet (alle gemte runder <= runde)
    lam_l = S.mean(-math.log(v[2]) for v in TIER.values())
    tg = {c: 0.9 + 2.0 * v[0] for c, v in TIER.items()}
    a0 = {c: tg[c] / S.mean(tg.values()) for c in TIER}
    d0 = {c: -math.log(TIER[c][2]) / lam_l for c in TIER}
    obs_a, obs_d = collections.defaultdict(list), collections.defaultdict(list)
    marked = {}
    for r in range(1, runde + 1):
        if r == runde and not rundeinfo:
            continue
        bf = betfair(r, par(r))
        if r == runde:
            marked = bf
        for c, (lf, lm, _, _, hj, mod) in bf.items():
            h = HA if hj else 1 / HA
            obs_a[c].append(lf / (lam_l * d0[mod] * h))
            obs_d[c].append(lm / (lam_l * a0[mod] / h))
    att = {c: (MARKED_PRIOR * a0[c] + sum(obs_a[c])) / (MARKED_PRIOR + len(obs_a[c])) for c in TIER}
    dfn = {c: (MARKED_PRIOR * d0[c] + sum(obs_d[c])) / (MARKED_PRIOR + len(obs_d[c])) for c in TIER}
    lam = lambda a, d, hj: lam_l * att[a] * dfn[d] * (HA if hj else 1 / HA)
    prog = collections.defaultdict(list)
    for h, a in (k for r in range(runde + 1, 21) for k in plan.get(r, [])):
            for c, hj, m in ((h, True, a), (a, False, h)):
                lf, lm = lam(c, m, hj), lam(m, c, not hj)
                prog[c].append((lf, lm) + resultat(lf, lm) + (hj,))
    naeste = {c: marked[c] if c in marked else None for c in TIER}
    for h, a in plan.get(runde, []):
            for c, hj, m in ((h, True, a), (a, False, h)):
                if naeste[c] is None:
                    lf, lm = lam(c, m, hj), lam(m, c, not hj)
                    naeste[c] = (lf, lm) + resultat(lf, lm) + (hj, m)

    # 5. spilletid, EV og forklaring pr. spiller
    rw = rotowire(runde) if rundeinfo else {}
    ctx = {"naeste": naeste, "prog": prog, "att_norm": {c: att[c] * lam_l for c in TIER}, "rest": 20 - runde}
    fn_mi = os.path.join(VAULT, "manager_input.json")
    mi = json.load(io.open(fn_mi, encoding="utf-8")) if os.path.exists(fn_mi) else {}
    mi = {k: v for k, v in mi.items() if not k.startswith("_")}
    board = []
    for s in spillere.values():
        it, kl, pos = s["it"], s["kl"], POS[s["it"]["positionId"]]
        nm = navn(it)
        man = mi.get(nm, {})
        if man and man.get("udloeber", "9999") < date.today().isoformat():
            print("  !! manager_input for %s udloeb %s og ignoreres" % (nm, man["udloeber"]))
            man = {}
        rolle = man.get("rolle", s["rolle"])
        pg, pa = prior.get(rolle, (0.0, 0.0))
        g90, a90 = rate(s["xg"], s["n"], pg), rate(s["xa"], s["n"], pa)
        # startandel: klubbens seneste kampe siden spillerens foerste optraeden for klubben
        egne = {x[7]: x for x in s["rows"] if x[2] == kl}
        foerste = min((x[0] for x in egne.values()), default=None)
        km = sorted(k for k in klubkampe[kl] if foerste and k[0] >= foerste)[-N_ANDEL:]
        andel = sum(1 for _, mid in km if mid in egne and egne[mid][3] != "Sub") / len(km) if km else None
        if kl in rw:
            l = rw[kl]
            ixi, iq, io_ = i_liste(nm, l.get("xi", [])), i_liste(nm, l.get("ques", [])), i_liste(nm, l.get("out", []))
            status = PS["OUT"] if io_ else PS["XI_QUES"] if ixi and iq else PS["XI"] if ixi else PS["QUES"] if iq else PS["ANDET"]
        else:   # ingen RotoWire for klubben (kun i backtest; live kraever kvalitet.py alle 20): startandel shrunket mod 0,14
            n_st = sum(1 for _, mid in km if mid in egne and egne[mid][3] != "Sub")
            status = (n_st + 2 * PS["ANDET"]) / (len(km) + 2)
        ps_n = status
        pstart = 0.5 * status + 0.5 * andel if (andel is not None and len(km) >= N_MIN_ANDEL) else status
        if "pStart" in man:
            pstart = man["pStart"]
        egne_st = [x for x in s["st"] if x[2] == kl]
        r = {"name": nm, "club": kl, "pos": pos, "price": it["price"] / 1e6, "startPrice": it["startPrice"] / 1e6,
             "us_id": s["pid"], "rolle": rolle, "g90": g90, "a90": a90, "pS_neste": ps_n, "pStart": pstart,
             "bt": (sum(min(x[4], 90) for x in egne_st) / 90 + SHRINK_START * norm_bt.get(rolle, 0.88)) / (len(egne_st) + SHRINK_START),
             "f60": (sum(1 for x in egne_st if x[4] >= 60) + SHRINK_START * norm_60.get(rolle, 0.9)) / (len(egne_st) + SHRINK_START)}
        evaluer(r, ctx)
        # forklaring: hvad tallet er maalt under
        saes = collections.defaultdict(lambda: [0, 0.0, 0.0])
        for x in s["st"]:
            t = saes["%s %s" % (x[1], x[2])]
            t[0] += x[4]; t[1] += x[5]; t[2] += x[6]
        aar = [x for x in s["st"] if x[1] == "2026"]
        sk = skud.get(s["pid"], [])
        xg_aar = sum(x for x, _ in sk)
        flag = []
        if sum(x[4] for x in aar) < 450:
            flag.append("tynd: %d startmin i aar" % sum(x[4] for x in aar))
        if any(x[2] != kl for x in s["st"]):
            flag.append("klubskifte: minutter fra anden klub vaegtet x%.1f" % V_ANDEN_KLUB)
        if xg_aar > 0.3 and sum(x for x, sit in sk if sit == "Penalty") / xg_aar > 0.25:
            flag.append("straffe: %.0f %% af aarets xG" % (100 * sum(x for x, sit in sk if sit == "Penalty") / xg_aar))
        if xg_aar > 0.3 and max(x for x, _ in sk) / xg_aar > 0.40:
            flag.append("koncentration: %.0f %% af aarets xG fra eet skud" % (100 * max(x for x, _ in sk) / xg_aar))
        if man:
            flag.append("MANAGER: %s" % man.get("grund", ""))
        r["forklaring"] = {"vaegtede_min": round(s["n"]), "vaegt_paa_prior": round(K / (s["n"] + K), 2),
                           "sum_xg": s["xg"], "sum_xa": s["xa"], "n": s["n"],
                           "prior": [pg, pa], "rolle_maalt": s["rolle"],
                           "saesoner": {k: {"startmin": v[0], "xg90": round(v[1] / v[0] * 90, 2) if v[0] else None,
                                            "xa90": round(v[2] / v[0] * 90, 2) if v[0] else None} for k, v in sorted(saes.items())},
                           "status": round(status, 2), "startandel": None if andel is None else round(andel, 2),
                           "klubkampe": len(km), "flag": flag}
        board.append(r)
    return board, {"runde": runde, "prior": prior, "att": att, "def": dfn, "marked_runder": [r for r in range(1, runde + 1) if bf_fil(r)],
                   "matchet": sum(1 for s in spillere.values() if s["pid"]), "aktive": len(spillere), "ctx": ctx,
                   "holdet_fil": H["_fil"]}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    runde = int(sys.argv[1])
    board, meta = byg(runde)
    json.dump(board, io.open(os.path.join(SP, "board.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("R%d: %d spillere, %d matchet mod understat, markedsrunder %s" % (runde, meta["aktive"], meta["matchet"], meta["marked_runder"]))
    print("rollepriorer (g90, a90):", {k: (round(v[0], 3), round(v[1], 3)) for k, v in sorted(meta["prior"].items())})
