# Metode

Her står, hvorfor modellen ser ud, som den gør, hvad tallene bygger på, og hvordan den er blevet målt. Hvordan den køres, står i [arbejdsgang.md](arbejdsgang.md).

## Hvorfor modellen har få regler

Den første udgave af projektet havde fem håndtunede lag oven på hinanden: tier-blandinger, karrierelapper, manuelle startchancer og en holdet-fil, der var blevet forældet. Da otte handelsforslag blev efterprøvet, faldt alle otte. Hver fejl sad i ét lag, og rettelserne nåede aldrig de andre.

Mønstret har et navn: **optimizerens forbandelse** (Smith & Winkler 2006). Når du leder blandt 600 spillere efter den højeste forventning, finder du systematisk dem, hvor støjen tilfældigvis trækker estimatet op. Jo flere estimater og jo mere støj, desto større skuffelse. Kuren er ikke flere lag, men **shrinkage**: et estimat, der hviler på lidt data, trækkes mod det typiske, indtil der er data nok til at tro på det.

Derfor blev hele kæden erstattet af én fil med tre regler, hver begrundet i forskning og målt i backtest. Baseballmodellen Marcel bygger på samme princip og præsterer på niveau med langt mere komplekse projektionssystemer. Få regler er et bevidst valg, og backtesten bakker det op.

**Kompleksitetsbudget:** ingen ny parameter, kilde eller lag uden en målt forbedring i backtest på mindst to runder.

## De tre regler

### 1. Rate (Marcel)

```
g90 = (Σ v · xG · 90 + K · prior_rolle) / (Σ v · minutter + K)
```

- Kun **starter** tæller. Indskiftninger mod trætte forsvar giver en skæv rate.
- **v** = 1,0 / 0,8 / 0,6 for indeværende og de to forrige sæsoner (Marcels 5/4/3).
- Minutter for **en anden klub** tæller halvt. xG pr. 90 minutter persisterer omkring 0,6 fra sæson til sæson, men kun omkring 0,4 efter et klubskifte.
- **K = 1.000 minutter**, omtrent 11 kampe. Under ti kampe er xG for ustabilt til at stå alene.
- **Prioren** er medianen for spillerens rolle (CB, FB, CM, AM, FW), udledt af data hver gang modellen kører. Rollen er den position, spilleren har startet flest minutter på.
- Samme regel giver a90 med xA.

En spiller med 500 vægtede minutter hviler altså 2/3 på prioren. Det er meningen.

### 2. Spilletid

| | Kilde |
|---|---|
| Næste runde | RotoWire: XI 0,92 · XI og tvivlsom 0,70 · tvivlsom 0,25 · ude 0,02 · ellers 0,14 |
| Resten af sæsonen | ½ status + ½ startandel i klubbens seneste 15 kampe med spilleren i klubben |

Uden RotoWire for en klub bruges startandelen, trukket mod 0,14 med to kampe. Under 5 kampe for klubben bruges kun status.

### 3. Holdstyrke

Hver klub starter med en preseason-tier for angreb og forsvar, som vejer som 4 runders markedsdata. For hver runde, hvor Betfair-priserne er gemt, findes de to Poisson-λ, der netop rammer markedets P(hjemmesejr) og P(ikke begge scorer) (`loes()`). Klubbens angrebs- og forsvarsfaktor opdateres med dem.

Markedet justerer selv for modstander, hjemmebane, skader og keepere. Derfor er der ingen håndlavede lag for de ting.

### Pointformlen

`ev_kamp()` oversætter spillets regler ([pointsystem.md](pointsystem.md)) til en forventning pr. kamp: mål efter position, assists, skud på mål, sejr og uafgjort fra Poisson-fordelingen, holdmål og modstandermål ud fra λ, clean sheet som e<sup>−λ<sub>imod</sub></sup>, redninger og gule kort. `evaluer()` er det eneste sted, EV beregnes. Også handelsreglen kalder den, så der findes ingen parallel beregning, der kan glide fra.

```
ev_tot = ev_neste + (runder tilbage) · ev_rest
```

## Beslutningsreglen

Shrinkagen er kuren mod optimizerens forbandelse. `handel.py` spørger kun, om en handel også holder, hvis modellen tager fejl på de måder, vi ved den kan. Gevinsten regnes over resten af sæsonen, **netto af gebyr (1 %) og bankrente (1 % pr. runde)**, og skal være positiv i alle seks:

| Kontrol | Hvad den tester | Hvorfor |
|---|---|---|
| basis | modellen som den er | |
| forskel −25 % | forskellen mellem spillerne er overvurderet | kalibreringen har målt β omkring 0,75-0,8 |
| K/2 | mere tillid til spillernes egne data | K er et skøn |
| 2K | mere tillid til rolleprioren | K er et skøn |
| ind pS −0,1 | de nye spiller mindre end ventet | spilletid er det sværeste at forudsige |
| ud pS +0,1 | de gamle spiller mere end ventet | samme |

Derudover:

- **Standard er ingen handel.** En positiv basis er ikke nok.
- En spiller, hvis rate hviler over 50 % på prioren, anbefales aldrig uden et menneskes vurdering. Modellen kender ham ikke.
- Alle spillere i begge hold regnes efter samme kontrol. Gevinsten ved A → B er præcis minus gevinsten ved B → A.

## Tests før en konklusion

Regler, som koden ikke selv håndhæver:

- **Koncentrationstesten.** Stammer over ~70 % af en spillers xG eller xA fra én hændelse, er tallet en begivenhed og ikke en rolle. Modellen flager det over 40 %.
- **Proces mod udfald.** Faktiske point minus modellens forventning. Et stort positivt gab er en regressionsfælde. Et stort negativt gab kan betyde, at spilleren er underbetalt.
- **Nedsiden regnes med exit-muligheden.** Du holder aldrig en brudt spiller sæsonen ud. Et scenarie, hvor spilleren beholdes til udløb, overvurderer risikoen, og jo billigere spilleren er, desto mere.
- **Regn altid netto af kapitalomkostningen.** En opgradering, der binder 1M ekstra i 13 runder, koster 130.000 i tabt rente.
- **En skadet spiller regnes med genkøb.** En midlertidig afløser og et genkøb koster to gebyrer, men brudpunktet er typisk omkring to runder. Hold banken klar til genkøbet.

## Evidens

Facit kommer fra understat og er valideret mod holdets egne point: 90-97 % af spillerne rammes kroneeksakt i de første tre runder.

**Kalibrering af den første, lagdelte model** (prognoser efter R3 mod realiserede point i R4-R5, 808 spiller-runder):

| Evidens bag prognosen | β |
|---|---|
| ≥ 15 hele kampe | 1,16 |
| 5-15 | 0,64 |
| < 5 | **0,34**: prognosens forskelle var mest støj |

**Backtest af den nuværende model** på samme spillere og runder:

| | MSE | β alle | β < 5 | β 5-15 | β ≥ 15 |
|---|---:|---:|---:|---:|---:|
| Første model | 3.504 | 0,77 | 0,34 | 0,64 | 1,16 |
| Nuværende, uden RotoWire og Betfair for runden | 3.506 | 0,87 | **0,96** | 0,32 | 1,05 |
| Nuværende, fuld | **3.258** | 0,83 | **0,96** | 0,31 | 0,95 |

Shrinkagen gjorde det, den skulle: spillere med tynd evidens er nu kalibreret (β 0,96 mod 0,34).

**Vagtpunktet** er spillere med 5-15 kampes evidens (β omkring 0,3), også i den første runde uden for stikprøven. Gruppen følges runde for runde, og der ændres først noget, når der er tre runders evidens.

**Afvist efter kompleksitetsbudgettet,** fordi de ikke gav en målbar forskel: en prisprior pr. rolle og prisinterval samt spilletidsvinduer på 5, 8 og 10 kampe (Brier 0,207-0,209).

**Taget ind,** fordi det var en fejl og ikke en tuning: startandel som reserve, når RotoWire mangler for en klub (Brier fra 0,209 til 0,178).

## Metoderegler for skøn

1. **Ex ante.** Begrund og præregistrér før runden (`praeregistrer.py`). Et tal uden mekanisme bag er ikke evidens.
2. **Regelkarantæne.** Ingen permanent regel eller parameter på under 3 runders evidens.
3. **Proces er ikke udfald.** En beslutning med positiv forventning, der tabte, var stadig rigtig. Afvigelser deles i varians, som ikke ændrer modellen, og bias, som gør.
4. **To uafhængige kilder pr. tvivlsom starter.** RotoWire skelner mellem forudsagt og bekræftet opstilling.
5. **En stime er proces.** Den måles i xG, skud og minutter, aldrig i mål. Et salg udløses aldrig af stimen selv, kun af et alternativ, der klarer de seks kontroller.
6. **Skan afløsere for skadede og udgåede spillere.** Det er ofte dér, de robuste handler ligger.
7. **Metoden ændres aldrig efter at have set svaret** på den aktuelle beslutning (Gelmans "forking paths"). Modellen fryses 24 timer før deadline. Derefter kommer kun nye data ind.

## Kendte forenklinger og næste skridt

- **Straffe** ligger i xG. En spiller, der har overtaget straffesparkene, er undervurderet, og en, der har mistet dem, er overvurderet. Næste skridt er npxG + holdets straffefrekvens × spillerens andel.
- **Spilletid for nye klubspillere** afhænger meget af én RotoWire-status, når de har under 5 kampe for klubben. Kandidaten er en shrinkage af startandelen mod status.
- **Klubskifte** halverer i dag vægten af gamle minutter, men sænker ikke niveauet. Data tyder på, at (npxG+xA)/90 falder ~15 % sæsonen efter et skifte.
- **Bankrenten** regnes lineært. Ved store kontantbeholdninger er renters rente værd at regne med.
- **Betfair** prissætter kun én runde pålideligt frem. Resten af sæsonen regnes på holdstyrken.

Hver ændring tages kun ind, hvis den forbedrer kalibreringen på mindst to runder.

## Kilder

- Smith & Winkler (2006), [*The Optimizer's Curse*](https://www.gwern.net/doc/statistics/decision/2006-smith.pdf): udvælgelse efter estimeret værdi skuffer systematisk.
- Michaud (1989), [*The Markowitz Optimization Enigma*](https://math.mit.edu/amc/2007fa/Michaud.pdf): optimeringer er "estimation-error maximizers".
- [Marcel](https://www.baseball-reference.com/about/marcels.shtml) og [en sammenligning med komplekse systemer](https://www.beyondtheboxscore.com/2016/1/14/10733872/steamer-zips-pecota-marcel-projections-review).
- Efron & Morris (1975), [*Data Analysis Using Stein's Estimator*](https://www.medicine.mcgill.ca/epidemiology/hanley/bios602/MultilevelData/EfronMorrisJASA1975.pdf): regression mod middelværdien.
- Dawes (1979), [*The Robust Beauty of Improper Linear Models*](https://www.cmu.edu/dietrich/sds/docs/dawes/the-robust-beauty-of-improper-linear-models-in-decision-making.pdf): simple modeller holder.
- [FPL Review om xG-præcision](https://docs.fplreview.com/articles/xg-accuracy/) og [Evidently om xG-persistens](https://evidently.substack.com/p/how-can-we-tell-if-a-footballer-will): fem kampe er for lidt, og xG/90 persisterer ~0,6 (0,4 ved klubskifte).
- Federal Reserve, [SR 11-7](https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm): modelrisiko, outcomes analysis og effective challenge.
