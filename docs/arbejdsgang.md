# Arbejdsgang

Alle scripts køres fra roden af repoet og bruger kun Pythons standardbibliotek. Data havner i `input/`, præregistreringer i `exante/` og facit i `facit/`. Alle tre er gitignoreret.

## Første gang

```bash
cp eksempler/hold.json eksempler/manager_input.json .     # ret hold.json til dit eget hold
python hent.py holdet                                     # priser, klubber og kampplan
python hent.py liga && python hent.py liga 2025           # understat, i år og sidste sæson
python model.py 8                                         # henter spillerhistorik første gang (~5 min)
python facit_alle.py                                      # realiserede point for alle spillere hidtil
python test_model.py                                      # tests uden data
```

Første kørsel af `model.py` henter understats spillerfiler, én pr. spiller med en halv sekunds pause, og kampfilerne for sæsonen. Bagefter ligger det hele i `input/`.

## Før hver deadline

1. **Hent data**
   ```bash
   python hent.py holdet          # når priserne har flyttet sig, altså efter hver runde
   python hent.py liga
   python hent.py betfair 8       # kræver BETFAIR_AK, se nedenfor
   python hent.py rotowire 8      # højst 24 timer før deadline
   ```
2. **Kør modellen og portene**
   ```bash
   python model.py 8
   python kvalitet.py --runde 8   # deadline læses fra holdets kampplan; stop ved STOP
   ```
3. **Præregistrér**, før du ser på handler: `python praeregistrer.py 8`. Filen kan ikke overskrives. Henter du RotoWire igen tæt på deadline, så præregistrér med et mærke, fx `8-lor`.
4. **Vurdér handler**
   ```bash
   python handel.py --skan "Phil Foden"                         # de 15 bedste afløsere i alle seks kontroller
   python handel.py "Phil Foden > Bryan Mbeumo"                 # én handel
   python handel.py "A > B" "C > D"                             # en pakke
   python handel.py "A > B" --log "største risiko: ..."         # skriv til beslutningslog.csv
   ```
   Skan alle 11 pladser, også de skadede og udgåede spillere. Læs forklaringen for ind- og ud-spillere: hvor mange minutter raten bygger på, hvor meget prioren vejer, og hvilke flag der er sat.
5. **Modelfrys 24 timer før deadline.** Derefter kommer kun nye data ind, ingen ændringer i modellen.

## Efter hver runde

```bash
python hent.py holdet && python hent.py liga
python facit_alle.py          # realiserede point fra understat
python kalibrering_alle.py    # β, MSE og top-test pr. præregistrering
```

Opdatér derefter `hold.json` med runde, hold, gebyrfri spillere og kapital fra appen. Skriv udfaldet i beslutningsloggen.

## Dine egne filer

| Fil | Indhold |
|---|---|
| `hold.json` | Næste beslutningsrunde, dine 11, de gebyrfri spillere, kapital (holdværdi ved vinduets start + bank, i mio.) og kaptajn |
| `manager_input.json` | Det eneste sted, dit skøn går ind i modellen: `pStart` og/eller `rolle`, med en grund og en udløbsdato. Hold det under ~5 poster |
| `beslutningslog.csv` | Alle vurderede handler med de seks kontroller og den største risiko. Oprettes ved første `--log` |
| `point-historik.json` | Valgfri. Holdets egne point pr. spiller og runde, så `facit_alle.py` kan validere sig selv |

## Datakilderne og deres fælder

| Kilde | Rolle |
|---|---|
| **holdet.dk** | Pris, klub, position og kampplan. Eneste autoritet på klubtilhør, også når spillets univers afviger fra virkeligheden |
| **understat** | Starter, minutter, xG, xA, roller og facit |
| **Betfair** | Holdstyrke fra Match Odds og "begge hold scorer" |
| **RotoWire** | Forventede opstillinger og skader til næste runde |

Fælderne er tavse. De giver ikke en fejl, bare forkerte tal. Derfor er de gjort til porte i `hent.py` og `kvalitet.py`:

- **understat** kræver headeren `X-Requested-With: XMLHttpRequest`. Uden den svarer serveren 404-HTML på 461 bytes, og en løkke skriver tomme filer uden at klage.
- **holdet.dk** svarer 200 med en HTML-skal på forkerte stier. En forældet holdet-fil giver forkerte klubber og priser. `kvalitet.py` stopper, hvis priserne ikke stemmer med startpris + facit-point.
- **Betfair** skal hentes på engelsk (`locale=en`), og markedstypen skal stå i søgningens hovedfilter. Ellers kommer der Match Odds i filen for "begge hold scorer", og runden falder stille ud af holdstyrken. Betfair prissætter reelt kun én runde pålideligt frem.
- **RotoWire** skifter fra forudsagt til bekræftet opstilling omkring en time før kampstart. Hent højst 24 timer før deadline.

### Betfair-nøglen

Betfairs offentlige web-endpoints kræver en app-nøgle (`_ak`), den samme som betfair.com's egen side bruger. Repoet indeholder ingen nøgle. Sæt den som miljøvariabel:

```bash
export BETFAIR_AK=...            # bash
$env:BETFAIR_AK = "..."          # PowerShell
```

## En ny sæson

Modellen er bygget til Premier Manager Efterår 2026. Til et nyt spil skal du rette:

- `GAME_ID` i `hent.py`
- sæsonerne i `V_SAESON` og `liga_2026()` i `model.py`
- preseason-tiers i `TIER` og klubkoderne i `H2F`, `UK` og `KLUBBER`, hvis ligaen har nye hold
- `MAKS_ALDER` i `kvalitet.py`, hvis ligafilens navn ændres
