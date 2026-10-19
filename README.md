<p align="center">
  <img src="docs/img/banner.svg" alt="holdet-premier-manager: forventet værdi pr. spiller og handler, der holder, selv hvis modellen tager fejl" width="100%">
</p>

<p align="center">
  <a href="https://github.com/anjo21ad/holdet-premier-manager/actions/workflows/test.yml"><img src="https://github.com/anjo21ad/holdet-premier-manager/actions/workflows/test.yml/badge.svg" alt="tests"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/afh%C3%A6ngigheder-ingen-2ea44f" alt="ingen afhængigheder">
  <a href="LICENSE"><img src="https://img.shields.io/badge/licens-MIT-blue" alt="MIT-licens"></a>
</p>

<h3 align="center">Hvem skal du købe, og hvem skal du sælge?</h3>

En model til Premier Manager på [holdet.dk](https://www.holdet.dk), udviklet og brugt runde for runde i Efterår 2026. Den giver hver spiller i spillet ét tal: hvor meget han forventes at stige i værdi resten af sæsonen. Og den giver en klar regel for, hvornår en handel er pengene værd.

Hver prognose skrives ned før deadline og måles bagefter mod det, der skete. Modellen ændres kun, når en ændring beviseligt giver bedre prognoser.

<p align="center"><img src="docs/img/testet.svg" alt="Bygget og testet i virkeligheden: cirka 590 spillere vurderes før hver deadline, 808 spiller-runder i backtest, 90-97 procent kroneeksakt pointberegning og seks kontroller pr. handel" width="100%"></p>

> [!TIP]
> **Oftest er svaret: behold dit hold.** En handel koster penge. Den skal bevise, at den er det værd, også hvis modellen tager fejl.

## Spillet på et halvt minut

<p align="center"><img src="docs/img/point-er-pris.svg" alt="Point er pris: scorer Bruno Fernandes det første mål i en 2-0-udesejr, stiger hans pris 262.000 kr." width="100%"></p>

Alt, hvad en spiller gør på banen, bliver til kroner på hans pris. Stiger dine spillere, stiger dit hold. Men hvert køb koster 1 % i gebyr, og penge, der står i spillere, giver ikke rente i banken. En handel skal altså tjene mere, end den koster.

## Den store fælde

<p align="center"><img src="docs/img/held-ligner-talent.svg" alt="Held ligner talent: 24 lige gode spillere spreder sig tilfældigt efter tre runder, og den, der ser bedst ud, har haft mest held" width="100%"></p>

Det er let at finde en spiller med flotte tal. Det svære er at vide, om tallene er ægte. Få kampe er for lidt til at skille talent fra held, og leder du blandt 600 spillere efter den, der ser bedst ud, finder du oftest den, der har været heldigst. Fænomenet har et navn: *optimizerens forbandelse* (Smith & Winkler 2006).

Modellen er bygget op omkring det problem. Den første udgave havde fem lag af håndlavede justeringer, og da otte forslag til handler blev efterprøvet, holdt ingen af dem. Derfor blev den bygget om fra bunden med få, gennemprøvede regler og en fast test af hver handel.

## Kuren: tro mest på det, der er set mange gange

<p align="center"><img src="docs/img/tro-paa-det-sete.svg" alt="Saka har 0,69 xG i år mod 0,35 før, og modellen siger 0,44. Palmer har 0,29 i år mod 0,45 før, og modellen siger 0,38" width="100%"></p>

Modellen vejer tre sæsoner sammen, så de nyeste kampe tæller mest, og trækker resultatet mod det typiske for spillerens rolle. Jo flere kampe en spiller har bag sig, desto mere vejer hans egne tal. Efter cirka 11 kampe vejer de mere end det typiske.

Saka og Palmer viser, hvorfor det betyder noget. En god eller dårlig start på sæsonen flytter vurderingen, men den overtager den ikke. Det er det, der skiller talent fra held. Princippet er det samme som i baseballmodellen Marcel og i Efron og Morris' klassiske arbejde om shrinkage.

## Hvad er en handel værd?

<p align="center"><img src="docs/img/handlens-vaerdi.svg" alt="Foden ud og Mbeumo ind: +645 i forventet vækst, minus 72 i gebyr og 114 i tabt rente, giver +458 tusind kroner" width="100%"></p>

En handel regnes over resten af sæsonen, ikke kun næste runde. Fra gevinsten trækkes gebyret og den rente, du går glip af, fordi pengene nu står i en spiller i stedet for i banken.

<details>
<summary><b>Sådan ser det ud i terminalen</b></summary>
<br>

Eksempelholdet i [`eksempler/hold.json`](eksempler/hold.json) før runde 8 i Efterår 2026:

```text
$ python handel.py "Phil Foden > Bryan Mbeumo"

Foden > Mbeumo
  basis +458   forskel -25 % +297   K/2 +466   2K +443   ind pS -0,1 +324   ud pS +0,1 +340
  -> ANBEFALES (positiv i 6 af 6; vaerst +297 tkr)

UD  Phil Foden (MCI, midfield/CM): g90 0.25  a90 0.25  pS naeste 0.37  pStart 0.38  ev_tot 387
      bygger paa 2814 vaegtede startminutter (prioren vejer 26 %): 2024 MCI 1639 min (xg90 0.33); 2025 MCI 1945 min (xg90 0.26); 2026 MCI 275 min (xg90 0.54)
      spilletid: RotoWire-status 0.37, startandel 0.4 over 15 klubkampe
      ! tynd: 275 startmin i aar
IND Bryan Mbeumo (MUN, midfield/AM): g90 0.40  a90 0.20  pS naeste 0.78  pStart 0.82  ev_tot 1032
      bygger paa 3771 vaegtede startminutter (prioren vejer 21 %): 2024 BRE 3419 min (xg90 0.36); 2025 MUN 2644 min (xg90 0.45); 2026 MUN 630 min (xg90 0.58)
      spilletid: RotoWire-status 0.78, startandel 0.87 over 15 klubkampe
      ! klubskifte: minutter fra anden klub vaegtet x0.5
```

Hver spiller kommer med en forklaring: hvor mange minutter tallet bygger på, hvor meget det typiske for rollen vejer, og hvad der bør undersøges, før tallet bruges. Foden har kun startet tre kampe i år, og hans startchance er lav. Mbeumo bygger på tre fulde sæsoner.

</details>

## Seks spørgsmål før hver handel

<p align="center"><img src="docs/img/seks-spoergsmaal.svg" alt="Seks spørgsmål: Foden til Mbeumo holder i alle seks og anbefales. Rice til Rogers er positiv i basis, men fejler tre af de seks" width="100%"></p>

Målingerne viser, hvor en model som denne typisk tager fejl. Forskellen mellem spillere er lidt mindre i virkeligheden, end prognoserne siger. Tilliden til en spillers egne tal kan være sat for højt eller for lavt. Og spilletid er det sværeste at forudsige. Derfor spørger modellen seks gange, om handlen stadig er god, hvis netop den fejl er sket. Ét nej, og du beholder dit hold.

## Sådan virker det

<p align="center"><img src="docs/img/saadan-virker-det.svg" alt="Fra data til beslutning: holdet.dk, understat, Betfair Match Odds og RotoWire går ind i modellen, derefter kvalitetstjek, seks spørgsmål og beslutning" width="100%"></p>

| Kilde | Hvad den bidrager med |
|---|---|
| **holdet.dk** | Priser, klubber og kampprogram |
| **understat** | Minutter, xG og xA fra hver kamp i tre sæsoner |
| **Betfair** | Match Odds: hvad markedet tror om hver kamp |
| **RotoWire** | Forventede startopstillinger til næste runde |

Før hver deadline tjekker modellen sine egne data. Er en fil forældet, eller har en kilde svaret med noget forkert, stopper den i stedet for at regne videre på forkerte tal. Efter hver runde sammenlignes prognoserne med det, der skete.

<details>
<summary><b>For de nysgerrige: de tre regler og formlen</b></summary>
<br>

| | Regel | Hvad den gør |
|---|---|---|
| 1 | **Rate (Marcel)** | xG og xA pr. 90 minutter fra **starter** i tre sæsoner, vægtet 1,0 / 0,8 / 0,6. Minutter i en anden klub tæller halvt. Raten trækkes mod medianen for spillerens rolle med 1.000 minutters vægt |
| 2 | **Spilletid** | Næste runde fra RotoWire. Resten af sæsonen er ½ status + ½ startandel i klubbens seneste 15 kampe |
| 3 | **Holdstyrke** | Udgangspunkt før sæsonen, opdateret med de målforventninger, der passer til Betfairs priser |
| | **Pointformel** | Spillets regler i `ev_kamp()`. `evaluer()` er det eneste sted, forventningen beregnes |

```
g90 = (Σ v · xG · 90 + K · typisk_for_rollen) / (Σ v · minutter + K)        K = 1.000 minutter
```

De seks kontroller i `handel.py`: basis, forskellen −25 %, K/2, 2K, nye spillere −0,1 i spilletid og gamle spillere +0,1 i spilletid. En spiller, hvis tal er mere end 50 % gæt, anbefales aldrig uden et menneskes vurdering.

Hele begrundelsen med kilder står i [docs/metode.md](docs/metode.md).

</details>

## Virker det?

<p align="center"><img src="docs/img/virker-det.svg" alt="For spillere med under 5 kampes data var den første models hældning 0,34 og denne models 0,96. Over 15 kampe 1,16 mod 0,95" width="100%"></p>

Alle prognoser skrives ned før runden og kan ikke rettes bagefter. Efter runden måles det, hvor meget af forskellen mellem spillerne der holdt. For spillere med få kampe var den første models forskelle mest held. Den nuværende model rammer næsten præcist, og den samlede fejl faldt med 7 % (MSE 3.504 mod 3.258).

Pointberegningen bag målingen rammer holdets egne tal kroneeksakt for 90-97 % af spillerne. Spillere med 5-15 kampe bag sig er den gruppe, der følges tættest fra runde til runde.

## Prøv det selv

Du skal bruge Python 3.10 eller nyere. Andet kræves ikke.

```bash
git clone https://github.com/anjo21ad/holdet-premier-manager.git
cd holdet-premier-manager
cp eksempler/hold.json eksempler/manager_input.json .    # ret hold.json til dit eget hold

python hent.py holdet                       # priser, klubber og kampprogram
python hent.py liga && python hent.py liga 2025
python hent.py rotowire 8                   # højst 24 timer før deadline
python hent.py betfair 8                    # kræver miljøvariablen BETFAIR_AK

python model.py 8                           # første gang hentes spillerhistorik (~5 min)
python facit_alle.py                        # faktiske point hidtil
python kvalitet.py --runde 8                # STOP betyder: ingen beslutning på disse data
python handel.py --skan "Phil Foden"        # de bedste afløsere, vurderet i alle seks spørgsmål
```

Testene kører uden data: `python test_model.py`. Hele rytmen før deadline og efter hver runde står i [docs/arbejdsgang.md](docs/arbejdsgang.md).

<details>
<summary><b>Hvad ligger hvor</b></summary>
<br>

| | |
|---|---|
| `hent.py` | Henter fra holdet.dk, understat, Betfair og RotoWire |
| `model.py` | De tre regler og pointformlen. Skriver `input/board.json` |
| `handel.py` | Seks spørgsmål pr. handel, `--skan` efter afløsere og `--log` til en beslutningslog |
| `kvalitet.py` | Tjekker data før en beslutning og stopper ved fejl |
| `praeregistrer.py` | Låser alle prognoser før deadline. Nægter at overskrive |
| `facit_alle.py` | Regner de faktiske point ud for alle spillere |
| `kalibrering_alle.py` | Måler prognoserne mod facit |
| `test_model.py` | Tests på opdigtede spillere og kampe |
| `docs/` | [Metode](docs/metode.md), [pointsystem](docs/pointsystem.md) og [arbejdsgang](docs/arbejdsgang.md) |
| `eksempler/` | Skabeloner til `hold.json` og `manager_input.json` |

</details>

## Kendte forenklinger

- Bygget til **Premier Manager Efterår 2026**. Til et nyt spil skal spil-id, sæsoner og udgangspunktet for holdene rettes ([se hvordan](docs/arbejdsgang.md#en-ny-sæson)).
- Straffespark ligger i xG. En spiller, der lige har overtaget straffesparkene, er undervurderet.
- Nye spillere i en klub får deres spilletid fra få kampe.
- Betfair prissætter næste runde. De senere runder regnes på holdstyrken.

## Data og vilkår

Repoet indeholder **ingen data**. Scriptsene henter fra holdet.dk, understat, Betfair og RotoWire til din egen maskine, og mapperne med data deles aldrig. Du er selv ansvarlig for at bruge kilderne efter deres vilkår.

Projektet er ikke tilknyttet holdet.dk, understat, Betfair eller RotoWire.

## Licens

[MIT](LICENSE)
