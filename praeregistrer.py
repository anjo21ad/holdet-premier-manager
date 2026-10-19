# -*- coding: utf-8 -*-
"""PRAEREGISTRERING: ex ante-snapshot af HELE boardet foer deadline (Tetlock; SR 11-7 'outcomes analysis').

Uden en forudsigelse skrevet ned foer udfaldet kan modellen aldrig kalibreres. Snapshottet gemmer alle
spilleres rundeprognose, ikke kun dit eget hold, saa kalibreringen faar ~300 datapunkter pr. runde.

Brug:  python praeregistrer.py <runde>[-<maerke>]      fx "7", eller "7-lor" efter sidste RotoWire-opdatering
Skriver exante/r<runde>[-<maerke>].json. Overskriver ALDRIG - en praeregistrering, der kan rettes
bagefter, er ingen praeregistrering. Et maerke kan ogsaa bruges til en modelvariant, fx "7-straffe",
som kalibrering_alle.py derefter maaler side om side med hovedmodellen.
"""
import hashlib, io, json, os, sys
from datetime import datetime
import model as M

VAULT = os.path.dirname(os.path.abspath(__file__))
FELTER = ["name", "club", "pos", "price", "us_id", "rolle", "g90", "a90", "pS_neste", "pStart", "bt", "f60",
          "ev_neste", "ev_rest", "ev_tot"]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    etiket = sys.argv[1]
    runde = int(etiket.split("-")[0])
    ud = os.path.join(VAULT, "exante", "r%s.json" % etiket)
    if os.path.exists(ud):
        sys.exit("STOP: %s findes allerede - praeregistreringer overskrives ikke" % ud)
    board, meta = M.byg(runde)
    fn = os.path.join(VAULT, "hold.json")
    hold = json.load(io.open(fn, encoding="utf-8")) if os.path.exists(fn) else {}
    kilder = [f for f in os.listdir(M.SP) if f.startswith(("rw-r%d." % runde, "bf-r%d-" % runde, "us-league-2026", meta["holdet_fil"]))]
    m = {"runde": runde, "etiket": etiket, "tidspunkt": datetime.now().isoformat(timespec="seconds"), "model": "model.py",
         "model_sha": hashlib.sha256(open(M.__file__, "rb").read()).hexdigest()[:16],
         "kilder": {f: datetime.fromtimestamp(os.path.getmtime(os.path.join(M.SP, f))).isoformat(timespec="minutes") for f in sorted(kilder)},
         "enhed": "tkr (point = prisdelta/1000)", "hold": hold.get("hold"), "kaptajn": hold.get("kaptajn"),
         "markedsrunder": meta["marked_runder"], "matchet": meta["matchet"], "holdet_fil": meta["holdet_fil"]}
    rows = []
    for r in board:
        x = {k: r.get(k) for k in FELTER}
        x["evidens_min"] = r["forklaring"]["vaegtede_min"]
        x["flag"] = r["forklaring"]["flag"]
        rows.append(x)
    os.makedirs(os.path.dirname(ud), exist_ok=True)
    json.dump({"meta": m, "spillere": rows}, io.open(ud, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("skrevet %s: %d spillere, model %s" % (ud, len(rows), m["model_sha"]))


if __name__ == "__main__":
    main()
