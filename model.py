# -*- coding: utf-8 -*-
"""MODEL - holdet.dk Premier Manager, Efteraar 2026. Een fil, tre regler, een pointformel.

Fire kilder, hver med een rolle:
  holdet    pris, klub, position (autoritet) og facit       holdet-*.json (den nyeste vaelges)
  FotMob    starter, minutter, xG, xA, positioner, skud     fm-m-*.json (PL 2024-2026 + fire andre topligaer 2024-2025)
  odds      holdstyrke (1X2 + over/under 2,5)               od-r<N>.json (Pinnacle; spillede runder fra football-data.co.uk)
  RotoWire  opstilling til naeste runde                    rw-r<N>.json
Kampprogram og runder fra holdets egen kampplan (holdet-pl-schedule-*.json).

Tre regler:
  1. RATE (Marcel): g90 = (sum v*npxG*90 + K*prior_rolle) / (sum v*min + K) over STARTER i tre saesoner.
     v = 1 / 0,8 / 0,6 efter saeson (5/4/3), x 0,5 for minutter i en anden klub. Samme for a90 med xA.
     Straffe er et separat led: + ligaens straffe-xG pr. holdkamp x spillerens andel af
     klubbens straffe-xG (2025 + i aar).
  2. SPILLETID: naeste runde = RotoWire-status; resten = 1/2 status + 1/2 startandel i klubbens
     seneste 15 kampe med spilleren i klubben, shrunket mod status med 3 kampe.
  3. HOLDSTYRKE: preseason-tier som prior (vaegt 4 runder), opdateret med markedets lambda fra hver gemt runde.
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
N_ANDEL = 15                                 # startandel over klubbens seneste 15 kampe (shrinkes mod status med SHRINK_START)
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
def od_fil(runde):
    """Rundens oddsfil ('od-r<N>.json'), eller None hvis runden ikke er gemt."""
    fn = "od-r%d.json" % runde
    return fn if os.path.exists(os.path.join(SP, fn)) else None
# FotMob positionId -> positionskode (GK, DC, DL/DR, DMC, MC, AML/AMR/AMC, FW), som ROLLE oversaetter til en rolle. Koden er
# linje x 10 + side; tabellen er kontrolleret paa 2.450 starter i R1-R8 2026. Koder uden for tabellen gives efter linjen.
FM_POS = {11: "GK", 32: "DR", 38: "DL", 51: "DR", 59: "DL", 62: "DMR", 68: "DML", 71: "DMR", 79: "DML", 72: "MR", 78: "ML",
          82: "AMR", 83: "AMR", 87: "AML", 88: "AML", 103: "AMR", 107: "AML"}


def fm_pos(pid):
    if pid in FM_POS:
        return FM_POS[pid]
    linje = (pid or 0) // 10
    return {3: "DC", 5: "DMC", 6: "DMC", 7: "MC", 8: "AMC"}.get(linje, "FW" if linje >= 10 else "MC")
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


FM_LIGAER = ("PL", "L1", "BL", "SA", "LL")
_HIST = {}


def fm_kampe(liga, saeson):
    """[(kampliste-raekke, kompakt kamp)] for ligaens faerdige kampe i cachen (hent.py fotmob)."""
    fn = os.path.join(SP, "fm-liga-%s-%s.json" % (liga, saeson))
    if not os.path.exists(fn):
        return []
    ud = []
    for m in J(os.path.basename(fn)):
        f = os.path.join(SP, "fm-m-%s.json" % m["id"])
        if m["faerdig"] and os.path.exists(f):
            ud.append((m, json.load(io.open(f, encoding="utf-8"))))
    return ud


def klubkode(navn):
    from hent import KODE
    return KODE.get(navn, navn)


def kampe_foer(runde):
    """PL-kampe i aar i runder < runde: [(runde, kamp)]. En kamp hoerer til den runde, hvis deadline ligger foer kampstart."""
    _, dl = kampplan()
    closes = [dl[r] for r in sorted(dl)]
    ud = []
    for m, k in fm_kampe("PL", "2026"):
        r = sum(1 for c in closes if c[:16] <= m["tid"][:16])
        if r < runde:
            ud.append((r, k))
    return sorted(ud, key=lambda t: t[1]["tid"])


def straffe(k):
    """{(spiller, kamp): straffe-xG} for een kamp."""
    ud = collections.defaultdict(float)
    for s in k["skud"]:
        if s["sit"] == "Penalty" and not s["selvmaal"]:
            ud[(s["id"], k["id"])] += s["xg"]
    return ud


def historik():
    """Raekker for 2024 og 2025 (alle ligaer) pr. FotMob-spiller: (dato, saeson, klub, position, min, npxG, xA, kamp).
    Statisk, saa den laeses een gang pr. koersel."""
    if "rk" not in _HIST:
        rk = collections.defaultdict(list)
        for saeson in ("2024", "2025"):
            for liga in FM_LIGAER:
                for m, k in fm_kampe(liga, saeson):
                    pen = straffe(k)
                    for p in k["spillere"]:
                        if p["min"] > 0:
                            rk[p["id"]].append((k["tid"], saeson, klubkode(k[p["hold"]]), fm_pos(p["pos"]) if p["start"] else "Sub",
                                                p["min"], p["xg"] - pen.get((p["id"], k["id"]), 0.0), p["xa"], k["id"]))
        _HIST["rk"] = rk
    return _HIST["rk"]


def marked(runde, fx_par):
    """{klub: (lambda_for, lambda_imod, pW, pD, hjemme, modstander)} fra rundens oddsfil."""
    fn = od_fil(runde)
    if not fn:
        return {}
    ud = {}
    for k in J(fn)["kampe"]:
        h, a = k["h"], k["a"]
        if (h, a) not in fx_par:
            continue
        lh, la = loes(k["pH"], k["pOver25"])
        ud[h] = (lh, la, k["pH"], k["pD"], True, a)
        ud[a] = (la, lh, k["pA"], k["pD"], False, h)
    return ud


def loes(ph, p_over):
    """Poisson-lambdaer der rammer markedets P(hjemmesejr) og P(over 2,5 maal). Totalen afhaenger kun af
    summen af lambdaerne, saa den findes foerst; P(hjemmesejr) fordeler den."""
    over = lambda T: 1 - math.exp(-T) * (1 + T + T * T / 2)
    lo, hi = 0.3, 8.0
    for _ in range(60):
        T = (lo + hi) / 2
        lo, hi = (T, hi) if over(T) < p_over else (lo, T)
    pH = lambda lh, la: sum(pois(i, lh) * pois(j, la) for i in range(11) for j in range(11) if i > j)
    a, b = 0.01, T - 0.01
    for _ in range(50):
        lh = (a + b) / 2
        a, b = (lh, b) if pH(lh, T - lh) < ph else (a, lh)
    return lh, T - lh


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
    """rundeinfo=False: uden RotoWire og odds for selve runden (fair sammenligning med generiske prognoser)."""
    H = holdet()
    pers, teams = H["_embedded"]["persons"], H["_embedded"]["teams"]
    plan, _ = kampplan()
    par = lambda r: set(plan.get(r, []))

    # 1. FotMob: aarets kampe foer runden (PL), 2024-2025 fra alle fem ligaer (historik())
    kampe = kampe_foer(runde)
    rk = collections.defaultdict(list)          # fm_id -> [(dato, saeson, klub, pos, min, npxg, xa, kamp)]
    skud = collections.defaultdict(list)        # fm_id -> [(xg, situation)] i aar
    klubkampe = collections.defaultdict(list)   # klub -> [(dato, kamp_id)] 2025 + 2026
    # straffe som separat led: rosternes xG er med straffe, saa straffe-xG traekkes fra pr. (spiller, kamp)
    PEN_KLUB = collections.defaultdict(float); PEN_SP = collections.defaultdict(float)
    holdkampe = 0
    for r, k in kampe:
        pen = straffe(k)
        for (pid, _), xg in pen.items():
            kl = klubkode(k[next(p["hold"] for p in k["spillere"] if p["id"] == pid)]) if any(p["id"] == pid for p in k["spillere"]) else None
            if kl:
                PEN_KLUB[kl] += xg; PEN_SP[(pid, kl)] += xg
        for side in ("h", "a"):
            holdkampe += 1
            klubkampe[klubkode(k[side])].append((k["tid"], k["id"]))
        for p in k["spillere"]:
            if p["min"] > 0:
                rk[p["id"]].append((k["tid"], "2026", klubkode(k[p["hold"]]), fm_pos(p["pos"]) if p["start"] else "Sub", p["min"],
                                    p["xg"] - pen.get((p["id"], k["id"]), 0.0), p["xa"], k["id"]))
        for s in k["skud"]:
            if not s["selvmaal"]:
                skud[s["id"]].append((s["xg"], s["sit"]))
    # 2025: klubbernes og spillernes straffe-xG og klubkampe fra sidste saesons PL-kampe
    PEN_KLUB25 = collections.defaultdict(float); PEN_SP25 = collections.defaultdict(float)
    kampe25 = fm_kampe("PL", "2025")
    for m, k in kampe25:
        hold_af = {p["id"]: klubkode(k[p["hold"]]) for p in k["spillere"]}
        for (pid, _), xg in straffe(k).items():
            if pid in hold_af:
                PEN_KLUB25[hold_af[pid]] += xg; PEN_SP25[(pid, hold_af[pid])] += xg
        for side in ("h", "a"):
            klubkampe[klubkode(k[side])].append((k["tid"], k["id"]))
    PEN_PR_HOLDKAMP = (sum(PEN_KLUB25.values()) + sum(PEN_KLUB.values())) / (2 * len(kampe25) + holdkampe)

    # 2. holdet -> FotMob: spillere med minutter for klubben i aar eller i PL sidste saeson; ellers et entydigt navn
    hist = historik()
    idx = collections.defaultdict(dict)
    for _, k in kampe + [(None, k) for _, k in kampe25]:
        for p in k["spillere"]:
            idx[klubkode(k[p["hold"]])][p["id"]] = toks(p["navn"] or "")
    aktive = [it for it in H["items"] if not it.get("isOut")]
    navn = lambda it: ((pers[str(it["personId"])].get("firstName") or "") + " " + (pers[str(it["personId"])].get("lastName") or "")).strip()
    klub = lambda it: H2F[teams[str(it["teamId"])]["abbreviation"]]
    tildel = collections.defaultdict(list)
    for it in aktive:
        sc = sorted(((match_score(toks(navn(it)), t), pid) for pid, t in idx[klub(it)].items()), reverse=True)
        if sc and sc[0][0] >= 65 and not (len(sc) > 1 and sc[1][0] == sc[0][0] and sc[1][1] != sc[0][1]):
            tildel[sc[0][1]].append((sc[0][0], it["personId"]))
    fm_af = {lst[0][1]: pid for pid, lst in ((p, sorted(l, reverse=True)) for p, l in tildel.items())
             if not (len(lst) > 1 and lst[0][0] == lst[1][0])}

    # 3. raa rater pr. spiller (starter, vaegtet) -> rolle -> rollepriorer fra data
    def raekker(pid, kl):
        return list(rk.get(pid, [])) + list(hist.get(pid, []))
    spillere = {}
    for it in aktive:
        pid, kl = fm_af.get(it["personId"]), klub(it)
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
    naeste_mk = {}
    for r in range(1, runde + 1):
        if r == runde and not rundeinfo:
            continue
        mk = marked(r, par(r))
        if r == runde:
            naeste_mk = mk
        for c, (lf, lm, _, _, hj, mod) in mk.items():
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
    naeste = {c: naeste_mk[c] if c in naeste_mk else None for c in TIER}
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
        # npxG-rate + ligaens straffe-xG pr. holdkamp x spillerens andel af klubbens straffe
        # (2025 + i aar, kun nuvaerende klub). Backtest R4-R8: MSE 3.148 -> 3.140, beta 0,83 -> 0,85, top 5 % 84 -> 89 %.
        klub_pen = PEN_KLUB25.get(kl, 0.0) + PEN_KLUB.get(kl, 0.0)
        andel_pen = min(1.0, (PEN_SP25.get((s["pid"], kl), 0.0) + PEN_SP.get((s["pid"], kl), 0.0)) / klub_pen) if klub_pen > 0 else 0.0
        pen90 = PEN_PR_HOLDKAMP * andel_pen
        g90, a90 = rate(s["xg"], s["n"], pg) + pen90, rate(s["xa"], s["n"], pa)
        # startandel: klubbens seneste kampe siden spillerens foerste optraeden for klubben
        egne = {x[7]: x for x in s["rows"] if x[2] == kl}
        foerste = min((x[0] for x in egne.values()), default=None)
        km = sorted(k for k in klubkampe[kl] if foerste and k[0] >= foerste)[-N_ANDEL:]
        n_st = sum(1 for _, mid in km if mid in egne and egne[mid][3] != "Sub")
        andel = n_st / len(km) if km else None
        if kl in rw:
            l = rw[kl]
            ixi, iq, io_ = i_liste(nm, l.get("xi", [])), i_liste(nm, l.get("ques", [])), i_liste(nm, l.get("out", []))
            status = PS["OUT"] if io_ else PS["XI_QUES"] if ixi and iq else PS["XI"] if ixi else PS["QUES"] if iq else PS["ANDET"]
        else:   # ingen RotoWire for klubben (kun i backtest; live kraever kvalitet.py alle 20): startandel shrunket mod 0,14
            status = (n_st + 2 * PS["ANDET"]) / (len(km) + 2)
        ps_n = status
        # startandelen shrinkes mod status med 3 kampe i stedet for et hop ved 5 klubkampe.
        # Brier for starter efter naeste runde: R4 0,1989 -> 0,1964, R5 0,1855 -> 0,1804, R6 0,1868 -> 0,1862.
        pstart = 0.5 * status + 0.5 * (n_st + SHRINK_START * status) / (len(km) + SHRINK_START)
        if "pStart" in man:
            pstart = man["pStart"]
        egne_st = [x for x in s["st"] if x[2] == kl]
        r = {"name": nm, "club": kl, "pos": pos, "price": it["price"] / 1e6, "startPrice": it["startPrice"] / 1e6,
             "fm_id": s["pid"], "person_id": s["it"]["personId"], "rolle": rolle, "g90": g90, "a90": a90, "pS_neste": ps_n, "pStart": pstart,
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
                           "prior": [pg, pa], "rolle_maalt": s["rolle"], "pen90": pen90, "straffeandel": round(andel_pen, 2),
                           "saesoner": {k: {"startmin": v[0], "xg90": round(v[1] / v[0] * 90, 2) if v[0] else None,
                                            "xa90": round(v[2] / v[0] * 90, 2) if v[0] else None} for k, v in sorted(saes.items())},
                           "status": round(status, 2), "startandel": None if andel is None else round(andel, 2),
                           "klubkampe": len(km), "flag": flag}
        board.append(r)
    return board, {"runde": runde, "prior": prior, "att": att, "def": dfn, "marked_runder": [r for r in range(1, runde + 1) if od_fil(r)],
                   "matchet": sum(1 for s in spillere.values() if s["pid"]), "aktive": len(spillere), "ctx": ctx,
                   "holdet_fil": H["_fil"]}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    runde = int(sys.argv[1])
    board, meta = byg(runde)
    json.dump(board, io.open(os.path.join(SP, "board.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("R%d: %d spillere, %d matchet mod FotMob, markedsrunder %s" % (runde, meta["aktive"], meta["matchet"], meta["marked_runder"]))
    print("rollepriorer (g90, a90):", {k: (round(v[0], 3), round(v[1], 3)) for k, v in sorted(meta["prior"].items())})
