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

I Premier Manager på [holdet.dk](https://www.holdet.dk) handler det om at få dit hold til at stige i værdi. Projektet giver hver spiller ét tal: hvor meget han forventes at stige resten af sæsonen. Og det giver en klar regel for, hvornår en handel er pengene værd.

> [!TIP]
> **Oftest er svaret: behold dit hold.** En handel koster penge. Den skal bevise, at den er det værd, også hvis modellen tager fejl.

&nbsp;

## Spillet på et halvt minut

<p align="center"><img src="docs/img/point-er-pris.svg" alt="Point er pris: en midtbanespiller, der scorer det første mål i en 2-0-udesejr, stiger 262.000 kr. i værdi" width="100%"></p>

Alt, hvad en spiller gør på banen, bliver til kroner på hans pris. Stiger dine spillere, stiger dit hold. Men hvert køb koster 1 % i gebyr, og penge, der står i spillere, giver ikke rente i banken. En handel skal altså tjene mere, end den koster.

## Den store fælde

<p align="center"><img src="docs/img/held-ligner-talent.svg" alt="Held ligner talent: 24 lige gode spillere spreder sig tilfældigt efter tre runder, og den, der ser bedst ud, har haft mest held" width="100%"></p>

Det er let at finde en spiller med flotte tal. Det svære er at vide, om tallene er ægte. Tre kampe er for lidt til at skille talent fra held, og leder du blandt 600 spillere efter den, der ser bedst ud, finder du næsten altid den, der har været heldigst. Fænomenet har et navn: *optimizerens forbandelse*.

Projektets første udgave faldt selv i fælden. Den havde fem lag af håndlavede justeringer, og da otte forslag til handler blev efterprøvet, holdt ingen af dem.

## Kuren: tro mest på det, der er set mange gange

<p align="center"><img src="docs/img/tro-paa-det-sete.svg" alt="Spiller A med 3 kampe og 0,80 xG får budet 0,35. Spiller B med 3 sæsoner og 0,45 xG får budet 0,39" width="100%"></p>

Modellen blander spillerens egne tal med det typiske for hans rolle. Har han spillet få kampe, vejer det typiske mest. Har han spillet mange, vejer hans egne tal mest. Grænsen går ved cirka 11 kampe.

Det lyder banalt, men det er netop det, der skiller en model, der jagter held, fra en, der finder talent.

## Hvad er en handel værd?

<p align="center"><img src="docs/img/handlens-vaerdi.svg" alt="Clarke ud og Neto ind: +620 i forventet vækst, minus 48 i gebyr og 62 i tabt rente, giver +510 tusind kroner" width="100%"></p>

En handel regnes over resten af sæsonen, ikke kun næste runde. Fra gevinsten trækkes gebyret og den rente, du går glip af, fordi pengene nu står i en spiller i stedet for i banken.

<details>
<summary><b>Sådan ser det ud i terminalen</b></summary>
<br>

Eksempelholdet i [`eksempler/hold.json`](eksempler/hold.json) før runde 8 i Efterår 2026:

```text
$ python handel.py "Jack Clarke > Pedro Neto"

Clarke > Neto
  basis +510   forskel -25 % +355   K/2 +520   2K +503   ind pS -0,1 +407   ud pS +0,1 +451
  -> ANBEFALES (positiv i 6 af 6; vaerst +355 tkr)

UD  Jack Clarke (IPS, midfield/AM): g90 0.18  a90 0.17  pS naeste 0.25  pStart 0.27  ev_tot 92
      bygger paa 631 vaegtede startminutter (prioren vejer 61 %): 2024 IPS 827 min (xg90 0.09); 2026 IPS 135 min (xg90 0.1)
      spilletid: RotoWire-status 0.25, startandel 0.29 over 7 klubkampe
      ! tynd: 135 startmin i aar
IND Pedro Neto (CHE, midfield/AM): g90 0.20  a90 0.23  pS naeste 0.72  pStart 0.76  ev_tot 712
      bygger paa 3708 vaegtede startminutter (prioren vejer 21 %): 2024 CHE 2000 min (xg90 0.17); 2025 CHE 2502 min (xg90 0.17); 2026 CHE 506 min (xg90 0.35)
      spilletid: RotoWire-status 0.72, startandel 0.8 over 15 klubkampe
```

Hver spiller kommer med en forklaring: hvor mange minutter tallet bygger på, og hvor meget det typiske for rollen vejer. Clarkes tal er 61 % gæt, Netos kun 21 %.

</details>

## Seks spørgsmål før hver handel

<p align="center"><img src="docs/img/seks-spoergsmaal.svg" alt="Seks spørgsmål: Clarke til Neto holder i alle seks og anbefales. Clarke til Rudoni holder også, men Rudonis tal er 73 procent gæt" width="100%"></p>

Ingen model er perfekt, og vi ved, hvor denne typisk tager fejl. Den overvurderer forskellen mellem spillere en smule. Den kan stole for meget eller for lidt på en spillers egne tal. Og spilletid er svær at forudsige. Derfor spørger den seks gange, om handlen stadig er god, hvis netop den fejl er sket. Ét nej, og du beholder dit hold.

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

Alle prognoser skrives ned før runden og kan ikke rettes bagefter. Efter runden måles det, hvor meget af forskellen mellem spillerne der holdt. For spillere med få kampe var den første models forskelle mest held. Den nye model rammer næsten præcist.

Det svage punkt er spillere med 5-15 kampe bag sig. Det følges runde for runde, og modellen ændres kun, hvis en ændring beviseligt hjælper. Pointberegningen bag målingen rammer holdets egne tal kroneeksakt for 90-97 % af spillerne.

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
python facit_alle.py                        # realiserede point hidtil
python kvalitet.py --runde 8                # STOP betyder: ingen beslutning på disse data
python handel.py --skan "Jack Clarke"       # de bedste afløsere, vurderet i alle seks spørgsmål
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

## Begrænsninger

- Bygget til **Premier Manager Efterår 2026**. Til et nyt spil skal spil-id, sæsoner og udgangspunktet for holdene rettes ([se hvordan](docs/arbejdsgang.md#en-ny-sæson)).
- Straffespark ligger i xG. En spiller, der lige har overtaget straffesparkene, er undervurderet.
- Nye spillere i en klub får deres spilletid fra meget få kampe.
- Betfair prissætter kun næste runde pålideligt. Resten af sæsonen regnes på holdstyrken.

## Data og vilkår

Repoet indeholder **ingen data**. Scriptsene henter fra holdet.dk, understat, Betfair og RotoWire til din egen maskine, og mapperne med data deles aldrig. Du er selv ansvarlig for at bruge kilderne efter deres vilkår.

Projektet er ikke tilknyttet holdet.dk, understat, Betfair eller RotoWire.

## Licens

[MIT](LICENSE)
