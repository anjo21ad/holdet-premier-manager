# Arbejdsgang

Alle scripts køres fra roden af repoet og bruger kun Pythons standardbibliotek. Data havner i `input/`, præregistreringer i `exante/` og facit i `facit/`. Alle tre er gitignoreret.

## Første gang

```bash
cp eksempler/hold.json eksempler/manager_input.json .     # ret hold.json til dit eget hold
python hent.py holdet                                     # priser, klubber, kampplan og resultater
python hent.py fotmob historik                            # 2024-2025 i PL og de fire andre store ligaer (~3.500 kampe, ca. 45 min)
python hent.py fotmob                                     # årets PL-kampe
python hent.py odds historik 10                           # odds for de spillede runder 1-10
python test_model.py                                      # tests uden data
```

Historikken hentes én gang og ligger derefter i `input/` som en kompakt fil pr. kamp. `hent.py fotmob` henter kun de kampe, der er kommet til siden sidst.

## Før hver deadline

1. **Hent data**
   ```bash
   python hent.py fotmob          # årets kampe, inklusive seneste runde
   python hent.py odds 11         # Pinnacle, højst 48 timer før deadline
   python hent.py rotowire 11     # højst 24 timer før deadline
   ```
2. **Kør modellen og portene**
   ```bash
   python model.py 11
   python kvalitet.py --runde 11  # deadline læses fra holdets kampplan; stop ved STOP
   ```
3. **Præregistrér**, før du ser på handler: `python praeregistrer.py 11`. Filen kan ikke overskrives. Henter du RotoWire igen tæt på deadline, så præregistrér med et mærke, fx `11-lor`.
4. **Vurdér handler**
   ```bash
   python handel.py --skan "Ezri Konsa"                         # de 15 bedste afløsere i alle seks kontroller
   python handel.py "Igor Thiago > Liam Delap"                  # én handel
   python handel.py "A > B" "C > D"                             # en pakke
   python handel.py "A > B" --log "største risiko: ..."         # skriv til beslutningslog.csv
   ```
   Skan alle 11 pladser, også de skadede og udgåede spillere. Læs forklaringen for ind- og ud-spillere: hvor mange minutter raten bygger på, hvor meget prioren vejer, og hvilke flag der er sat.
5. **Modelfrys 24 timer før deadline.** Derefter kommer kun nye data ind, ingen ændringer i modellen.

## Efter hver runde

```bash
python hent.py holdet         # priserne efter runden: de er facit
python facit_alle.py          # point for alle spillere = prisændringen siden sidste runde
python kalibrering_alle.py    # β, MSE og top-test pr. præregistrering
```

Facit kræver et holdet-snapshot efter hver runde. Glemmer du en runde, kan den ikke regnes bagefter. Opdatér derefter `hold.json` med runde, hold, gebyrfri spillere og kapital fra appen, og skriv udfaldet i beslutningsloggen.

## Dine egne filer

| Fil | Indhold |
|---|---|
| `hold.json` | Næste beslutningsrunde, dine 11, de gebyrfri spillere, kapital (dine spilleres værdi + bank efter gebyrer, i mio.) og kaptajn |
| `manager_input.json` | Det eneste sted, dit skøn går ind i modellen: `pStart` og/eller `rolle`, med en grund og en udløbsdato. Hold det under ~5 poster |
| `beslutningslog.csv` | Alle vurderede handler med de seks kontroller og den største risiko. Oprettes ved første `--log` |
| `facit/ekstra.json` | Valgfri. Facit for runder, hvor du ikke har et holdet-snapshot: `{"runder": {"<runde>": {"<personId>": <point>}}}` |

## Datakilderne og deres fælder

| Kilde | Rolle |
|---|---|
| **holdet.dk** | Pris, klub, position, kampplan og facit. Eneste autoritet på klubtilhør, også når spillets univers afviger fra virkeligheden |
| **FotMob** | Starter, minutter, xG, xA, positioner og skud (med situation, så straffe kan skilles fra) |
| **Pinnacle** | Odds på næste runde: resultat og over/under 2,5 mål. Spillede runder fra football-data.co.uk |
| **RotoWire** | Forventede opstillinger og skader til næste runde |

Fælderne er tavse. De giver ikke en fejl, bare forkerte tal. Derfor er de gjort til porte i `hent.py` og `kvalitet.py`:

- **holdet.dk** har sit API under `/api/fantasy/`. Forkerte stier giver 200 eller 404 med en HTML-skal. En forældet holdet-fil giver forkerte klubber og priser, så `kvalitet.py` stopper, hvis filen er hentet før seneste runde sluttede.
- **FotMob** er et uofficielt API, der kan ændre sig. `hent.py` stopper, hvis svaret ikke er JSON, eller en kamp ikke har 22 startere og spillerstatistik. `kvalitet.py` stopper, hvis en spillet kamp mangler i cachen. Positionskoderne (`positionId`) oversættes til roller i `model.fm_pos`.
- **Pinnacle** svares fra et åbent guest-API. Modellen bruger moneyline og linjen 2,5 mål, som også findes, når hovedlinjen er en anden. `kvalitet.py` stopper, hvis en af rundens kampe mangler, eller sandsynlighederne er uplausible. Oddsene prissætter kun næste runde; resten af sæsonen regnes på holdstyrken.
- **RotoWire** skifter fra forudsagt til bekræftet opstilling omkring en time før kampstart. Hent højst 24 timer før deadline.

## En ny sæson

Modellen er bygget til Premier Manager Efterår 2026. Til et nyt spil skal du rette:

- `GAME_ID` i `hent.py`
- sæsonerne: `FM_SAESON` i `hent.py`, `V_SAESON` og sæsonerne `"2024"`-`"2026"` i `model.py` og football-data-sæsonen i `odds_historik()`
- preseason-tiers i `TIER` og klubkoderne i `H2F`, `UK`, `KODE` og `KLUBBER`, hvis ligaen har nye hold
