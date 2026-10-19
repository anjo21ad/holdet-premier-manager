# -*- coding: utf-8 -*-
"""FACIT FOR ALLE SPILLERE - realiserede point fra understat, uden browser og uden holdet-API.

Hvorfor: kalibrering kraever realiserede point for HELE puljen, ikke kun dit eget hold. holdet-API'et
giver kun den aktuelle pris (ikke point pr. kamp). understat har alt pointmotoren skal bruge:
rosters (minutter, maal, assists, kort, selvmaal, ind-/udskiftning) og
skud (minut, resultat, situation) -> skud paa maal og redninger.

Regler (regelsaet 119, docs/pointsystem.md): +7 paa banen, sejr 25 / uafgjort 5 /
nederlag -8, udesejr +10, hjemmenederlag -5, holdmaal +10 og modstandermaal -8 mens spilleren er
paa banen, maal 125/150/175/250 efter holdet-position, assist 60, skud paa maal (ikke maal, ikke
straffe) 10, redning 5, gult -20, roedt -50, selvmaal -50, scoring til sejr 40 / til uafgjort 20,
clean sheet 50 (forsvar) / 75 (keeper) ved >= 60 minutter og 0 maal imod.

KENDTE TILNAERMELSER (maales af valider() mod holdets egne point, se nedenfor):
  * spillere uden minutter faar -5 (baenk); holdet giver 0, hvis spilleren ikke var i truppen
  * indskiftningsminut = 90 - spilletid; overtid er ikke modelleret
  * skud paa maal efter understats 'SavedShot'; holdets datapartner kan taelle anderledes

Validering (valgfri): har du selv noteret holdets point pr. spiller og runde fra appen, saa gem dem i
point-historik.json som {"<id>": {"navn": "<spiller>", "pos": "midtbane", "r": [<R1>, <R2>, ...]}} (tkr).
Saa sammenligner valider() facit med holdets egne tal for de runder, filen daekker.

Brug:  python facit_alle.py            henter manglende kampe, skriver facit/understat.json
"""
import collections, io, json, os, statistics as S, sys, unicodedata
import hent as U

VAULT = os.path.dirname(os.path.abspath(__file__))
SP = U.SP
GOAL = {"defense": 175, "midfield": 150, "striker": 125, "goalkeeper": 250}
POS_DK = {"forsvar": "defense", "midtbane": "midfield", "angreb": "striker", "maalmand": "goalkeeper", "målmand": "goalkeeper"}


def norm(x):
    return "".join(c for c in unicodedata.normalize("NFD", x or "") if unicodedata.category(c) != "Mn").lower().strip()


def kamp(mid):
    fn = os.path.join(SP, "us-m-%s.json" % mid)
    if os.path.exists(fn) and os.path.getsize(fn) > 1000:
        return json.load(io.open(fn, encoding="utf-8"))
    d = U.hent_json("getMatchData/%s" % mid, ("rosters", "shots"))
    json.dump(d, io.open(fn, "w", encoding="utf-8"), ensure_ascii=False)
    return d


def maal_haendelser(dato, md):
    """[(minut, side, scorer_id)] i tidsorden; selvmaal faar scorer None. Afstemmes mod slutresultatet."""
    ev = []
    for s in md["shots"]["h"] + md["shots"]["a"]:
        if s["result"] == "Goal":
            ev.append([int(s["minute"]), s["h_a"], s["player_id"]])
        elif s["result"] == "OwnGoal":
            ev.append([int(s["minute"]), s["h_a"], None])
    ft = {"h": int(dato["goals"]["h"]), "a": int(dato["goals"]["a"])}
    tael = collections.Counter(e[1] for e in ev)
    if tael != collections.Counter({k: v for k, v in ft.items() if v}):
        for e in ev:                      # selvmaal kan staa paa skytten
            if e[2] is None:
                e[1] = "a" if e[1] == "h" else "h"
        tael = collections.Counter(e[1] for e in ev)
    ok = tael == collections.Counter({k: v for k, v in ft.items() if v})
    return sorted(ev, key=lambda e: e[0]), ft, ok


def afgoerende(ev, ft):
    """(sejrsmaal, udligningsmaal) som i r3_facit: sejr = maalet der bragte vinderen foran for sidste gang."""
    sejr = uaf = None
    if ft["h"] != ft["a"]:
        v = "h" if ft["h"] > ft["a"] else "a"
        n = {"h": 0, "a": 0}
        for e in ev:
            n[e[1]] += 1
            foran = n[v] > n["a" if v == "h" else "h"]
            if foran and sejr is None:
                sejr = e
            if not foran:
                sejr = None
    elif ft["h"] > 0:
        uaf = ev[-1]
    return sejr, uaf


def point_kamp(dato, md, pos_af):
    """{us_player_id: {navn, side, min, point, komp}} for alle spillere med minutter."""
    ev, ft, ok = maal_haendelser(dato, md)
    sejr, uaf = afgoerende(ev, ft)
    skud = md["shots"]["h"] + md["shots"]["a"]
    ud = {}
    for side in ("h", "a"):
        mod = "a" if side == "h" else "h"
        egne, imod = ft[side], ft[mod]
        rost = [p for p in md["rosters"][side].values() if int(p["time"]) > 0]
        for p in rost:
            t = int(p["time"])
            if p["position"] == "Sub":
                fra, til = 90 - t, 200
            else:
                fra, til = 0, (t if p["roster_in"] != "0" or int(p["red_card"]) else 200)
            pos = pos_af(p["player_id"], p["player"])
            d = {"paa banen": 7}
            d["resultat"] = 25 if egne > imod else (5 if egne == imod else -8)
            if egne > imod and side == "a":
                d["udesejr"] = 10
            if egne < imod and side == "h":
                d["hjemmenederlag"] = -5
            hf = sum(1 for e in ev if e[1] == side and fra <= e[0] <= til)
            hi = sum(1 for e in ev if e[1] == mod and fra <= e[0] <= til)
            if hf:
                d["holdmaal"] = 10 * hf
            if hi:
                d["modstandermaal"] = -8 * hi
            g = int(p["goals"])
            if g and pos:
                d["maal"] = g * GOAL[pos]
            if int(p["assists"]):
                d["assist"] = 60 * int(p["assists"])
            if int(p["own_goals"]):
                d["selvmaal"] = -50 * int(p["own_goals"])
            if int(p["yellow_card"]):
                d["gult"] = -20 * int(p["yellow_card"])
            if int(p["red_card"]):
                d["roedt"] = -50 * int(p["red_card"])
            if sejr and sejr[1] == side and sejr[2] == p["player_id"]:
                d["scoring til sejr"] = 40
            if uaf and uaf[1] == side and uaf[2] == p["player_id"]:
                d["scoring til uafgjort"] = 20
            sot = sum(1 for s in skud if s["player_id"] == p["player_id"] and s["result"] == "SavedShot" and s["situation"] != "Penalty")
            if sot:
                d["skud paa maal"] = 10 * sot
            if pos == "goalkeeper":
                red = sum(1 for s in md["shots"][mod] if s["result"] == "SavedShot" and fra <= int(s["minute"]) <= til)
                if red:
                    d["redninger"] = 5 * red
            if pos in ("defense", "goalkeeper") and imod == 0 and (min(til, 90) - fra) >= 60:
                d["clean sheet"] = 50 if pos == "defense" else 75
            ud[p["player_id"]] = {"navn": p["player"], "side": side, "min": t, "pos": pos,
                                  "point": sum(d.values()), "komp": d, "maal_afstemt": ok}
    return ud


def runder(league):
    """Runde = holdets k'te kamp (kontrolleres: begge hold skal vaere enige)."""
    res = sorted([x for x in league["dates"] if x["isResult"]], key=lambda x: x["datetime"])
    nr = collections.Counter()
    ud = collections.defaultdict(list)
    for x in res:
        h, a = x["h"]["title"], x["a"]["title"]
        nr[h] += 1; nr[a] += 1
        if nr[h] != nr[a]:
            raise SystemExit("rundetildeling uenig for %s - %s (%d/%d): udsat kamp?" % (h, a, nr[h], nr[a]))
        ud[nr[h]].append(x)
    return dict(ud)


def point_historik():
    """Dine egne noterede holdet-point (valgfri fil), eller {}."""
    fn = os.path.join(VAULT, "point-historik.json")
    return json.load(io.open(fn, encoding="utf-8")) if os.path.exists(fn) else {}


def holdet_positioner():
    """us_id -> holdet-position via modellens board; navn -> position via point-historik som reserve."""
    import model as M
    _, pid = M.us_kort()
    nav = {norm(v["navn"]): POS_DK.get(norm(v["pos"]), None) for v in point_historik().values()}

    def pos_af(us_pid, navn):
        return pid.get(str(us_pid)) or nav.get(norm(navn))
    return pos_af


def byg():
    import model as M
    league = M.liga_2026()                     # den ligafil med flest spillede kampe
    league_fil = "%d kampe" % sum(1 for x in league["dates"] if x["isResult"])
    pos_af = holdet_positioner()
    ud, advarsler = {}, []
    for rnd, kampe in sorted(runder(league).items()):
        ud[rnd] = {}
        for x in kampe:
            md = kamp(x["id"])
            pk = point_kamp(x, md, pos_af)
            if not all(v["maal_afstemt"] for v in pk.values()):
                advarsler.append("R%d %s-%s: maalhaendelser stemmer ikke med %s-%s" % (
                    rnd, x["h"]["title"], x["a"]["title"], x["goals"]["h"], x["goals"]["a"]))
            for k, v in pk.items():
                v["klub"] = U.UK.get(x[v["side"]]["title"])
                ud[rnd][k] = v
    os.makedirs(os.path.join(VAULT, "facit"), exist_ok=True)
    json.dump({"kilde": "understat getLeagueData + getMatchData, %s" % league_fil, "runder": ud},
              io.open(os.path.join(VAULT, "facit", "understat.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return ud, advarsler


def valider(ud):
    """Sammenlign med holdets egne point (point-historik.json) for spillere med minutter."""
    import model as M
    ph = point_historik()
    if not ph:
        print("(ingen point-historik.json - facit er ikke valideret mod holdets egne point)")
        return
    us_af = M.us_kort()[0]
    print("VALIDERING mod holdets egne point (kun spillere med minutter):")
    for rnd in range(1, max(len(v["r"]) for v in ph.values()) + 1):
        par = []
        for v in ph.values():
            uid = us_af.get(norm(v["navn"]))
            if not uid or uid not in ud.get(rnd, {}) or len(v["r"]) < rnd:
                continue
            par.append((v["r"][rnd - 1], ud[rnd][uid]["point"], v["navn"]))
        if not par:
            continue
        fejl = [b - a for a, b, _ in par]
        eks = sum(1 for e in fejl if e == 0)
        print("  R%d: %d spillere | kroneeksakt %d (%.0f %%) | |fejl| <= 10: %.0f %% | MAE %.1f | snitfejl %+.1f tkr" % (
            rnd, len(par), eks, 100 * eks / len(par), 100 * sum(1 for e in fejl if abs(e) <= 10) / len(par),
            S.mean(abs(e) for e in fejl), S.mean(fejl)))
        store = sorted(par, key=lambda t: -abs(t[1] - t[0]))[:4]
        print("      stoerste afvigelser: " + "; ".join("%s holdet %d / os %d" % (n, a, b) for a, b, n in store))


if __name__ == "__main__":
    ud, adv = byg()
    print("facit skrevet: " + ", ".join("R%d %d spillere" % (r, len(v)) for r, v in sorted(ud.items())))
    for a in adv:
        print("  ADVAR " + a)
    valider(ud)
