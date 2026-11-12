# -*- coding: utf-8 -*-
"""TESTS UDEN DATA: modellens regler, beslutningsreglen, kvalitetsportene og pointmotoren.

Alt koerer paa syntetiske spillere og kampe, saa testene virker i en frisk klon og i CI.
PASS = virker · FAIL = brudt · FEJL = testen selv fejlede
Brug:  python test_model.py
"""
import csv, io, json, math, os, shutil, sys, tempfile, traceback

import model as M
import handel as HA
import kvalitet as KV
import facit_alle as FA
import praeregistrer as PR

resultat = []


def test(navn):
    def wrap(fn):
        try:
            fn()
            resultat.append(("PASS", navn, ""))
        except AssertionError as e:
            resultat.append(("FAIL", navn, str(e)))
        except Exception:
            resultat.append(("FEJL", navn, traceback.format_exc().splitlines()[-1]))
        return fn
    return wrap


# ---------- et syntetisk univers: fire klubber, 13 runder tilbage ----------
KLUBBER = ["AAA", "BBB", "CCC", "DDD"]
CTX = {"naeste": {c: (1.4, 1.2) + M.resultat(1.4, 1.2) + (True, "BBB") for c in KLUBBER},
       "prog": {c: [(1.3, 1.3) + M.resultat(1.3, 1.3) + (i % 2 == 0,) for i in range(12)] for c in KLUBBER},
       "att_norm": {c: 1.3 for c in KLUBBER}, "rest": 12}
PRIOR = {"goalkeeper": (0.0, 0.002), "defense": (0.05, 0.05), "midfield": (0.15, 0.15), "striker": (0.5, 0.09)}


def spiller(navn, klub, pos, pris, g90, a90, ps=0.9, n=3000.0):
    """En board-raekke, hvis Marcel-rate med K giver netop g90/a90 ud fra n vaegtede startminutter."""
    pg, pa = PRIOR[pos]
    r = {"name": navn, "club": klub, "pos": pos, "price": pris, "g90": g90, "a90": a90,
         "pS_neste": ps, "pStart": ps, "bt": 0.95, "f60": 0.95,
         "forklaring": {"sum_xg": (g90 * (n + M.K) - M.K * pg) / 90, "sum_xa": (a90 * (n + M.K) - M.K * pa) / 90,
                        "n": n, "prior": [pg, pa], "vaegt_paa_prior": round(M.K / (n + M.K), 2), "pen90": 0.0, "straffeandel": 0.0,
                        "saesoner": {}, "status": ps, "startandel": ps, "klubkampe": 15, "flag": []}}
    return M.evaluer(r, CTX)


HOLD = [spiller("Keeper Et", "AAA", "goalkeeper", 5.0, 0.0, 0.002),
        spiller("Back Et", "AAA", "defense", 4.0, 0.05, 0.05), spiller("Back To", "BBB", "defense", 4.0, 0.05, 0.05),
        spiller("Back Tre", "CCC", "defense", 4.0, 0.05, 0.05), spiller("Back Fire", "DDD", "defense", 4.0, 0.05, 0.05),
        spiller("Midt Et", "AAA", "midfield", 5.0, 0.2, 0.2), spiller("Midt To", "BBB", "midfield", 5.0, 0.2, 0.2),
        spiller("Midt Tre", "CCC", "midfield", 4.0, 0.15, 0.15), spiller("Midt Svag", "DDD", "midfield", 3.0, 0.05, 0.05, ps=0.6),
        spiller("Angriber Et", "AAA", "striker", 8.0, 0.6, 0.1), spiller("Angriber To", "BBB", "striker", 6.0, 0.45, 0.09)]
ALT = [spiller("Midt Stjerne", "CCC", "midfield", 4.0, 0.35, 0.25, ps=0.92, n=4000),
       spiller("Ukendt Talent", "CCC", "midfield", 3.0, 0.40, 0.30, ps=0.92, n=300),
       spiller("Dyr Stjerne", "CCC", "midfield", 20.0, 0.5, 0.3),
       spiller("AAA Midt", "AAA", "midfield", 4.0, 0.3, 0.2),
       spiller("Midt Lidt Bedre", "CCC", "midfield", 3.0, 0.07, 0.06, ps=0.62),
       spiller("Midt Tre Klon", "CCC", "midfield", 4.0, 0.15, 0.15)]
B = {M.norm(r["name"]): r for r in HOLD + ALT}
NAVNE = [r["name"] for r in HOLD]
INFO = {"runde": 8, "hold": NAVNE, "gebyrfri": NAVNE, "kapital": sum(r["price"] for r in HOLD) + 2.0, "kaptajn": "Angriber Et"}


# ---------- modellens regler ----------
@test("Marcel: uden minutter er raten lig rolleprioren")
def _():
    assert M.rate(0.0, 0.0, 0.3) == 0.3


@test("Marcel: med n = K vejer data og prior lige meget")
def _():
    data_rate, prior = 0.6, 0.2
    r = M.rate(data_rate * M.K / 90, M.K, prior)
    assert abs(r - 0.4) < 1e-12, r


@test("Poisson: sejr + uafgjort + nederlag = 1, og lige hold er symmetriske")
def _():
    pw, pd = M.resultat(1.4, 1.1)
    pl = M.resultat(1.1, 1.4)[0]
    assert abs(pw + pd + pl - 1) < 1e-5, pw + pd + pl    # summen skaeres af ved 10 maal
    pw2, pd2 = M.resultat(1.3, 1.3)
    assert abs(pw2 - (1 - pw2 - pd2)) < 1e-5, (pw2, pd2)


@test("positioner: FotMobs positionId oversaettes til roller efter linje og side")
def _():
    forvent = {11: "GK", 32: "FB", 34: "CB", 38: "FB", 64: "CM", 75: "CM", 83: "AM", 85: "AM", 105: "FW", 115: "FW"}
    faktisk = {p: M.ROLLE[M.fm_pos(p)] for p in forvent}
    assert faktisk == forvent, faktisk


@test("markedet -> lambda: loes() genfinder de lambdaer, der skabte priserne")
def _():
    lh, la = 1.6, 1.1
    ph = M.resultat(lh, la, N=11)[0]
    T = lh + la
    over = 1 - math.exp(-T) * (1 + T + T * T / 2)
    l1, l2 = M.loes(ph, over)
    assert abs(l1 - lh) < 0.02 and abs(l2 - la) < 0.02, (l1, l2)


@test("pointformel: en spiller uden spilletid koster -5 (baenk)")
def _():
    r = dict(HOLD[5], pS_neste=0.0)
    e = M.ev_kamp(r, 1.4, 1.2, 0.45, 0.25, True, 0.0, 1.3)
    assert abs(e - (-5.0)) < 1e-12, e


@test("pointformel: hoejere xG/90 giver hoejere forventning")
def _():
    lav = M.ev_kamp(dict(HOLD[5], g90=0.1), 1.4, 1.2, 0.45, 0.25, True, 0.9, 1.3)
    hoej = M.ev_kamp(dict(HOLD[5], g90=0.4), 1.4, 1.2, 0.45, 0.25, True, 0.9, 1.3)
    assert hoej > lav


@test("EV beregnes eet sted: evaluer() er deterministisk")
def _():
    x = dict(HOLD[9])
    assert abs(M.evaluer(x, CTX)["ev_tot"] - HOLD[9]["ev_tot"]) < 1e-9


# ---------- beslutningsreglen ----------
@test("straffeleddet foelger med i K/2 og 2K: kun npxG-raten shrinkes, straffeleddet laegges til bagefter")
def _():
    r = spiller("Straffe Skytte", "DDD", "midfield", 4.5, 0.20, 0.15)
    r["forklaring"]["pen90"] = 0.05
    for k in (M.K / 2, 2 * M.K):
        x = HA.variant(r, CTX, k, 0.0)
        f = r["forklaring"]
        assert abs(x["g90"] - (M.rate(f["sum_xg"], f["n"], f["prior"][0], k) + 0.05)) < 1e-12, (k, x["g90"])


@test("symmetri: gevinst(A->B) = -gevinst(B->A) eksakt")
def _():
    d1, _ = HA.gevinst(B, CTX, INFO, ["Midt Svag"], ["Midt Stjerne"], HA.KONTROLLER[0])
    info2 = dict(INFO, hold=[n for n in NAVNE if n != "Midt Svag"] + ["Midt Stjerne"])
    d2, _ = HA.gevinst(B, CTX, info2, ["Midt Stjerne"], ["Midt Svag"], HA.KONTROLLER[0])
    assert abs(d1 + d2) < 1e-6, (d1, d2)


@test("en klar opgradering klarer alle seks kontroller")
def _():
    v = HA.vurder(B, CTX, INFO, ["Midt Svag"], ["Midt Stjerne"])
    assert v["robust"] and v["antal_pos"] == 6, v


@test("standard = ingen handel: positiv basis er ikke nok")
def _():
    v = HA.vurder(B, CTX, INFO, ["Midt Svag"], ["Midt Lidt Bedre"])
    assert v["basis"] > 0 and not v["robust"], v


@test("en prior-spiller (> 50 % prior) anbefales aldrig, selv med seks positive")
def _():
    v = HA.vurder(B, CTX, INFO, ["Midt Svag"], ["Ukendt Talent"])
    assert v["antal_pos"] == 6 and v["prior_spillere"] == ["Ukendt Talent"] and not v["robust"], v


@test("ugyldige handler afvises: formation, klubloft og budget")
def _():
    assert "formation" in HA.vurder(B, CTX, INFO, ["Keeper Et"], ["Midt Stjerne"])["ugyldig"]
    assert "samme klub" in HA.vurder(B, CTX, INFO, ["Midt Svag"], ["AAA Midt"])["ugyldig"]
    assert "budget" in HA.vurder(B, CTX, INFO, ["Midt Svag"], ["Dyr Stjerne"])["ugyldig"]


@test("gebyr og bankrente: en identisk spiller koster 1 % gebyr + renten af gebyret = -45,2 tkr")
def _():
    d, _ = HA.gevinst(B, CTX, INFO, ["Midt Tre"], ["Midt Tre Klon"], HA.KONTROLLER[0])
    forventet = -(0.01 * 4.0 * 1000 + 0.01 * 4.0 * 10 * (CTX["rest"] + 1))
    assert abs(d - forventet) < 1e-9, (d, forventet)


@test("beslutningsloggen oprettes med header ved foerste brug")
def _():
    d = tempfile.mkdtemp()
    gammel = HA.VAULT
    try:
        HA.VAULT = d
        v = HA.vurder(B, CTX, INFO, ["Midt Svag"], ["Midt Stjerne"])
        HA.log("Svag > Stjerne", ["Midt Svag"], ["Midt Stjerne"], v, "stoerste risiko: test", 8)
        HA.log("Svag > Stjerne", ["Midt Svag"], ["Midt Stjerne"], v, "igen", 8)
        rows = list(csv.reader(io.open(os.path.join(d, "beslutningslog.csv"), encoding="utf-8")))
        assert rows[0] == HA.LOG_FELTER and len(rows) == 3, rows
    finally:
        HA.VAULT = gammel; shutil.rmtree(d)


# ---------- kvalitetsporte ----------
def i_tmp(indhold):
    d = tempfile.mkdtemp()
    io.open(os.path.join(d, "x.json"), "wb").write(indhold)
    KV.SP, KV.stop[:] = d, []
    return d


@test("port: en kort HTML-side (fx en 404) stopper")
def _():
    d = i_tmp(b"<!DOCTYPE html>" + b" " * 446)
    try:
        KV.laes("x.json")
        assert KV.stop
    finally:
        KV.SP = M.SP; shutil.rmtree(d)


@test("port: holdet-HTML-skal stopper selv over 1000 bytes")
def _():
    d = i_tmp(b"<html>" + b"x" * 5000 + b"</html>")
    try:
        KV.laes("x.json")
        assert any("HTML" in s for s in KV.stop), KV.stop
    finally:
        KV.SP = M.SP; shutil.rmtree(d)


def od(kampe):
    return {"runde": 8, "kilde": "test", "kampe": [{"h": h, "a": a, "pH": 0.5, "pD": 0.25, "pA": 0.25, "pOver25": 0.55} for h, a in kampe]}


PAR = {("AAA", "BBB"), ("CCC", "DDD")}


@test("port: en oddsfil med alle rundens kampe og plausible sandsynligheder passerer")
def _():
    KV.stop[:] = []
    KV.odds_port("od-r8.json", od(PAR), PAR)
    assert not KV.stop, KV.stop


@test("port: en oddsfil, der mangler en kamp eller har uplausible sandsynligheder, stopper")
def _():
    KV.stop[:] = []
    KV.odds_port("od-r8.json", od([("AAA", "BBB")]), PAR)
    assert any("mangler kampe" in s for s in KV.stop), KV.stop
    KV.stop[:] = []
    d = od(PAR); d["kampe"][0]["pH"] = 0.9
    KV.odds_port("od-r8.json", d, PAR)
    assert any("uplausible" in s for s in KV.stop), KV.stop


# ---------- facit fra holdets priser ----------
def holdet_fil(d, ddmm, priser):
    json.dump({"items": [{"personId": p, "price": v, "startPrice": 4000000} for p, v in priser.items()], "_embedded": {"persons": {}}},
              io.open(os.path.join(d, "holdet-%s.json" % ddmm), "w", encoding="utf-8"))


def kampplan_fil(d):
    runder = [{"close": "2026-08-21T19:00:00Z", "end": "2026-08-25T10:00:00Z"}, {"close": "2026-08-28T19:00:00Z", "end": "2026-09-01T10:00:00Z"},
              {"close": "2026-09-04T19:00:00Z", "end": "2026-09-07T10:00:00Z"}]
    json.dump({"rounds": runder, "events": []}, io.open(os.path.join(d, "holdet-pl-schedule.json"), "w", encoding="utf-8"))


@test("facit: point = prisdelta mellem snapshots efter hver runde; en runde uden snapshot faar intet facit")
def _():
    d = tempfile.mkdtemp()
    gl = (FA.SP, FA.VAULT)
    try:
        kampplan_fil(d)
        holdet_fil(d, "2608", {1: 4100000, 2: 3995000})     # efter R1 (slut 25/8, foer R2's deadline 28/8)
        holdet_fil(d, "0209", {1: 4317000, 2: 3995000})     # efter R2
        FA.SP, FA.VAULT = d, d
        f = FA.byg()
        assert f["runder"]["1"] == {"1": 100, "2": -5}, f["runder"]["1"]
        assert f["runder"]["2"] == {"1": 217, "2": 0}, f["runder"]["2"]
        assert "3" not in f["runder"], f["runder"].keys()
    finally:
        FA.SP, FA.VAULT = gl
        shutil.rmtree(d)


@test("port: en holdet-fil hentet foer seneste runde sluttede stopper")
def _():
    d = tempfile.mkdtemp()
    gl = M.SP
    try:
        kampplan_fil(d)
        M.SP, KV.stop[:] = d, []
        KV.holdet_port(3, {"holdet_fil": "holdet-0209.json"})     # efter R2 sluttede 1/9: frisk
        assert not KV.stop, KV.stop
        KV.holdet_port(3, {"holdet_fil": "holdet-2608.json"})     # mangler R2's point
        assert any("hentet foer R2 sluttede" in s for s in KV.stop), KV.stop
    finally:
        M.SP = gl
        shutil.rmtree(d)


# ---------- praeregistrering ----------
@test("praeregistrering overskrives aldrig")
def _():
    d = tempfile.mkdtemp()
    gammel, argv = PR.VAULT, sys.argv
    try:
        os.makedirs(os.path.join(d, "exante"))
        io.open(os.path.join(d, "exante", "r99.json"), "w").write("{}")
        PR.VAULT, sys.argv = d, ["praeregistrer.py", "99"]
        try:
            PR.main()
            assert False, "praeregistrer.py skrev oven i en eksisterende fil"
        except SystemExit as e:
            assert "overskrives ikke" in str(e), e
    finally:
        PR.VAULT, sys.argv = gammel, argv
        shutil.rmtree(d)


if __name__ == "__main__":
    for status, navn, info in resultat:
        print("%-5s %s%s" % (status, navn, ("   [" + info + "]") if info else ""))
    n = {s: sum(1 for x in resultat if x[0] == s) for s in ("PASS", "FAIL", "FEJL")}
    print("\n%(PASS)d pass, %(FAIL)d fail, %(FEJL)d fejl" % n)
    sys.exit(1 if n["FAIL"] or n["FEJL"] else 0)
