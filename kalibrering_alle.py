# -*- coding: utf-8 -*-
"""KALIBRERING PAA HELE PULJEN - SR 11-7 'outcomes analysis'.

Spoergsmaalet: naar modellen siger X tkr, hvad faar spilleren saa? Maalt paa alle spillere,
ikke kun dit eget hold, og opdelt efter hvor meget evidens prognosen hvilede paa.

  haeldning beta (realiseret ~ a + beta * prognose): 1 = kalibreret, < 1 = overmod
      (prognoserne spreder sig mere end virkeligheden - noejagtig hvad optimizerens forbandelse udnytter)
  MSE: samlet fejl - til at sammenligne modelvarianter paa de samme spiller-runder
  top-test: de spillere modellen rangerer hoejest - leverer de det lovede?

Prognoser:  exante/r<N>[-<maerke>].json (praeregistrer.py) - medtages naar facit for runden findes.
            En variant praeregistreret som fx r7-straffe.json maales side om side med r7.json.
Facit:      facit/understat.json (facit_alle.py)
Ikke-spillende spillere faar -5 (baenk). holdet giver 0 ved 'ikke i truppen' - lille skaevhed.

Brug:  python kalibrering_alle.py
"""
import glob, io, json, math, os, re, statistics as S, unicodedata

VAULT = os.path.dirname(os.path.abspath(__file__))


def norm(x):
    return "".join(c for c in unicodedata.normalize("NFD", x or "") if unicodedata.category(c) != "Mn").lower().strip()


def ols(xs, ys):
    mx, my = S.mean(xs), S.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    res = [y - a - b * x for x, y in zip(xs, ys)]
    se = math.sqrt(sum(r * r for r in res) / (len(xs) - 2) / sxx)
    return a, b, se


def maal(par):
    """par: [(prognose, realiseret)] -> (n, MSE, bias, beta, SE)."""
    xs, ys = [p for p, _ in par], [r for _, r in par]
    a, b, se = ols(xs, ys)
    return len(par), S.mean((r - p) ** 2 for p, r in par), S.mean(r - p for p, r in par), b, se


def prognoser():
    """[(kilde, runde, [(navn, klub, pos, prognose, evidens i hele kampe)])] fra praeregistreringerne."""
    ud = []
    for fn in sorted(glob.glob(os.path.join(VAULT, "exante", "r*.json"))):
        m = re.fullmatch(r"r(\d+)(-[a-z0-9]+)?\.json", os.path.basename(fn))
        if not m:
            continue
        d = json.load(io.open(fn, encoding="utf-8"))
        rows = [(r["name"], r["club"], r["pos"], r["ev_neste"], (r.get("evidens_min") or 0) / 90.0)
                for r in d["spillere"] if r.get("ev_neste") is not None]
        ud.append((os.path.basename(fn), int(m.group(1)), rows))
    return ud


def main():
    fn = os.path.join(VAULT, "facit", "understat.json")
    if not os.path.exists(fn):
        raise SystemExit("facit/understat.json mangler - koer python facit_alle.py foerst")
    facit = json.load(io.open(fn, encoding="utf-8"))["runder"]
    import model as M
    us_af = M.us_kort()[0]
    samlet = {}
    for kilde, rnd, rows in prognoser():
        f = facit.get(str(rnd))
        if not f:
            print("(%s: intet facit for R%d endnu)" % (kilde, rnd))
            continue
        for navn, klub, pos, ev, n90 in rows:
            uid = us_af.get(norm(navn))
            if uid is None:
                continue                      # uden understat-id kan facit ikke slaas op
            real = f[uid]["point"] if uid in f else -5
            samlet.setdefault(kilde, []).append((rnd, navn, pos, ev, real, n90))
    if not samlet:
        print("ingen praeregistreringer med facit endnu (exante/ + facit_alle.py efter runden)")

    for kilde, par in samlet.items():
        n, mse, bias, b, se = maal([(p[3], p[4]) for p in par])
        print("\n=== %s: %d spiller-runder ===" % (kilde, n))
        print("  snit prognose %.1f  snit realiseret %.1f  |  MSE %.0f  bias %+.1f  |  haeldning beta %.2f (SE %.2f)" % (
            S.mean(p[3] for p in par), S.mean(p[4] for p in par), mse, bias, b, se))
        spand = [("evidens < 5", lambda n: n < 5), ("evidens 5-15", lambda n: 5 <= n < 15), ("evidens >= 15", lambda n: n >= 15)]
        print("  efter evidens (hele kampe):")
        for lbl, fn in spand:
            sub = [p for p in par if fn(p[5])]
            if len(sub) < 30:
                print("    %-14s n=%3d  (for faa)" % (lbl, len(sub)))
                continue
            a2, b2, se2 = ols([p[3] for p in sub], [p[4] for p in sub])
            print("    %-14s n=%3d  prognose %5.1f  realiseret %5.1f  beta %.2f (SE %.2f)" % (
                lbl, len(sub), S.mean(p[3] for p in sub), S.mean(p[4] for p in sub), b2, se2))
        print("  efter position:")
        for pos in ("goalkeeper", "defense", "midfield", "striker"):
            sub = [p for p in par if p[2] == pos]
            if len(sub) >= 30:
                a2, b2, se2 = ols([p[3] for p in sub], [p[4] for p in sub])
                print("    %-11s n=%3d  prognose %5.1f  realiseret %5.1f  beta %.2f (SE %.2f)" % (
                    pos, len(sub), S.mean(p[3] for p in sub), S.mean(p[4] for p in sub), b2, se2))
        print("  top-test (optimizerens forbandelse): leverer de hoejest rangerede det lovede?")
        srt = sorted(par, key=lambda p: -p[3])
        for andel in (0.02, 0.05, 0.10, 0.25):
            sub = srt[:max(1, int(len(srt) * andel))]
            mp, mr = S.mean(p[3] for p in sub), S.mean(p[4] for p in sub)
            tynd = [p for p in sub if p[5] < 5]
            print("    top %3.0f %% (n=%3d): prognose %6.1f  realiseret %6.1f  (%.0f %% af det lovede)  heraf tynd evidens %d" % (
                100 * andel, len(sub), mp, mr, 100 * mr / mp if mp else float("nan"), len(tynd)))


if __name__ == "__main__":
    main()
