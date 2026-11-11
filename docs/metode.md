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

- Kun **starter** tæller. Indskiftninger mod trætte forsvar giver en skæv rate.
- **v** = 1,0 / 0,8 / 0,6 for indeværende og de to forrige sæsoner (Marcels 5/4/3).
- Minutter for **en anden klub** tæller halvt. xG pr. 90 minutter persisterer omkring 0,6 fra sæson til sæson, men kun omkring 0,4 efter et klubskifte.
- **K = 1.000 minutter**, omtrent 11 kampe. Under ti kampe er xG for ustabilt til at stå alene.
- **Prioren** er medianen for spillerens rolle (CB, FB, CM, AM, FW), udledt af data hver gang modellen kører. Rollen er den position, spilleren har startet flest minutter på.
- **Straffe** er et separat led. Raten bygger på xG uden straffe (npxG), og bagefter lægges ligaens straffe-xG pr. holdkamp (0,079) gange spillerens andel af klubbens straffe-xG i sidste og denne sæson til.
- Samme regel giver a90 med xA, uden straffeled.

En spiller med 500 vægtede minutter hviler altså 2/3 på prioren. Det er meningen.

### 2. Spilletid

| | Kilde |
|---|---|
| Næste runde | RotoWire: XI 0,92 · XI og tvivlsom 0,70 · tvivlsom 0,25 · ude 0,02 · ellers 0,14 |
| Resten af sæsonen | ½ status + ½ startandel i klubbens seneste 15 kampe med spilleren i klubben, trukket mod status med 3 kampe |

Uden RotoWire for en klub bruges startandelen, trukket mod 0,14 med to kampe. Startandelen trækkes altid mod status med tre kampes vægt, så en spiller med få kampe for klubben ikke længere springer fra kun status til fuld startandel ved den femte kamp.

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

## Datakilderne i november 2026

To af de fire kilder svigter:

- **understat** har været nede siden 2. november og svarer kun med en vedligeholdelsesside.
- **Betfair** lukker for danske kunder 18. november. Om de offentlige priser stadig kan hentes fra en dansk IP bagefter, er uvist.

Erstatningerne er testet mod de gamle kilder, men endnu ikke bygget ind:

| Kilde | Erstatter | Testet |
|---|---|---|
| Pinnacle (åbent guest-API) | Betfair: 1X2, totaler og holdtotaler | 1X2 for runde 11 lå i gennemsnit 0,5 procentpoint fra Betfair, højst 1,3, over ni kampe |
| FotMob | understat: skudkort med xG og situation pr. skud, opstillinger | Skudniveauet gør det muligt at skille straffe fra og køre koncentrationstesten som før |
| FPL (officielt API) | understat: xG, xA, minutter og starter pr. kamp | Korrelation 0,977 med understats xG i runde 1-8 over 183 spillere. FPL bruger Opta-skalaen, som ligger lavere: xG skal ganges med 1,107 og xA med 1,27 |
| holdet.dk | understat som facit | Point er prisændring, så holdets egne priser er facit |

En ny kilde er også en ny parameter, så den følger kompleksitetsbudgettet: den tages først ind, når backtesten på runde 4-8 ikke bliver dårligere med den. Indtil da regnes runderne på understat-data til og med runde 8. Runde 9 og frem lægges ind fra FPL som et tjek ved siden af modellen, og `kvalitet.py` stopper med vilje.

Tjekket 11. november: en fuld optimering med og uden runde 9-10 fra FPL gav samme konklusion, ingen robust handel, og flyttede spillernes forventning med højst ca. 40.000 kr.

## Evidens

Facit kommer fra understat og er valideret mod holdets egne point: 90-97 % af spillerne rammes kroneeksakt i de første tre runder. Mens understat er nede, er facit holdets egne prisændringer.

**Backtest på R4-R5.** Den første, lagdelte models prognoser efter R3 mod realiserede point i R4-R5, og den nuværende model regnet bagefter på de samme 824 spiller-runder (`kalibrering_alle.py --sammenlign`, genberegnet 23/10 på det opdaterede facit):

| | MSE | β alle | β < 5 | β 5-15 | β ≥ 15 | top 5 % leveret |
|---|---:|---:|---:|---:|---:|---:|
| Første model | 3.436 | 0,78 | **0,37** | 0,64 | 1,16 | 97 % |
| Nuværende, uden RotoWire og Betfair for runden | 3.439 | 0,88 | 0,99 | 0,32 | 1,05 | 98 % |
| Nuværende, fuld | **3.200** | 0,84 | 0,95 | 0,31 | 0,95 | 89 % |

I den første model var forskellene for spillere med under 5 kampe mest støj (β 0,37). Shrinkagen rettede det i backtesten. Den samlede fejl faldt 7 %, og hele faldet kom fra RotoWire og Betfair for runden.

**Præregistrerede runder.** Den nuværende models prognoser låst med `praeregistrer.py` før deadline (`exante/r6-ny2.json`, `exante/r7.json`). Modellen blev rettet én gang mellem de to runder.

| | n | β alle | β < 5 | β 5-15 | β ≥ 15 | top 5 % leveret |
|---|---:|---:|---:|---:|---:|---:|
| R6 | 472 | 0,74 | 1,28 | 0,31 | 0,81 | 72 % |
| R7 | 472 | 1,03 | 0,36 | 0,94 | 1,08 | 100 % |
| R6 og R7 samlet | 944 | **0,90** (SE 0,07) | 0,85 (0,18) | **0,62** (0,16) | 0,96 (0,09) | 86 % |

Samlet ligger hældningen inden for de 25 %, som kontrollen "forskel −25 %" dækker. De enkelte evidensgrupper svinger meget fra runde til runde, så de læses samlet og med standardfejl.

**Senere runder.** R8 (`exante/r8.json`, 472 spiller-runder) gav β 0,66 (SE 0,08), og de 5 % højest rangerede leverede kun 57 % af det lovede. R9 blev ikke præregistreret. R10 (`exante/r10.json`, 477 spiller-runder) gav β 0,84 (SE 0,09), og toppen leverede 112 %. R10 er målt mod holdets egne prisændringer og regnet på understat-data til og med R8, fordi understat var nede.

**Handler væk fra raske startere** leverer kun omkring halvdelen. I en backtest på R4-R8 leverede handler, der holdt i alle seks kontroller, 50 % af det forudsagte, når den solgte spiller var en rask starter, og 93 %, når han var usikker. Det er ikke gjort til en regel, men en handel væk fra en rask starter skal have god margin.

**Vagtpunktet** er spillere med 5-15 kampes evidens: β 0,31 i backtesten og 0,62 samlet uden for stikprøven. Gruppen følges runde for runde, og der ændres først noget, når der er tre runders evidens.

**Afvist efter kompleksitetsbudgettet,** fordi de ikke gav en målbar forskel: en prisprior pr. rolle og prisinterval samt spilletidsvinduer på 5, 8 og 10 kampe (Brier 0,207-0,209).

**Taget ind,** fordi det var en fejl og ikke en tuning: startandel som reserve, når RotoWire mangler for en klub (Brier fra 0,209 til 0,178).

**Taget ind 26/10 efter backtest på R4-R8** (`kalibrering_alle.py --backtest`, 2.385 spiller-runder):

| | MSE | β (SE) | β 5-15 | top 5 % leveret |
|---|---:|---:|---:|---:|
| Før | 3.148 | 0,83 (0,04) | 0,61 | 84 % |
| Med straffe som separat led | **3.140** | **0,85** (0,04) | 0,62 | **89 %** |

Straffeleddet var bedre i fire af fem runder og uændret i R4. Startandelen trukket mod status med tre kampe gav Brier 0,1924 → 0,1894 for starter i R6-R8 og 0,2256 → 0,2150 for spillere med under 5 klubkampe. Ingen af rettelserne tilføjer en ny parameter: straffefrekvensen og andelene udledes af data, og de tre kampe er den samme shrinkage som for minutter pr. start.

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
- **Betfair** prissætter kun én runde pålideligt frem. Resten af sæsonen regnes på holdstyrken. Betfair lukker for danske kunder 18. november 2026, se [Datakilderne i november 2026](#datakilderne-i-november-2026).

Hver ændring tages kun ind, hvis den forbedrer kalibreringen på mindst to runder.

## Kilder

- Smith & Winkler (2006), [*The Optimizer's Curse*](https://www.gwern.net/doc/statistics/decision/2006-smith.pdf): udvælgelse efter estimeret værdi skuffer systematisk.
- Michaud (1989), [*The Markowitz Optimization Enigma*](https://math.mit.edu/amc/2007fa/Michaud.pdf): optimeringer er "estimation-error maximizers".
- [Marcel](https://www.baseball-reference.com/about/marcels.shtml) og [en sammenligning med komplekse systemer](https://www.beyondtheboxscore.com/2016/1/14/10733872/steamer-zips-pecota-marcel-projections-review).
- Efron & Morris (1975), [*Data Analysis Using Stein's Estimator*](https://www.medicine.mcgill.ca/epidemiology/hanley/bios602/MultilevelData/EfronMorrisJASA1975.pdf): regression mod middelværdien.
- Dawes (1979), [*The Robust Beauty of Improper Linear Models*](https://www.cmu.edu/dietrich/sds/docs/dawes/the-robust-beauty-of-improper-linear-models-in-decision-making.pdf): simple modeller holder.
- [FPL Review om xG-præcision](https://docs.fplreview.com/articles/xg-accuracy/) og [Evidently om xG-persistens](https://evidently.substack.com/p/how-can-we-tell-if-a-footballer-will): fem kampe er for lidt, og xG/90 persisterer ~0,6 (0,4 ved klubskifte).
- Federal Reserve, [SR 11-7](https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm): modelrisiko, outcomes analysis og effective challenge.
