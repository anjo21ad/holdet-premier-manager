# CLAUDE.md: arbejdsregler for dette repo

Repoet er beslutningsgrundlag for handler i holdet.dk's Premier Manager. Svar på dansk.

## Målet

Målfunktionen er **total forventet vækst i holdets værdi**, netto af gebyr (1 %) og bankrente (1 % pr. runde). Det er ikke EV pr. mio., og der tages ingen hensyn til ejerandele eller differentialer. Risiko modelleres i spilletid (pS), ikke i spredning.

## Sådan skal der argumenteres

Regn efter, vis mellemregningen, og sig det, hvis et forslag ikke holder. Når en anbefaling omgøres, skal fejlen navngives. Faste tests før en konklusion:

- **Koncentrationstesten.** Stammer over ~70 % af en spillers xG eller xA fra én hændelse, er tallet en begivenhed og ikke en rolle.
- **Proces mod udfald.** Faktiske point minus modellens forventning. Stort positivt gab er en regressionsfælde.
- **Nedsiden regnes med exit-muligheden.** En brudt spiller holdes aldrig sæsonen ud.
- **Regn altid netto af kapitalomkostningen.**
- **Se, hvad et tal er målt under**, før det bruges til en handel: vægtede minutter, prior-vægt, status, startandel og flag.

## Modellen

Se [docs/metode.md](docs/metode.md). Kort: Marcel-rate på xG uden straffe med K = 1.000 minutter plus et separat straffeled, spilletid fra RotoWire og startandel trukket mod status med tre kampe, holdstyrke fra Betfair. `evaluer()` er det eneste sted, EV beregnes. Dit eget skøn går kun ind via `manager_input.json`.

**Kompleksitetsbudget:** ingen ny parameter, kilde eller lag uden målt forbedring i kalibreringen på mindst 2 runder (præregistrér varianten med et mærke og kør `kalibrering_alle.py`).

## Beslutningsregel

- En handel anbefales kun, hvis gevinsten er positiv i alle seks kontroller i `handel.py`. **Standard er ingen handel.**
- Spillere, hvis rate hviler over 50 % på prioren, anbefales aldrig uden et menneskes vurdering.
- Skan også afløsere for skadede og udgåede spillere, og regn en skadet spiller med genkøb, ikke kun permanent salg.
- Modelfrys 24 timer før deadline. Derefter kun nye data.
- `kvalitet.py` skal stå uden STOP, før der træffes en beslutning.

## Data

**Status november 2026:** understat er nede, og Betfair lukker for danske kunder 18/11. Erstatningerne (Pinnacle, FotMob, FPL) er testet, men ikke bygget ind; se [docs/metode.md](docs/metode.md#datakilderne-i-november-2026). Indtil da stopper `kvalitet.py` på understat, og en beslutning kræver et tjek af, hvad de manglende runder ændrer.

holdet.dk er eneste autoritet på pris, klub og position, også når spillets univers afviger fra virkeligheden. Ret aldrig en klub ud fra generel viden. Data må ikke committes: `input/`, `exante/` og `facit/` er gitignoreret og skal blive det.

Arbejdsgang og datafælder: [docs/arbejdsgang.md](docs/arbejdsgang.md). `python test_model.py` skal stå uden FAIL.
