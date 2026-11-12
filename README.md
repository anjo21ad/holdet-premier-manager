<p align="center">
  <img src="docs/img/banner.svg" alt="holdet-premier-manager: hvad er hver spiller værd resten af sæsonen, og hvornår betaler en handel sig?" width="100%">
</p>

<p align="center">
  <a href="https://github.com/anjo21ad/holdet-premier-manager/actions/workflows/test.yml"><img src="https://github.com/anjo21ad/holdet-premier-manager/actions/workflows/test.yml/badge.svg" alt="tests"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/afh%C3%A6ngigheder-ingen-2ea44f" alt="ingen afhængigheder">
  <a href="LICENSE"><img src="https://img.shields.io/badge/licens-MIT-blue" alt="MIT-licens"></a>
</p>

<h3 align="center">Hvem skal du købe, og hvem skal du sælge?</h3>

Denne model er lavet til Premier Manager på [holdet.dk](https://www.holdet.dk) og er brugt på mit eget hold i hver runde siden sæsonstart. Den giver alle spillere ét tal: hvor meget de ventes at stige i værdi resten af sæsonen. Og den har en fast regel for, hvornår en handel betaler sig.

**Mit hold, Skjoldes Juveler, ligger nr. 19 af over 28.000 efter ti runder.** Ti runder er for lidt til at skille dygtighed fra held, så det er et godt tegn og ikke et bevis. Hvorfor står under [Den store fælde](#den-store-fælde-held-ligner-talent).

## Hvorfor har jeg lavet det her?

Jeg synes, det er grineren at bruge data til at finde muligheder, som andre overser. Derudover kan jeg bare godt lide at vinde. Filmen Moneyball har ligeledes været en stor inspirationskilde til projektet.

I Moneyball har Oakland Athletics et af ligaens mindste budgetter. I stedet for at betale for det, alle kan se, som slaggennemsnit og homeruns, køber de spillere, der kommer på base. Det vinder kampe, og markedet prissatte det for lavt.

Premier Manager har samme skævhed. Det synlige er point og seneste form, og det er fristende at købe den spiller, der lige har scoret. Modellen ser på det, der skaber pointene: chancernes kvalitet, spilletid og holdets styrke.

## Spillet og målet

<p align="center"><img src="docs/img/point-er-pris.svg" alt="Point er pris: scorer Bruno Fernandes det første mål i en 2-0-udesejr, stiger hans pris 262.000 kr." width="100%"></p>

I Premier Manager er point det samme som prisændring. Alt, hvad en spiller gør på banen, bliver til kroner på hans pris, og stiger dine spillere, stiger dit hold. Hvert køb koster 1 % i gebyr, og penge, der står i spillere, giver ikke den rente på 1 % pr. runde, som de ville give i banken.

Modellens mål er derfor holdets samlede værdi, netto af gebyr og rente. Det handler ikke om at eje de spillere, der giver mest pr. million, men om det hold, der giver mest i alt.

## Data: fire kilder

<p align="center"><img src="docs/img/saadan-virker-det.svg" alt="Fra data til beslutning: holdet.dk, FotMob, odds fra Pinnacle og RotoWire går ind i modellen, derefter kvalitetstjek, seks kontroller og beslutning" width="100%"></p>

| Kilde | Hvad den giver | Hvorfor den er vigtig |
|---|---|---|
| **holdet.dk** | Priser, klubber, positioner og kampprogram | Point er pris, så spillets egne tal er facit. holdet.dk er eneste autoritet, også når spillets univers afviger fra virkeligheden |
| **FotMob** | Starter, minutter, xG og xA fra hver kamp i tre sæsoner, i Premier League og de fire andre store ligaer | xG måler chancernes kvalitet og svinger mindre end mål. Det er grundlaget for spillerens egen rate |
| **Pinnacle** | Odds på næste runde: resultat og over/under 2,5 mål | Markedet er det bedste offentlige bud på hver kamp. Herfra kommer sejrschance, mål for og imod og clean sheet. For Calafiori står det for 61 % af værdien |
| **RotoWire** | Forventede startopstillinger til næste runde | Alt ganges med spilletid. En spiller på bænken giver −5 |

Før hver deadline tjekker `kvalitet.py` data. Er en fil for gammel, eller har en kilde svaret forkert, stopper den hellere end at regne videre.

Odds for runder, der allerede er spillet, kommer fra football-data.co.uk's arkiv.

## Den store fælde: held ligner talent

<p align="center"><img src="docs/img/held-ligner-talent.svg" alt="Held ligner talent: 24 lige gode spillere spreder sig tilfældigt efter tre runder, og den, der ser bedst ud, har haft mest held" width="100%"></p>

Det er let at finde en spiller med flotte tal. Det svære er at vide, om tallene er ægte. Få kampe er for lidt til at skille talent fra held. Leder du blandt 600 spillere efter den, der ser bedst ud, finder du som regel den heldigste.

## Principperne: tre regler

Hver spillers tal bygger på tre regler: hvor meget han skaber, når han er på banen, hvor meget han spiller, og hvor stærkt hans hold er.

### 1. Hvad spilleren skaber: Marcel

<p align="center"><img src="docs/img/marcel.svg" alt="Marcel: Tom Tangos baseballprognose bruger de seneste tre sæsoner vægtet 5/4/3 og trækker mod gennemsnittet. Her bruges xG og xA fra starter, det typiske for rollen med 1.000 minutters vægt, og minutter i en anden klub tæller halvt. Sakas bud på 0,44 bygger 14 procent på i år, 39 procent på sidste sæson, 23 procent på sæsonen før og 24 procent på det typiske for rollen" width="100%"></p>

Marcel er en prognosemodel fra baseball. Tom Tango lavede den for at vise, hvor langt man kommer med det mest basale: de seneste tre sæsoner vægtet 5/4/3 og et træk mod gennemsnittet, indtil der er data nok. Navnet kommer fra "Marcel the Monkey", fordi den skulle være så enkel, at en abe kunne regne den ud. Tabellen viser Marcels fire byggesten, og hvordan de er oversat til fodbold.

Premier Manager har samme problem som baseball: få kampe, meget støj og en stærk fristelse til at tro på den seneste form. Oversat til fodbold måler modellen xG og xA i stedet for mål, kun fra kampe, spilleren starter, og trækker mod det typiske for spillerens rolle. Straffespark regnes for sig: raten bygger på xG uden straffe, og bagefter lægges ligaens straffe-xG pr. kamp gange spillerens andel af klubbens straffe til. Hvert tal kan følges tilbage til de minutter og sæsoner, det bygger på.

<p align="center"><img src="docs/img/tro-paa-det-sete.svg" alt="Saka har 0,69 xG i år mod 0,35 før, og modellen siger 0,44. Palmer har 0,29 i år mod 0,45 før, og modellen siger 0,38" width="100%"></p>

Jo flere kampe, jo mere vejer spillerens egne tal. Efter cirka elleve kampe vejer de mere end det typiske for rollen. Saka og Palmer viser, hvordan det virker: en god eller dårlig start flytter vurderingen, men overtager den ikke.

### 2. Spilletid: opstillingerne

Næste runde regnes på RotoWires forventede opstilling. Resten af sæsonen er halvt RotoWire og halvt den andel af klubbens seneste 15 kampe, spilleren har startet. Andelen trækkes mod RotoWire med tre kampes vægt, så en spiller med få kampe for klubben ikke svinger fra den ene yderlighed til den anden.

### 3. Holdstyrke: markedet

Hvert hold har et udgangspunkt fra før sæsonen, som hver runde opdateres med de målforventninger, der passer til oddsene på resultat og antal mål. Næste kamp regnes direkte på oddsene.

<details>
<summary><b>For de nysgerrige: reglerne og formlen</b></summary>
<br>

| | Regel | Hvad den gør |
|---|---|---|
| 1 | **Rate (Marcel)** | xG uden straffe og xA pr. 90 minutter fra **starter** i tre sæsoner, vægtet 1,0 / 0,8 / 0,6. Minutter i en anden klub tæller halvt. Raten trækkes mod medianen for spillerens rolle med 1.000 minutters vægt. Straffe lægges til som et separat led: ligaens straffe-xG pr. holdkamp × spillerens andel af klubbens straffe |
| 2 | **Spilletid** | Næste runde fra RotoWire. Resten af sæsonen er ½ status + ½ startandel i klubbens seneste 15 kampe, trukket mod status med tre kampe |
| 3 | **Holdstyrke** | Udgangspunkt før sæsonen, opdateret med de målforventninger, der passer til oddsene: totalen fra P(over 2,5 mål) og fordelingen fra P(hjemmesejr) |
| | **Pointformel** | Spillets regler i `ev_kamp()`. `evaluer()` er det eneste sted, forventningen beregnes |

```
g90 = (Σ v · npxG · 90 + K · typisk_for_rollen) / (Σ v · minutter + K) + straffeled        K = 1.000 minutter
```

Hele begrundelsen med kilder står i [docs/metode.md](docs/metode.md).

</details>

## Et regnestykke: Calafiori mod Everton

<p align="center"><img src="docs/img/calafiori.svg" alt="Calafiori mod Everton hjemme i runde 8: 70,4 tusind kroner i forventet vækst. Arsenal giver 43,0: clean sheet, holdmål, resultat, mål imod og nederlag hjemme. Calafiori selv giver 25,4: mål, assist, skud på mål, sejrsmål og udligning. At være med giver 2,0: på banen og gult kort. Inputs: 66 % chance for sejr, Everton scorer ikke i 46 %, 92 % chance for at starte, 0,127 xG og 0,076 xA pr. 90 minutter" width="100%"></p>

Sådan bliver tallene til kroner for én spiller. Calafiori ventes at stige 70.400 kr., når Arsenal tager imod Everton i runde 8, regnet med de data, modellen havde før deadline. Hvert led er en chance gange det, spillets regler giver, gange hvor meget han ventes at spille.

61 % af det kommer fra Arsenal og ikke fra Calafiori selv. Køber du en forsvarer, køber du hans hold. For Haaland er det omvendt: 76 % af hans forventede vækst kommer fra hans egne mål og chancer.

## Det samme for alle 589 spillere

<p align="center"><img src="docs/img/alle-spillere.svg" alt="Alle 589 spillere efter forventet vækst resten af sæsonen. Bedst pr. position: Raya 897, Gabriel 905, Cole Palmer 1.135, Haaland 1.678. Calafiori ligger på 852 tusind kroner, nr. 2 af 195 forsvarere og nr. 23 af 589 i alt. 307 spillere ventes at give under 100 tusind kroner" width="100%"></p>

Regnestykket gentages for hver kamp resten af sæsonen og for hver af de 589 spillere i spillet. For Calafiori giver det 852.000 kr. og en plads som nr. 2 blandt forsvarerne.

Godt halvdelen af spillerne ventes at give under 100.000 kr., fordi de sjældent starter. De gode handler skal findes blandt de få spillere længst til højre.

## Før en handel anbefales

<p align="center"><img src="docs/img/handlens-vaerdi.svg" alt="Foden ud og Mbeumo ind: +645 i forventet vækst, minus 72 i gebyr og 114 i tabt rente, giver +458 tusind kroner" width="100%"></p>

En handel regnes over resten af sæsonen og ikke kun næste runde. Fra gevinsten trækkes gebyret og den rente, du mister, når pengene står i en spiller i stedet for i banken.

<details>
<summary><b>Sådan ser det ud i terminalen</b></summary>
<br>

Eksempelholdet i [`eksempler/hold.json`](eksempler/hold.json) før runde 8:

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

Under hver spiller står, hvad tallet bygger på: antal minutter, hvor meget det typiske for rollen vejer, og hvad man bør kigge efter. Foden har kun startet tre kampe i år og starter sjældent for tiden. Mbeumo bygger på tre hele sæsoner.

</details>

<p align="center"><img src="docs/img/seks-spoergsmaal.svg" alt="Seks kontroller: Foden til Mbeumo holder i alle seks og anbefales. Rice til Rogers er positiv i basis, men fejler tre af de seks" width="100%"></p>

Modellen kan tage fejl, så en handel skal også betale sig, hvis den gør. Målingerne viser tre steder, hvor prognoser som disse rammer ved siden af, og hver kontrol regner handlen igen, som om en af fejlene var sket:

| Kendt fejl | Kontrol |
|---|---|
| Forskellene mellem spillerne er mindre i virkeligheden, end prognosen siger | Forskellen −25 % |
| Vægten på spillerens egne tal kan være for høj eller for lav | K/2 og 2K |
| Spilletid er svær at forudsige | Den nye spiller −0,1 og den gamle +0,1 i spilletid |

Sammen med basis, altså modellens bedste bud, giver det seks kontroller. Ét nej er nok til at beholde holdet. Hviler en ny spillers tal over 50 % på det typiske for rollen, anbefales han aldrig uden et menneskes vurdering.

> [!TIP]
> **Oftest er svaret at beholde holdet.** En handel koster gebyr og rente, så den skal kunne betale sig, også hvis tallene er lidt for optimistiske.

### Rundens handel

<p align="center"><img src="docs/img/mit-hold.svg" alt="Skjoldes Juveler i runde 11, nr. 19 af over 28.000 hold efter ti runder: Raya; Gabriel, Konsa, De Cuyper; Schade, Gómez, Gross, Enciso; Delap, Haaland (kaptajn), Kostoulas. Rundens handel: Thiago ud, udelukket i tre kampe, Delap ind, +185 tusind kroner over resten af sæsonen og ja i alle seks kontroller" width="100%"></p>

Før runde 11 skiftede jeg Thiago ud med Delap. Thiago fik direkte rødt kort i runde 10 og er udelukket i de næste tre kampe, så han giver 0 point i runde 11-13. Modellen regnede både et permanent salg og en midlertidig afløser med genkøb bagefter. Den prøvede afløsere i alle tre positioner, fordi en formation med to angribere også var mulig. Delap gav 185.000 kr. over resten af sæsonen og 92.000 kr. i den værste af de seks kontroller. Han koster 2,5 mio. kr. mindre end Thiago, så pengene står i banken og holder et genkøb åbent, når Thiago er tilbage. Kortet bliver opdateret efter hver runde.

## Virker det?

<p align="center"><img src="docs/img/virker-det.svg" alt="Kan man stole på forskellene? Hældning 1,0 er præcist. Runde 4-5: 0,73. Runde 6-7: 1,08. Runde 8: 0,79. Runde 9-10: 0,91. Runde 4-10 samlet efter antal kampe: under 5 1,00, 5-15 0,62, over 15 0,94, alle 0,94. Top 5 % leverede 111 % af det lovede" width="100%"></p>

Hver runde fra 4 til 10 er regnet, som modellen ville have set den før deadline: kun kampe, odds og opstillinger, der fandtes på det tidspunkt. Bagefter måles, hvor meget af forskellen mellem spillerne der holdt. 1,0 er præcist, og under 1 betyder, at prognosen overdriver forskellene.

- **Samlet holder det.** Over 3.551 spiller-runder er hældningen 0,94. Det ligger inden for de 25 %, som kontrollen "forskellen −25 %" dækker.
- **Toppen leverer det lovede.** De 5 % højest rangerede spillere leverede 111 % af det lovede, top 10 % 103 % og top 25 % 99 %.
- **Spillere med 5-15 kampe er det svage punkt.** Hældningen er 0,62, så forskellene i den gruppe er overdrevne. Gruppen følges runde for runde, og der ændres først noget, når der er tre runders evidens.
- **Én runde er for lidt.** Hældningen svinger fra 0,73 i runde 4-5 til 1,08 i runde 6-7. Først samlet siger tallene noget.

Hver regel er kun taget ind, fordi den gjorde backtesten bedre. Det gælder også straffe som et separat led og startandelen, der trækkes mod status. Pointene i målingen er holdet.dk's egne prisændringer; for runde 4-5 er de regnet ud fra kampdata med spillets regler. Fra nu af låses prognoserne med `praeregistrer.py` før hver deadline og lægges til, efterhånden som runderne bliver spillet.

## Kom i gang

Du skal bruge Python 3.10 eller nyere. Jeg anbefaler at bruge repoet sammen med [Claude Code](https://claude.com/claude-code). [CLAUDE.md](CLAUDE.md) indeholder arbejdsreglerne: `kvalitet.py` skal stå uden STOP, en handel skal holde i alle seks kontroller, og modellen fryses før deadline. Claude Code læser filen automatisk og følger reglerne. Du kan spørge på almindeligt dansk, for eksempel *"Hent data til runde 9 og find en afløser for Foden"*, og få svaret regnet på samme måde hver gang.

**Kør det så tæt på deadline som muligt.** Skader, pressemøder og forventede opstillinger ændrer sig hele ugen, og jo tættere du kommer på kampene, jo mindre ændrer data sig. RotoWire skal hentes højst 24 timer før deadline. Selve metoden ændres aldrig det sidste døgn: modellen fryses 24 timer før deadline, og derefter kommer kun nye data ind.

```bash
git clone https://github.com/anjo21ad/holdet-premier-manager.git
cd holdet-premier-manager
cp eksempler/hold.json eksempler/manager_input.json .    # ret hold.json til dit eget hold

python hent.py holdet                       # priser, klubber, kampprogram og resultater
python hent.py fotmob historik              # første gang: to sæsoner i fem ligaer (~3.500 kampe, ca. 45 min)
python hent.py fotmob                       # årets kampe; kør igen efter hver runde
python hent.py odds historik 10             # første gang: odds for de spillede runder
python hent.py odds 11                      # Pinnacle, højst 48 timer før deadline
python hent.py rotowire 11                  # højst 24 timer før deadline

python model.py 11
python facit_alle.py                        # facit fra holdet.dk's priser (hent holdet efter hver runde)
python kvalitet.py --runde 11               # STOP betyder: ingen beslutning på disse data
python handel.py --skan "Phil Foden"        # de bedste afløsere, vurderet i alle seks kontroller
```

Testene kører uden data: `python test_model.py`. Hvad du gør før deadline og efter hver runde, står i [docs/arbejdsgang.md](docs/arbejdsgang.md).

<details>
<summary><b>Hvad ligger hvor</b></summary>
<br>

| | |
|---|---|
| `hent.py` | Henter fra holdet.dk, FotMob, Pinnacle og RotoWire (odds for spillede runder fra football-data.co.uk) |
| `model.py` | De tre regler og pointformlen. Skriver `input/board.json` |
| `handel.py` | Seks kontroller pr. handel, `--skan` efter afløsere og `--log` til en beslutningslog |
| `kvalitet.py` | Tjekker data før en beslutning og stopper ved fejl |
| `praeregistrer.py` | Låser alle prognoser før deadline. Nægter at overskrive |
| `facit_alle.py` | Facit for alle spillere fra holdet.dk's priser: point er prisændring |
| `kalibrering_alle.py` | Måler prognoserne mod facit. `--backtest` kører modellen, som den var før hver runde |
| `test_model.py` | Tests på opdigtede spillere og kampe |
| `CLAUDE.md` | Arbejdsreglerne, som Claude Code følger |
| `docs/` | [Metode](docs/metode.md), [pointsystem](docs/pointsystem.md) og [arbejdsgang](docs/arbejdsgang.md) |
| `eksempler/` | Skabeloner til `hold.json` og `manager_input.json` |

</details>

## Kendte forenklinger

- Sat op til Premier Manager i efteråret 2026. Til et nyt spil skal du rette spil-id, sæsoner og holdenes udgangspunkt ([se hvordan](docs/arbejdsgang.md#en-ny-sæson)).
- Straffeandelen bygger på sidste og denne sæson. En spiller, der lige har overtaget straffesparkene, er undervurderet, indtil han har taget nogle.
- Udelukkelser og gule kort ligger ikke i modellen og regnes ved siden af.
- Nye spillere i en klub får deres spilletid fra få kampe.
- Spillere fra ligaer uden for de fem store hviler på det typiske for rollen.
- Oddsene dækker næste runde. De senere runder regnes på holdstyrken.
- Kaptajnens dobbelte vækst regnes med i `handel.py`, men ikke i spillernes tal i `board.json`. Et fald hos kaptajnen trækkes ikke fra, og den bund ligger ikke i modellen.

## Data og vilkår

Repoet indeholder **ingen data**. Scriptene henter fra holdet.dk, FotMob, Pinnacle, football-data.co.uk og RotoWire til din egen computer, og data kommer aldrig med i repoet. Du er selv ansvarlig for at bruge kilderne efter deres vilkår.

Projektet er ikke tilknyttet holdet.dk, FotMob, Pinnacle, football-data.co.uk eller RotoWire.

## Licens

Koden er under [MIT](LICENSE). Skriften i illustrationerne er [Inter](https://rsms.me/inter/) under [SIL Open Font License](docs/img/LICENSE-Inter.txt).
