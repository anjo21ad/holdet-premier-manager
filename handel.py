# -*- coding: utf-8 -*-
"""HANDEL: seks kontroller pr. handel. Standard = ingen handel.

Bayesiansk shrinkage i model.py er selve kuren mod optimizerens forbandelse (Smith & Winkler 2006).
Kontrollerne her spoerger kun, om handlen ogsaa holder, hvis modellen tager fejl paa de maader,
vi ved den kan tage fejl. Handlen anbefales kun, hvis gevinsten er positiv i ALLE seks:
  1 basis
  2 forskel -25 %   brutto-forskellen i EV x 0,75 (gebyr og rente uaendret) - kalibreringen maalte beta ~0,75
  3 K/2             mere tillid til spillernes egne data
  4 2K              mere tillid til rolleprioren
  5 ind pS -0,1     ind-spillerne spiller mindre end ventet
  6 ud pS +0,1      ud-spillerne spiller mere end ventet
Gevinst = tkr over resten af saesonen, netto af gebyr (1 %) og bankrente (10 tkr/M/runde). Holdet og
kapitalen laeses fra hold.json. Forklaringen for hver spiller er modellens egen (ingen parallel beregning).

Brug:  python handel.py "Ud > Ind" ["Ud2 > Ind2" ...]     vurder en handel eller pakke
       python handel.py --skan "Spiller"                 de bedste afloesere for en spiller
       ... --log "stoerste risiko: ..."                  skriv vurderingen til beslutningslog.csv
"""
import copy, csv, io, json, os, sys
from datetime import date
import model as M

VAULT = os.path.dirname(os.path.abspath(__file__))
LOG_FELTER = ["dato", "runde", "status", "handel", "ud", "ind", "basis", "vaerst", "bedst", "positive", "robust",
              "begrundelse", "stoerste_risiko", "udfald"]
FORM_OK = {(3, 4, 3), (3, 5, 2), (4, 3, 3), (4, 4, 2), (4, 5, 1), (5, 3, 2), (5, 4, 1)}
BETA = 0.75
MAKS_PRIOR = 0.5     # en ind-spiller, hvis rate hviler > 50 % paa prioren, kan aldrig anbefales uden manager-vurdering
KONTROLLER = [("basis", None, 1.0, 0.0, 0.0), ("forskel -25 %", None, BETA, 0.0, 0.0), ("K/2", M.K / 2, 1.0, 0.0, 0.0),
              ("2K", 2 * M.K, 1.0, 0.0, 0.0), ("ind pS -0,1", None, 1.0, -0.1, 0.0), ("ud pS +0,1", None, 1.0, 0.0, 0.1)]


def last():
    fn = os.path.join(VAULT, "hold.json")
    if not os.path.exists(fn):
        sys.exit("hold.json mangler - kopier eksempler/hold.json hertil og indsaet dit eget hold")
    info = json.load(io.open(fn, encoding="utf-8"))
    board, meta = M.byg(info["runde"])
    return {M.norm(r["name"]): r for r in board}, meta["ctx"], info


def find(B, navn):
    k = M.norm(navn)
    if k in B:
        return B[k]["name"]
    kand = [r["name"] for kk, r in B.items() if kk.split()[-1] == k.split()[-1] or k in kk]
    if len(kand) != 1:
        sys.exit("'%s' er ikke entydig: %s" % (navn, kand[:6] or "ingen"))
    return kand[0]


def variant(r, ctx, k, dps):
    x = copy.copy(r)
    if k is not None:
        f = x["forklaring"]
        x["g90"], x["a90"] = M.rate(f["sum_xg"], f["n"], f["prior"][0], k), M.rate(f["sum_xa"], f["n"], f["prior"][1], k)
    if dps:
        x["pS_neste"] = min(1.0, max(0.0, x["pS_neste"] + dps))
        x["pStart"] = min(1.0, max(0.0, x["pStart"] + dps))
    return M.evaluer(x, ctx) if (k is not None or dps) else x


def gevinst(B, ctx, info, ud, ind, kontrol):
    """(gevinst, '') eller (None, grund). Alle spillere i begge hold regnes efter samme kontrol (symmetri)."""
    _, k, beta, d_ind, d_ud = kontrol
    cur = [variant(B[M.norm(n)], ctx, k, d_ud if n in ud else 0.0) for n in info["hold"]]
    alt = [x for x in cur if x["name"] not in ud] + [variant(B[M.norm(n)], ctx, k, d_ind) for n in ind]
    nposs = {p: sum(1 for x in alt if x["pos"] == p) for p in ("goalkeeper", "defense", "midfield", "striker")}
    if nposs["goalkeeper"] != 1 or (nposs["defense"], nposs["midfield"], nposs["striker"]) not in FORM_OK:
        return None, "ugyldig formation"
    if max(sum(1 for x in alt if x["club"] == c) for c in {x["club"] for x in alt}) > 4:
        return None, "over 4 fra samme klub"
    def penge(h):
        geb = 0.01 * sum(x["price"] for x in h if x["name"] not in info["gebyrfri"])
        bank = info["kapital"] - sum(x["price"] for x in h) - geb
        return bank, bank * 10 * (ctx["rest"] + 1) - geb * 1000
    def ev(h):
        return sum(x["ev_tot"] for x in h) + sum(x["ev_tot"] for x in h if x["name"] == info["kaptajn"])
    bank_alt, p_alt = penge(alt)
    if bank_alt < -1e-9:
        return None, "budget: bank %.0fk efter handlen" % (1000 * bank_alt)
    return beta * (ev(alt) - ev(cur)) + p_alt - penge(cur)[1], ""


def vurder(B, ctx, info, ud, ind):
    res = [gevinst(B, ctx, info, ud, ind, k) for k in KONTROLLER]
    if res[0][0] is None:
        return {"ugyldig": res[0][1]}
    v = [x for x, _ in res]
    prior_spillere = [n for n in ind if B[M.norm(n)]["forklaring"]["vaegt_paa_prior"] > MAKS_PRIOR]
    return {"vaerdier": v, "basis": v[0], "vaerst": min(v), "antal_pos": sum(1 for x in v if x > 0),
            "prior_spillere": prior_spillere, "robust": all(x > 0 for x in v) and not prior_spillere}


def forklar(r):
    f = r["forklaring"]
    s = "; ".join("%s %d min (xg90 %s)" % (k, v["startmin"], v["xg90"]) for k, v in f["saesoner"].items())
    L = ["  %s (%s, %s/%s): g90 %.2f  a90 %.2f  pS naeste %.2f  pStart %.2f  ev_tot %.0f" % (
        r["name"], r["club"], r["pos"], r["rolle"], r["g90"], r["a90"], r["pS_neste"], r["pStart"], r["ev_tot"]),
         "      bygger paa %d vaegtede startminutter (prioren vejer %.0f %%): %s" % (f["vaegtede_min"], 100 * f["vaegt_paa_prior"], s or "ingen starter"),
         "      spilletid: RotoWire-status %.2f, startandel %s over %d klubkampe" % (f["status"], f["startandel"], f["klubkampe"])]
    L += ["      ! " + x for x in f["flag"]]
    return "\n".join(L)


def log(handel, ud, ind, v, risiko, runde):
    """Tilfoej en raekke til beslutningslog.csv (oprettes ved foerste brug). Status og udfald udfyldes i haanden."""
    fn = os.path.join(VAULT, "beslutningslog.csv")
    x = {k: "" for k in LOG_FELTER}
    x.update({"dato": date.today().isoformat(), "runde": runde, "status": "vurderet", "handel": handel,
              "ud": " + ".join(ud), "ind": " + ".join(ind), "stoerste_risiko": risiko})
    if "ugyldig" in v:
        x["begrundelse"] = "Ugyldig: " + v["ugyldig"]
    else:
        x.update({"basis": round(v["basis"]), "vaerst": round(v["vaerst"]), "bedst": round(max(v["vaerdier"])),
                  "positive": "%d/6" % v["antal_pos"], "robust": v["robust"],
                  "begrundelse": ", ".join("%s %+.0f" % (k[0], w) for k, w in zip(KONTROLLER, v["vaerdier"]))})
    ny = not os.path.exists(fn)
    with io.open(fn, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FELTER)
        if ny:
            w.writeheader()
        w.writerow(x)


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    risiko = None
    if "--log" in a:
        i = a.index("--log"); risiko = a[i + 1]; a = a[:i] + a[i + 2:]
    B, ctx, info = last()
    info["hold"] = [find(B, n) for n in info["hold"]]
    print("hold R%d: %s\n" % (info["runde"], ", ".join(n.split()[-1] for n in info["hold"])))
    if a and a[0] == "--skan":
        ud = find(B, a[1])
        r0 = B[M.norm(ud)]
        kand = [r for r in B.values() if r["pos"] == r0["pos"] and r["name"] not in info["hold"] and r["pS_neste"] >= 0.5]
        basis = sorted(((gevinst(B, ctx, info, [ud], [r["name"]], KONTROLLER[0])[0], r["name"]) for r in kand),
                       key=lambda t: -(t[0] if t[0] is not None else -1e9))[:15]
        res = [(n, vurder(B, ctx, info, [ud], [n])) for g, n in basis if g is not None]
        print("SKANNING: %s -> %d kandidater (%s, pS naeste >= 0,5); de 15 bedste paa basis vurderet i alle seks:" % (ud, len(kand), r0["pos"]))
        for n, v in res:
            print("  %-28s basis %+6.0f  vaerst %+6.0f  positiv %d/6  %s" % (n, v["basis"], v["vaerst"], v["antal_pos"],
                  "ROBUST" if v["robust"] else ("PRIOR-SPILLER: kraever manager-vurdering" if v["prior_spillere"] else "")))
        if not res:
            print("  ingen gyldige afloesere (budget, formation eller klubloft)")
        if res and not any(v["robust"] for _, v in res):
            print("  -> ingen afloeser klarer alle seks kontroller: behold %s" % ud)
        print("\n" + forklar(r0))
        return
    par = [tuple(find(B, y.strip()) for y in x.split(">")) for x in a]
    ud, ind = [u for u, _ in par], [i for _, i in par]
    navn = ", ".join("%s > %s" % (u.split()[-1], i.split()[-1]) for u, i in par)
    v = vurder(B, ctx, info, ud, ind)
    if "ugyldig" in v:
        print("%s: UGYLDIG (%s)" % (navn, v["ugyldig"]))
    else:
        print("%s\n  %s\n  -> %s (positiv i %d af 6; vaerst %+.0f tkr)\n" % (
            navn, "   ".join("%s %+.0f" % (k[0], w) for k, w in zip(KONTROLLER, v["vaerdier"])),
            "ANBEFALES" if v["robust"] else "anbefales IKKE", v["antal_pos"], v["vaerst"]))
        if v["prior_spillere"]:
            print("  !! %s: raten hviler over %.0f %% paa prioren - modellen kender ikke spilleren. Kraever manager-vurdering." % (
                ", ".join(v["prior_spillere"]), 100 * MAKS_PRIOR))
    for n in ud + ind:
        print(("UD " if n in ud else "IND") + forklar(B[M.norm(n)])[1:])
    if risiko is not None:
        log(navn, ud, ind, v, risiko, info["runde"])
        print("\nlogget i beslutningslog.csv")


if __name__ == "__main__":
    main()
