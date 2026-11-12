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
g90 = (Σ v · npxG · 90 + K · prior_rolle) / (Σ v · minutter + K) + straffeled
```

- **Data:** starter, minutter, xG og xA pr. kamp fra FotMob, i Premier League og de fire andre store ligaer (Ligue 1, Bundesliga, Serie A og La Liga). Straffe skilles fra med skudkortet.
- Kun **starter** tæller. Indskiftninger mod trætte forsvar giver en skæv rate.
- **v** = 1,0 / 0,8 / 0,6 for indeværende og de to forrige sæsoner (Marcels 5/4/3).
- Minutter for **en anden klub** tæller halvt. xG pr. 90 minutter persisterer omkring 0,6 fra sæson til sæson, men kun omkring 0,4 efter et klubskifte.
- **K = 1.000 minutter**, omtrent 11 kampe. Under ti kampe er xG for ustabilt til at stå alene.
- **Prioren** er medianen for spillerens rolle (CB, FB, CM, AM, FW), udledt af data hver gang modellen kører. Rollen er den position, spilleren har startet flest minutter på.
- **Straffe** er et separat led. Raten bygger på xG uden straffe (npxG), og bagefter lægges ligaens straffe-xG pr. holdkamp (0,093) gange spillerens andel af klubbens straffe-xG i sidste og denne sæson til.
- Samme regel giver a90 med xA, uden straffeled.

En spiller med 500 vægtede minutter hviler altså 2/3 på prioren. Det er meningen.

### 2. Spilletid

| | Kilde |
|---|---|
| Næste runde | RotoWire: XI 0,92 · XI og tvivlsom 0,70 · tvivlsom 0,25 · ude 0,02 · ellers 0,14 |
| Resten af sæsonen | ½ status + ½ startandel i klubbens seneste 15 kampe med spilleren i klubben, trukket mod status med 3 kampe |

Uden RotoWire for en klub bruges startandelen, trukket mod 0,14 med to kampe. Startandelen trækkes altid mod status med tre kampes vægt, så en spiller med få kampe for klubben ikke længere springer fra kun status til fuld startandel ved den femte kamp.

### 3. Holdstyrke

Hver klub starter med en preseason-tier for angreb og forsvar, som vejer som 4 runders markedsdata. For hver runde, hvor oddsene er gemt, findes de to Poisson-λ, der rammer markedets P(hjemmesejr) og P(over 2,5 mål) (`loes()`): totalen afhænger kun af summen af λ'erne og findes af P(over 2,5), og P(hjemmesejr) fordeler den. Oddsene for næste runde kommer fra Pinnacle, og for spillede runder fra football-data.co.uk's arkiv (gennemsnit før kampen). Klubbens angrebs- og forsvarsfaktor opdateres med dem.

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

Facit er holdet.dk's egne prisændringer: point er pris, så det er præcist. For runde 1-5, hvor der ikke findes priser fra hver runde, er point regnet ud fra kampdata med spillets regler; hvor det kan kontrolleres, rammer det holdets egne tal på kronen for 90-97 % af spillerne.

**Backtest på runde 4-10.** Hver runde er regnet med de data, modellen ville have haft før deadline: kampe, odds og opstillinger fra før deadline (`kalibrering_alle.py --backtest`, 3.551 spiller-runder):

| | n | MSE | β (SE) |
|---|---:|---:|---:|
| Alle | 3.551 | 2.794 | **0,94** (0,04) |
| Under 5 kampes evidens | 1.182 | 1.015 | 1,00 (0,08) |
| 5-15 kampe | 768 | 2.781 | **0,62** (0,09) |
| Over 15 kampe | 1.601 | 4.113 | 0,94 (0,06) |

Top-testen pr. runde: de 5 % højest rangerede leverede 111 % af det lovede, top 10 % 103 % og top 25 % 99 %. Samlet ligger hældningen inden for de 25 %, som kontrollen "forskel −25 %" dækker. Pr. runde svinger den fra 0,43 (R5) til 1,17 (R7), så den læses samlet og med standardfejl.

**Præregistrerede runder.** Prognoserne låses med `praeregistrer.py` før hver deadline og måles mod facit med `kalibrering_alle.py`, efterhånden som runderne bliver spillet.

**Handler væk fra raske startere** leverer kun omkring halvdelen. I en backtest på R4-R8 leverede handler, der holdt i alle seks kontroller, 50 % af det forudsagte, når den solgte spiller var en rask starter, og 93 %, når han var usikker. Det er ikke gjort til en regel, men en handel væk fra en rask starter skal have god margin.

**Vagtpunktet** er spillere med 5-15 kampes evidens: β 0,62, så forskellene i den gruppe er ca. 1,6 gange så store, som de burde være. Kontrollen "forskel −25 %" dækker kun en del af det. Gruppen følges runde for runde, og der ændres først noget, når der er tre runders evidens.

**Afvist efter kompleksitetsbudgettet,** fordi de ikke gav en målbar forskel: en prisprior pr. rolle og prisinterval samt spilletidsvinduer på 5, 8 og 10 kampe (Brier 0,207-0,209).

**Taget ind,** fordi det var en fejl og ikke en tuning: startandel som reserve, når RotoWire mangler for en klub (Brier fra 0,209 til 0,178).

**Taget ind efter backtest på R4-R8:** straffe som et separat led (fejlen faldt i fire af fem runder og var uændret i den femte) og startandelen trukket mod status med tre kampe (Brier for starter 0,1924 → 0,1894, og 0,2256 → 0,2150 for spillere med under 5 klubkampe). Ingen af dem tilføjer en ny parameter: straffefrekvensen og andelene udledes af data, og de tre kampe er den samme shrinkage som for minutter pr. start.

## Metoderegler for skøn

1. **Ex ante.** Begrund og præregistrér før runden (`praeregistrer.py`). Et tal uden mekanisme bag er ikke evidens.
2. **Regelkarantæne.** Ingen permanent regel eller parameter på under 3 runders evidens.
3. **Proces er ikke udfald.** En beslutning med positiv forventning, der tabte, var stadig rigtig. Afvigelser deles i varians, som ikke ændrer modellen, og bias, som gør.
4. **To uafhængige kilder pr. tvivlsom starter.** RotoWire skelner mellem forudsagt og bekræftet opstilling.
5. **En stime er proces.** Den måles i xG, skud og minutter, aldrig i mål. Et salg udløses aldrig af stimen selv, kun af et alternativ, der klarer de seks kontroller.
6. **Skan afløsere for skadede og udgåede spillere.** Det er ofte dér, de robuste handler ligger.
7. **Metoden ændres aldrig efter at have set svaret** på den aktuelle beslutning (Gelmans "forking paths"). Modellen fryses 24 timer før deadline. Derefter kommer kun nye data ind.

## Kendte forenklinger og næste skridt

- **Straffeandelen** er bagudskuende. Den kender ikke et nyt førstevalg, før han har taget straffe, så en handel, der afhænger af en straffeskytte, regnes også med de kendte skytter.
- **Spilletid for faste startere** er for høj: spillere i RotoWires XI fik pStart 0,85 for resten af sæsonen, men startede 74 % af de følgende runder (R6-R8).
- **Udelukkelser og gule kort** ligger ikke i modellen. En karantæne regnes ved siden af, som en spiller, der giver 0 i de runder, han mangler.
- **Kaptajnbonussen** er mindst 0, fordi et fald ikke trækkes fra. Modellen regner kaptajnens forventning uden den bund, så den er lidt for lav.
- **Klubskifte** halverer i dag vægten af gamle minutter, men sænker ikke niveauet. Data tyder på, at (npxG+xA)/90 falder ~15 % sæsonen efter et skifte.
- **Bankrenten** regnes lineært. Ved store kontantbeholdninger er renters rente værd at regne med.
- **Oddsene** prissætter kun én runde pålideligt frem. Resten af sæsonen regnes på holdstyrken.
- **Spillere fra andre ligaer** end de fem store hviler på rolleprioren.

Hver ændring tages kun ind, hvis den forbedrer kalibreringen på mindst to runder.

## Kilder

- Smith & Winkler (2006), [*The Optimizer's Curse*](https://www.gwern.net/doc/statistics/decision/2006-smith.pdf): udvælgelse efter estimeret værdi skuffer systematisk.
- Michaud (1989), [*The Markowitz Optimization Enigma*](https://math.mit.edu/amc/2007fa/Michaud.pdf): optimeringer er "estimation-error maximizers".
- [Marcel](https://www.baseball-reference.com/about/marcels.shtml) og [en sammenligning med komplekse systemer](https://www.beyondtheboxscore.com/2016/1/14/10733872/steamer-zips-pecota-marcel-projections-review).
- Efron & Morris (1975), [*Data Analysis Using Stein's Estimator*](https://www.medicine.mcgill.ca/epidemiology/hanley/bios602/MultilevelData/EfronMorrisJASA1975.pdf): regression mod middelværdien.
- Dawes (1979), [*The Robust Beauty of Improper Linear Models*](https://www.cmu.edu/dietrich/sds/docs/dawes/the-robust-beauty-of-improper-linear-models-in-decision-making.pdf): simple modeller holder.
- [FPL Review om xG-præcision](https://docs.fplreview.com/articles/xg-accuracy/) og [Evidently om xG-persistens](https://evidently.substack.com/p/how-can-we-tell-if-a-footballer-will): fem kampe er for lidt, og xG/90 persisterer ~0,6 (0,4 ved klubskifte).
- Federal Reserve, [SR 11-7](https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm): modelrisiko, outcomes analysis og effective challenge.
