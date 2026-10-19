# Pointsystemet

I Premier Manager er point det samme som prisændring. Når en spiller scorer, stiger hans pris, og dit hold bliver mere værd. Det er hele spillet: få holdets samlede værdi til at vokse.

Tallene herunder er regelsæt 119 (Efterår 2026), kontrolleret mod hele feltets prisændringer i de første runder. `facit_alle.py` regner reglerne ud fra understat-data og rammer holdets egne tal kroneeksakt for 90-97 % af spillerne.

## Hændelser

| Hændelse | Kr. | Bemærkning |
|---|---:|---|
| Mål, angriber | +125.000 | |
| Mål, midtbane | +150.000 | |
| Mål, forsvar | +175.000 | |
| Mål, målmand | +250.000 | |
| Assist | +60.000 | Ikke ved selvmål og straffe |
| Skud på mål uden scoring | +10.000 | Ikke straffe, stolpe eller blokeret |
| Scoring til sejr | +40.000 | Målet, der bragte vinderen foran for sidste gang |
| Scoring til uafgjort | +20.000 | Det sidste mål i en uafgjort kamp |
| Sejr / uafgjort / nederlag | +25.000 / +5.000 / −8.000 | Kræver at have været på banen |
| Sejr på udebane | +10.000 | Oven i sejren |
| Nederlag på hjemmebane | −5.000 | Oven i nederlaget |
| Holdet scorer | +10.000 | Pr. mål, kun mens spilleren er på banen |
| Modstanderen scorer | −8.000 | Pr. mål, kun mens spilleren er på banen. Eget selvmål tæller med |
| På banen | +7.000 | Startende eller indskiftet |
| I truppen, ikke på banen | −5.000 | |
| Ikke i truppen | 0 | |
| Clean sheet, forsvar / målmand | +50.000 / +75.000 | Kræver mindst 60 minutter |
| Redning | +5.000 | Pr. redning |
| Reddet straffe | +100.000 | |
| Brændt straffe | −30.000 | |
| Hattrick | +100.000 | |
| Gult kort | −20.000 | Gives også på bænken |
| Rødt kort | −50.000 | |
| Selvmål | −50.000 | Kun for selvmålsscoreren |

## Økonomien rundt om

| | |
|---|---|
| Kaptajn | Kaptajnens vækst tælles én gang til og udbetales i banken |
| Bankrente | 1 % pr. runde af kontantbeholdningen |
| Gebyr | 1 % af købsprisen. Et fortrudt køb i samme vindue er gebyrfrit |
| Klubloft | Højst 4 spillere fra samme klub |
| Formationer | 1 målmand og 3-5-2, 3-4-3, 4-3-3, 4-4-2, 4-5-1, 5-3-2 eller 5-4-1 |

## Detaljer, der er målt i data

- **Clean sheet kræver 60 minutter.** En forsvarer, der blev skiftet ud i 59. minut, fik ikke clean sheet. En, der gik ud i 61. minut, fik det.
- **−5 og 0 er to tilstande.** −5 betyder på bænken, 0 betyder uden for truppen. Filtrér derfor "spillede" som point ∉ {−5, 0}.
- **Kun Premier League giver point.** Pokalkampe, europæisk fodbold og landskampe flytter ikke en eneste pris.
- **Der findes ingen afgørende assist.** Scoring til sejr og til uafgjort går kun til målscoreren.

## Hvad det betyder for modellen

- Målscorere dominerer, og mål på favorithold bærer ekstra, fordi en del af dem bliver sejrsmål.
- Holdmål og modstandermål (+10 / −8 pr. mål) spreder topklubbernes spillere fra bundklubbernes. Det er grunden til, at holdstyrken fra Betfair vejer tungt.
- Clean sheet og redninger gør målmanden til en forsvarsspiller med eget regnestykke. `ev_kamp` regner clean sheet som e<sup>−λ<sub>imod</sub></sup>.
- Gebyret og den tabte rente gør, at hver handel skal tjene sig hjem. Mod slutningen af sæsonen er der færre runder at gøre det på.
