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
                        "n": n, "prior": [pg, pa], "vaegt_paa_prior": round(M.K / (n + M.K), 2),
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


@test("markedet -> lambda: loes() genfinder de lambdaer, der skabte priserne")
def _():
    lh, la = 1.6, 1.1
    ph = M.resultat(lh, la, N=11)[0]
    ikke_begge = math.exp(-la) + math.exp(-lh) - math.exp(-lh - la)
    l1, l2 = M.loes(ph, ikke_begge)
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


@test("port: understat-404 (461 bytes HTML) stopper")
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


def bf_json(markedstype, runnere):
    ev = [{"event": {"eventName": "Hold%d v Hold%d" % (i, i + 10)},
           "marketNodes": [{"description": {"marketType": markedstype},
                            "runners": [{"description": {"runnerName": n}} for n in runnere]}]} for i in range(10)]
    return {"eventTypes": [{"eventNodes": ev}]}


@test("port: Match Odds i BTTS-filen stopper; en korrekt BTTS-fil passerer")
def _():
    KV.stop[:] = []
    KV.betfair_port("bf-r8-BOTH_TEAMS_TO_SCORE.json", bf_json("MATCH_ODDS", ["Hold1", "Hold11", "The Draw"]))
    assert any("markedstyperne" in s for s in KV.stop), KV.stop
    KV.stop[:] = []
    KV.betfair_port("bf-r8-BOTH_TEAMS_TO_SCORE.json", bf_json("BOTH_TEAMS_TO_SCORE", ["Yes", "No"]))
    assert not KV.stop, KV.stop


@test("port: Betfair hentet paa dansk stopper")
def _():
    KV.stop[:] = []
    KV.betfair_port("bf-r8-MATCH_ODDS.json", bf_json("MATCH_ODDS", ["Hold1", "Hold11", "Uafgjort"]))
    assert any("locale" in s for s in KV.stop), KV.stop


# ---------- pointmotoren (facit) ----------
def rost(pid, navn, tid, position, maal=0, roster_in="0"):
    return {"player_id": pid, "player": navn, "time": str(tid), "position": position, "roster_in": roster_in,
            "red_card": "0", "yellow_card": "0", "goals": str(maal), "assists": "0", "own_goals": "0"}


def skud(pid, minut, side, result="SavedShot"):
    return {"player_id": pid, "minute": str(minut), "h_a": side, "result": result, "situation": "OpenPlay"}


# udekamp 0-1: forsvareren (1) scorer i 30. minut, hjemmekeeperen (2) redder tre skud,
# indskiftet angriber (3) og indskiftet forsvarer (4) kommer paa i 70. minut
KAMP = {"rosters": {"h": {"a": rost("2", "Keeper Hjemme", 90, "GK")},
                    "a": {"a": rost("1", "Back Ude", 90, "DC", maal=1), "b": rost("3", "Sub Angriber", 20, "Sub"),
                          "c": rost("4", "Sub Back", 20, "Sub")}},
        "shots": {"h": [], "a": [skud("1", 30, "a", "Goal")] + [skud("9", m, "a") for m in (10, 50, 80)]}}
POS = {"1": "defense", "2": "goalkeeper", "3": "striker", "4": "defense"}
FACIT = FA.point_kamp({"goals": {"h": "0", "a": "1"}}, KAMP, lambda pid, navn: POS[pid])


@test("facit: sejrsmaal af udeforsvarer = 7+25+10+10+175+40+50 = 317")
def _():
    assert FACIT["1"]["point"] == 317, FACIT["1"]["komp"]


@test("facit: hjemmekeeper med tre redninger i et 0-1-nederlag = 7-8-5-8+15 = 1")
def _():
    assert FACIT["2"]["point"] == 1, FACIT["2"]["komp"]


@test("facit: clean sheet kraever 60 minutter, og holdmaal kun mens spilleren er paa banen")
def _():
    assert FACIT["4"]["point"] == 42 and "clean sheet" not in FACIT["4"]["komp"], FACIT["4"]["komp"]
    assert FACIT["3"]["point"] == 42 and "holdmaal" not in FACIT["3"]["komp"], FACIT["3"]["komp"]


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
