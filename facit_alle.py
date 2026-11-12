# -*- coding: utf-8 -*-
"""FACIT FOR ALLE SPILLERE - fra holdets egne priser: point = prisdelta.

Hvorfor: kalibrering kraever realiserede point for HELE puljen, ikke kun dit eget hold. I spillet er point og
prisaendring det samme, saa holdets priser er facit paa kronen.

En runde faar facit, naar der findes et holdet-snapshot efter runden og et efter forrige runde (for R1:
startprisen). Et snapshot hoerer til runden, hvis filnavnets dato ligger fra rundens slut til foer naeste
rundes deadline; ligger der flere, bruges det seneste. Hent derfor holdet efter hver runde (hent.py holdet).
Runder uden snapshots paa begge sider faar intet facit, medmindre de ligger i den valgfrie fil
facit/ekstra.json ({runde: {holdet-personId: point}}).

Brug:  python facit_alle.py            skriver facit/holdet.json: {runde: {holdet-personId: point}} og kilden pr. runde
"""
import glob, io, json, os

VAULT = os.path.dirname(os.path.abspath(__file__))
SP = os.path.join(VAULT, "input")


def snapshots():
    """{dato 'YYYY-MM-DD': (filnavn, {personId: pris})} for alle holdet-filer."""
    ud = {}
    for f in glob.glob(os.path.join(SP, "holdet-[0-9][0-9][0-9][0-9].json")):
        fn = os.path.basename(f)
        dd, mm = int(fn[7:9]), int(fn[9:11])
        d = json.load(io.open(f, encoding="utf-8"))
        ud["%d-%02d-%02d" % (2026 if mm >= 7 else 2027, mm, dd)] = (fn, {str(it["personId"]): it["price"] for it in d["items"]},
                                                                     {str(it["personId"]): it["startPrice"] for it in d["items"]})
    return ud


def byg():
    d = json.load(io.open(os.path.join(SP, "holdet-pl-schedule.json"), encoding="utf-8"))
    slut = {i + 1: x["end"][:10] for i, x in enumerate(d["rounds"])}
    deadline = {i + 1: x["close"][:10] for i, x in enumerate(d["rounds"])}
    snap = snapshots()
    efter = {}   # runde -> (filnavn, priser): seneste snapshot fra rundens slut til foer naeste deadline
    for r in slut:
        kand = [dt for dt in snap if dt >= slut[r] and (r + 1 not in deadline or dt < deadline[r + 1])]
        if kand:
            efter[r] = snap[max(kand)]
    fn = os.path.join(VAULT, "facit", "ekstra.json")
    kd = json.load(io.open(fn, encoding="utf-8"))["runder"] if os.path.exists(fn) else {}
    runder, kilde = {}, {}
    for r in sorted(slut):
        if r in efter and (r - 1 in efter or r == 1):
            fn1, p1, start = efter[r]
            fn0, p0 = (efter[r - 1][0], efter[r - 1][1]) if r > 1 else ("startpris", start)
            runder[str(r)] = {pid: round((p1[pid] - p0[pid]) / 1000) for pid in p1 if pid in p0}
            kilde[str(r)] = "holdet %s -> %s" % (fn0, fn1)
        elif str(r) in kd:
            runder[str(r)], kilde[str(r)] = kd[str(r)], "facit/ekstra.json"
    ud = {"_doc": "Point pr. runde og holdet-personId. Kilden pr. runde staar i 'kilde'.", "kilde": kilde, "runder": runder}
    os.makedirs(os.path.join(VAULT, "facit"), exist_ok=True)
    json.dump(ud, io.open(os.path.join(VAULT, "facit", "holdet.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return ud


if __name__ == "__main__":
    ud = byg()
    for r, k in ud["kilde"].items():
        print("R%s: %4d spillere  %s" % (r, len(ud["runder"][r]), k))
    print("skrevet facit/holdet.json")
