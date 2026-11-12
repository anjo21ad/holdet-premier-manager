# -*- coding: utf-8 -*-
"""KVALITETSPORTE: koeres FOER en beslutning og STOPPER ved fejl.

En regel, som vaerktoejet ikke haandhaever, brydes netop under tidspres. Derfor er de tavse faelder
gjort til porte med exit-kode != 0:
  STOP  = data er forkerte eller forældede; der maa ikke traeffes beslutning paa dem
  ADVAR = data er brugbare, men et menneske boer se paa listen

Brug:  python kvalitet.py --runde <N> [--deadline 2026-10-10T13:30]   (deadline: default fra holdets kampplan)
"""
import collections, glob, io, json, os, sys
from datetime import datetime

from hent import SP, KODE

KLUBBER = {"ARS", "AVL", "BOU", "BRE", "BHA", "CHE", "COV", "CRY", "EVE", "FUL", "HUL", "IPS", "LEE",
           "LIV", "MCI", "MUN", "NEW", "NFO", "SUN", "TOT"}
# maks. alder ved deadline (timer) - RotoWire skifter fra predicted til confirmed ~1 t foer kickoff
MAKS_ALDER = {"rw-r{r}.json": 24, "od-r{r}.json": 48, "fm-liga-PL-2026.json": 96}
# (g90, a90)-loft pr. position: over dette er en rate ekstrem i PL (bedste offensive forsvarere ~0,15 xG/90)
GRAENSER = {"defense": (0.20, 0.30), "midfield": (0.60, 0.50), "striker": (1.00, 0.45), "goalkeeper": (0.01, 0.05)}

stop, advar = [], []


def laes(fn):
    """JSON-port: findes, er ikke en HTML-skal, og kan parses."""
    sti = os.path.join(SP, fn)
    if not os.path.exists(sti):
        stop.append("%s mangler" % fn)
        return None
    raw = io.open(sti, "rb").read()
    if raw.lstrip()[:1] == b"<":
        stop.append("%s er HTML, ikke JSON (en HTML-skal paa en flyttet sti?) - %d bytes" % (fn, len(raw)))
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError as e:
        stop.append("%s kan ikke parses: %s" % (fn, e))
        return None


def odds_port(fn, od, par):
    """Oddsfil: rundens kampe, og sandsynligheder der summer til 1 og ligger i et plausibelt omraade."""
    kampe = {(k["h"], k["a"]): k for k in od.get("kampe", [])}
    mangler = sorted(par - set(kampe))
    if mangler:
        stop.append("%s mangler kampe: %s - de regnes paa holdstyrken alene" % (fn, mangler))
    for (h, a), k in kampe.items():
        s = k["pH"] + k["pD"] + k["pA"]
        if abs(s - 1) > 0.01 or not 0.2 <= k["pOver25"] <= 0.9 or min(k["pH"], k["pD"], k["pA"]) <= 0.01:
            stop.append("%s: %s-%s har uplausible sandsynligheder (1X2 sum %.3f, over 2,5 %.2f)" % (fn, h, a, s, k["pOver25"]))


def fotmob_port(r, deadline_utc):
    """Alle aarets PL-kampe foer runden skal ligge i cachen; ellers mangler modellen spilletid og xG."""
    import model as M
    liste = laes("fm-liga-PL-2026.json")
    if liste is None:
        return
    _, dl = M.kampplan()
    closes = [dl[x] for x in sorted(dl)]
    foer = [m for m in liste if not m["aflyst"] and sum(1 for c in closes if c[:16] <= m["tid"][:16]) < r]
    ufaerdige = [m for m in foer if not m["faerdig"]]
    mangler = [m for m in foer if m["faerdig"] and not os.path.exists(os.path.join(SP, "fm-m-%s.json" % m["id"]))]
    if ufaerdige:
        stop.append("FotMob: %d kampe foer R%d er ikke faerdige i kamplisten (gammel liste? koer: python hent.py fotmob)" % (len(ufaerdige), r))
    if mangler:
        stop.append("FotMob: %d spillede kampe mangler i cachen (koer: python hent.py fotmob)" % len(mangler))
    pr_hold = collections.Counter(KODE.get(n, n) for m in foer for n in (m["h"], m["a"]))
    if pr_hold and (len(set(pr_hold.values())) > 1 or min(pr_hold.values()) < r - 1):
        advar.append("FotMob: kampe pr. hold %s foer R%d (udsat kamp?)" % (sorted(set(pr_hold.values())), r))
    for saeson in ("2024", "2025"):
        for liga in ("PL", "L1", "BL", "SA", "LL"):
            if not os.path.exists(os.path.join(SP, "fm-liga-%s-%s.json" % (liga, saeson))):
                stop.append("FotMob-historik mangler: %s %s (koer: python hent.py fotmob historik)" % (liga, saeson))


def holdet_port(r, meta):
    """Den valgte holdet-fil skal vaere hentet efter seneste afsluttede runde - ellers mangler priserne dens point."""
    import model as M
    d = M.J("holdet-pl-schedule.json")
    slut = {i + 1: x["end"][:10] for i, x in enumerate(d["rounds"])}
    fn = meta["holdet_fil"]
    dd, mm = int(fn[7:9]), int(fn[9:11])
    hentet = "%d-%02d-%02d" % (2026 if mm >= 7 else 2027, mm, dd)
    if r > 1 and hentet < slut[r - 1]:
        stop.append("holdet-filen %s er hentet foer R%d sluttede (%s) - priserne mangler rundens point (koer: python hent.py holdet)"
                    % (fn, r - 1, slut[r - 1]))


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
    od = laes("od-r%d.json" % r)
    if od is not None:
        odds_port("od-r%d.json" % r, od, set(M.kampplan()[0].get(r, [])))
    fotmob_port(r, deadline)

    # 3. modellens OUTPUT - det er det, handel.py bruger
    try:
        board, meta = M.byg(r)
        if meta["matchet"] < 0.7 * meta["aktive"]:
            stop.append("kun %d af %d spillere matchet mod FotMob" % (meta["matchet"], meta["aktive"]))
        holdet_port(r, meta)
        if r not in meta["marked_runder"]:
            stop.append("ingen oddsfil for R%d (koer: python hent.py odds N) - naeste runde regnes paa holdstyrken alene" % r)
        prior = {k: v for k, v in meta["prior"].items() if k != "GK"}
        if any(v[0] <= 0 for v in prior.values()):
            stop.append("rolleprior paa 0 for %s - for faa spillere med nok minutter (mangler historikken?)" % sorted(k for k, v in prior.items() if v[0] <= 0))
    except Exception as e:
        stop.append("modelkoerslen (model.py) fejlede: %r" % e)
        board = None
    if board is not None:
        fremmede = sorted({x["club"] for x in board} - KLUBBER)
        if fremmede:
            stop.append("klubber uden for spillets univers: %s" % fremmede)
        # holdet er eneste autoritet paa klub: afvigelser mod FotMobs seneste kamp LISTES, overskrives aldrig
        senest = {}
        for _, k in sorted(M.kampe_foer(r), key=lambda t: t[1]["tid"]):
            for p in k["spillere"]:
                senest[p["id"]] = KODE.get(k[p["hold"]], k[p["hold"]])
        afv = [(x["name"], x["club"], senest[x["fm_id"]]) for x in board if x["fm_id"] and senest.get(x["fm_id"]) not in (None, x["club"])]
        if afv:
            advar.append("klub: holdet og FotMob er uenige om %d spillere (holdet gaelder): %s" % (len(afv), ", ".join("%s %s/%s" % t for t in afv[:8])))
        blinde = [x["name"] for x in board if not x["fm_id"] and x["pS_neste"] >= 0.5]
        if blinde:
            advar.append("%d sandsynlige startere uden FotMob-match (rater = prior alene): %s" % (len(blinde), ", ".join(blinde[:10])))
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
