# -*- coding: utf-8 -*-
"""KVALITETSPORTE: koeres FOER en beslutning og STOPPER ved fejl.

En regel, som vaerktoejet ikke haandhaever, brydes netop under tidspres. Derfor er de tavse faelder
gjort til porte med exit-kode != 0:
  STOP  = data er forkerte eller forældede; der maa ikke traeffes beslutning paa dem
  ADVAR = data er brugbare, men et menneske boer se paa listen

Brug:  python kvalitet.py --runde <N> [--deadline 2026-10-10T13:30]   (deadline: default fra holdets kampplan)
"""
import glob, io, json, os, sys
from datetime import datetime

from hent import SP, UK

KLUBBER = {"ARS", "AVL", "BOU", "BRE", "BHA", "CHE", "COV", "CRY", "EVE", "FUL", "HUL", "IPS", "LEE",
           "LIV", "MCI", "MUN", "NEW", "NFO", "SUN", "TOT"}
# maks. alder ved deadline (timer) - RotoWire skifter fra predicted til confirmed ~1 t foer kickoff
MAKS_ALDER = {"rw-r{r}.json": 24, "bf-r{r}-MATCH_ODDS.json": 48, "bf-r{r}-BOTH_TEAMS_TO_SCORE.json": 48,
              "us-league-2026.json": 96}
# (g90, a90)-loft pr. position: over dette er en rate ekstrem i PL (bedste offensive forsvarere ~0,15 xG/90)
GRAENSER = {"defense": (0.20, 0.30), "midfield": (0.60, 0.50), "striker": (1.00, 0.45), "goalkeeper": (0.01, 0.05)}

stop, advar = [], []


def laes(fn):
    """JSON-port: findes, er ikke en HTML-skal eller en 461-bytes 404, og kan parses."""
    sti = os.path.join(SP, fn)
    if not os.path.exists(sti):
        stop.append("%s mangler" % fn)
        return None
    raw = io.open(sti, "rb").read()
    if raw.lstrip()[:1] == b"<":
        stop.append("%s er HTML, ikke JSON (holdet-skal eller understat-404?) - %d bytes" % (fn, len(raw)))
        return None
    if len(raw) < 1000:
        stop.append("%s er kun %d bytes (understat uden XHR-header giver 461)" % (fn, len(raw)))
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError as e:
        stop.append("%s kan ikke parses: %s" % (fn, e))
        return None


def pris_mod_facit(board, r):
    """Andel af spillerne, hvor pris = startpris + realiserede point (point = prisdelta) inden for 20 tkr.
    En forældet holdet-fil falder igennem her, fordi dens priser mangler de seneste runders point.
    None, hvis facit endnu ikke er bygget (python facit_alle.py)."""
    fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), "facit", "understat.json")
    if not os.path.exists(fn):
        return None
    fac = json.load(io.open(fn, encoding="utf-8"))["runder"]
    afv = [abs(x["price"] - x["startPrice"] - sum(fac[str(k)].get(str(x["us_id"]), {}).get("point", -5) / 1000.0
                                                 for k in range(1, r) if str(k) in fac))
           for x in board if x["us_id"]]
    return sum(1 for a in afv if a <= 0.02) / len(afv)


def betfair_port(fn, bf):
    """Betfair-fil: mindst 10 kampe, kun filens egen markedstype og engelske runner-navne."""
    ev = [e for et in bf.get("eventTypes", []) for e in et.get("eventNodes", [])]
    if len([e for e in ev if " v " in e["event"]["eventName"]]) < 10:
        stop.append("%s: under 10 kampe med ' v ' i navnet (locale=da eller ' - '-navne?)" % fn)
    typer = {m["description"].get("marketType") for e in ev for m in e["marketNodes"]}
    if typer != {fn.split("-", 2)[2][:-5]}:
        stop.append("%s indeholder markedstyperne %s (Match Odds i BTTS-filen faar runden til at falde stille ud af modellen)"
                    % (fn, sorted(typer)))
    navne = {rn["description"]["runnerName"] for e in ev for m in e["marketNodes"] for rn in m["runners"]}
    if navne & {"Uafgjort", "Ja", "Nej"}:
        stop.append("%s er hentet med locale=da - parseren forventer engelske runner-navne" % fn)


def alder(fn, deadline):
    sti = os.path.join(SP, fn)
    return (deadline - datetime.fromtimestamp(os.path.getmtime(sti))).total_seconds() / 3600 if os.path.exists(sti) else None


def main():
    import model as M
    a = sys.argv[1:]
    if "--runde" not in a:
        sys.exit(__doc__)
    r = int(a[a.index("--runde") + 1])
    if "--deadline" in a:
        deadline = datetime.fromisoformat(a[a.index("--deadline") + 1])
    else:   # holdets kampplan er i UTC; sammenlignes med filtider i lokal tid
        deadline = datetime.fromisoformat(M.kampplan()[1][r].replace("Z", "+00:00")).astimezone().replace(tzinfo=None)

    # 1. friskhed ved deadline
    for skabelon, maks in MAKS_ALDER.items():
        fn = skabelon.format(r=r)
        t = alder(fn, deadline)
        if t is None:
            stop.append("%s mangler" % fn)
        elif t > maks:
            stop.append("%s er %.0f t gammel ved deadline (maks %d t)" % (fn, t, maks))

    # 2. kildernes indhold
    rw = laes("rw-r%d.json" % r)
    if rw is not None:
        if set(rw) != KLUBBER:
            stop.append("RotoWire mangler klubber: %s" % sorted(KLUBBER - set(rw)))
        for k, v in rw.items():
            if len(v.get("xi", [])) != 11:
                stop.append("RotoWire %s har %d i XI (parser-forskydning?)" % (k, len(v.get("xi", []))))
    us = laes("us-league-2026.json")
    if us is not None:
        hist = {t["title"]: len(t.get("history", [])) for t in us["teams"].values()}
        if len(set(hist.values())) > 1 or min(hist.values()) < r - 1:
            stop.append("understat: kampe pr. hold %s - forventet %d spillede runder for alle" % (sorted(set(hist.values())), r - 1))
    for fn in ("bf-r%d-MATCH_ODDS.json" % r, "bf-r%d-BOTH_TEAMS_TO_SCORE.json" % r):
        bf = laes(fn)
        if bf is not None:
            betfair_port(fn, bf)
    for fn in sorted(glob.glob(os.path.join(SP, "us-p-*.json"))):
        raw = io.open(fn, "rb").read()
        if len(raw) < 1000 or raw[:1] != b"{":
            stop.append("%s er %d bytes / ikke JSON" % (os.path.basename(fn), len(raw)))

    # 3. modellens OUTPUT - det er det, handel.py bruger
    try:
        board, meta = M.byg(r)
        if meta["matchet"] < 0.7 * meta["aktive"]:
            stop.append("kun %d af %d spillere matchet mod understat" % (meta["matchet"], meta["aktive"]))
        andel = pris_mod_facit(board, r)
        if andel is None:
            advar.append("facit/understat.json mangler (koer python facit_alle.py) - holdet-filens alder er ikke tjekket")
        elif andel < 0.7:
            stop.append("holdet-filen %s stemmer ikke med facit: kun %.0f %% af priserne = startpris + point (foraeldet fil?)" % (meta["holdet_fil"], 100 * andel))
        if r not in meta["marked_runder"]:
            stop.append("ingen Betfair-filer for R%d (koer: python hent.py betfair N) - naeste runde regnes paa tier alene" % r)
    except Exception as e:
        stop.append("modelkoerslen (model.py) fejlede: %r" % e)
        board = None
    if board is not None:
        fremmede = sorted({x["club"] for x in board} - KLUBBER)
        if fremmede:
            stop.append("klubber uden for spillets univers: %s" % fremmede)
        if us is not None:   # holdet er eneste autoritet paa klub: afvigelser LISTES, overskrives aldrig
            usklub = {str(p["id"]): UK.get(p["team_title"].split(",")[-1].strip()) for p in us["players"]}
            afv = [(x["name"], x["club"], usklub[str(x["us_id"])]) for x in board
                   if x["us_id"] and usklub.get(str(x["us_id"])) not in (None, x["club"])]
            if afv:
                advar.append("klub: holdet og understat er uenige om %d spillere (holdet gaelder): %s"
                             % (len(afv), ", ".join("%s %s/%s" % t for t in afv[:8])))
        blinde = [x["name"] for x in board if not x["us_id"] and x["pS_neste"] >= 0.5]
        if blinde:
            advar.append("%d sandsynlige startere uden understat-match (rater = prior alene): %s" % (len(blinde), ", ".join(blinde[:10])))
        for x in board:
            gmax, amax = GRAENSER[x["pos"]]
            if x["g90"] > gmax or x["a90"] > amax:
                advar.append("uplausibel rate: %s (%s) g90 %.2f a90 %.2f" % (x["name"], x["pos"], x["g90"], x["a90"]))
            for f in ("pStart", "pS_neste"):
                if not 0 <= x[f] <= 1:
                    stop.append("%s: %s = %s uden for [0,1]" % (x["name"], f, x[f]))

    print("KVALITETSPORTE R%d (deadline %s lokal tid)" % (r, deadline.isoformat(timespec="minutes")))
    for s in stop:
        print("  STOP   " + s)
    for s in advar:
        print("  ADVAR  " + s)
    if not stop and not advar:
        print("  alle porte groenne")
    if stop:
        print("\n%d STOP - der maa ikke traeffes beslutning paa disse data." % len(stop))
        sys.exit(1)
    print("\ningen STOP (%d advarsler)." % len(advar))


if __name__ == "__main__":
    main()
