# Rodinná databáze – dokumentace projektu

**Verze dokumentace:** 0.8
**Stav:** pracovní návrh v implementaci
**Datum revize:** 16. 7. 2026

## Účel balíčku

Tento balíček je aktuálním zdrojem pravdy pro projekt **Rodinná databáze – Návrh a vývoj**.

Projekt není zamýšlen pouze jako rodokmen, ale jako dlouhodobě rozšiřitelný rodinný informační systém pro evidenci osob, událostí, vazeb, míst, zdrojů, dokumentů, fotografií a citlivých rodinných informací.

## Obsah

1. `01_VIZE_A_ROZSAH.md`
2. `02_FUNKCNI_SPECIFIKACE.md`
3. `03_DATOVY_MODEL.md`
4. `04_UZIVATELSKE_ROLE_A_PRAVA.md`
5. `05_PRAVIDLA_DOKUMENTACE.md`
6. `06_ROZHODNUTI_A_OTEVRENE_OTAZKY.md`
7. `07_ROADMAPA.md`
8. `08_ARCHITEKTONICKE_PRINCIPY.md`
9. `09_CODING_STANDARD.md`
10. `10_UI_UX_NAVRH.md`
11. `11_DATABAZOVY_NAVRH.md`
12. `12_ARCHITEKTONICKA_ROZHODNUTI.md`
13. `CHANGELOG.md`

Přehledové výstupy:

- `stemma_databaze_a4_prehled.pdf` – stručný přehled databázového návrhu,
- `stemma_stav_aplikace_a4.html` – editovatelný zdroj stavového sheetu,
- `stemma_stav_aplikace_a4.pdf` – A4 stavový sheet po dokončení M1.

## Jak dokumentaci používat

- Za platnou se považuje vždy nejnovější verze dokumentu.
- Při rozporu mezi chatem a dokumentací má přednost novější dokumentace, pokud uživatel výslovně neurčí jinak.
- Důležitá nová rozhodnutí se po schválení zapracují do dokumentace.
- Dokumentace se neaktualizuje po každé drobnosti, ale vždy dříve, než by hrozila ztráta kontextu.
- Starší verze se nemažou; přesouvají se do archivu.



## Stav verze 0.8

Verze 0.8 zaznamenává dokončení milníku M1 a přechod k jádru domény:

- potvrzuje založení a registraci aplikace `common`,
- eviduje pět pevných `TextChoices` a sedm abstraktních modelů,
- zaznamenává validaci neúplných a nejistých dat bez falešné přesnosti,
- potvrzuje automatické odvozování technických mezí `sort_date` a `sort_date_end`,
- eviduje 26 testů aplikace `common` a 28 testů celého projektu,
- potvrzuje, že M1 nevytvořil vlastní databázovou tabulku ani migraci,
- označuje M2 – jádro Osoba, Místo, Událost a Vazba – jako následující implementační krok,
- přidává editovatelný zdroj a PDF stavového A4 sheetu.

## Stav verze 0.7

Verze 0.7 zaznamenává zahájení implementace MVP a dokončení milníku M0:

- potvrzuje Python 3.14 a Django 5.2 LTS,
- zaznamenává ověřené vývojové prostředí Python 3.14.6, Django 5.2.16 a SQLite 3.50.4,
- potvrzuje použití `venv` a `pip`,
- zaznamenává založení Django projektu s konfiguračním balíčkem `config`,
- potvrzuje vlastní uživatelský model `accounts.User` od první projektové migrace,
- zaznamenává bezpečnou lokální konfiguraci mimo Git, základní testy a zahájení práce ve větvi `feature/mvp`.

## Stav verze 0.6

Verze 0.6 dokončuje databázovou a technickou návrhovou etapu:

- uzavírá logický databázový model a katalog polí,
- definuje společný model neúplných a nejistých dat,
- stanovuje kardinality, integritní pravidla, indexy a audit,
- potvrzuje explicitní propojení příloh a zdrojů,
- navrhuje strukturu Django aplikací, doménové služby a selektory,
- určuje pořadí migrací a připravuje projekt k implementaci.

## Stav verze 0.3

Verze 0.3 doplňuje:

- první ucelený návrh UI/UX,
- strukturu seznamu a detailu osoby,
- responzivní chování pro počítač, tablet a telefon,
- pravidla editace, upozornění a prázdných stavů,
- světlý a tmavý motiv včetně konkrétních barevných proměnných,
- kategorie osob v datovém modelu.

## Stav verze 0.1

Verze 0.1 sjednocuje dosavadní návrh, odstraňuje rozpory verze 0.0 a doplňuje zejména:

- trvale viditelný seznam osob a detail osoby,
- narození a úmrtí jako události,
- automatický výpočet věku a stavu žijící/zemřelý,
- automatické římské číslování osob se shodným jménem,
- obousměrné vazby mezi osobami,
- zdravotní informace,
- hrobová místa,
- univerzální přílohy,
- architektonické principy,
- pravidla kontroly konzistence,
- roli projektového architekta Marcus.


## Technologické rozhodnutí

- Python 3.14
- Django 5.2 LTS
- serverově renderované Django šablony
- HTMX pro dílčí aktualizace rozhraní
- SQLite pro vývoj a první provozní verzi
- minimum vlastního JavaScriptu
- žádná SPA architektura

Django bylo zvoleno jako kompromis mezi rychlostí výsledné aplikace, rychlostí vývoje, spolehlivostí a možností používat Python také pro importy, exporty, automatizaci a budoucí práci s dokumenty.

## Repozitář

Oficiální GitHub repozitář projektu:

`https://github.com/manicap/Stemma`


## Aktuální fáze projektu

- Návrh UI/UX je uzavřen jako schválený pracovní základ.
- Databázový a technický návrh je dokončen jako schválený pracovní základ.
- Implementace MVP byla zahájena ve větvi `feature/mvp`.
- Milníky M0 – založení Django projektu – a M1 – společný základ – jsou dokončeny.
- Existuje konfigurační balíček `config`, aplikace `accounts` a `common`, vlastní model `accounts.User`, první projektová migrace a testovaný společný základ.
- `common` obsahuje pevné výčty, abstraktní modely a validaci neúplných dat včetně technických řadicích mezí.
- Aktuálním krokem je M2: jádro Osoba, Místo, Událost a Vazba.
- Hlavním technickým dokumentem zůstává `11_DATABAZOVY_NAVRH.md`.


## Autoritativní úložiště

Jediným autoritativním úložištěm projektu je GitHub:

`https://github.com/manicap/Stemma`

Projektové zdroje v ChatGPT jsou pracovní kopií aktuální dokumentace pro právě řešenou etapu. Historii, platné soubory a konečný stav projektu uchovává GitHub.

## Architektonická rozhodnutí

Významná a dlouhodobá rozhodnutí jsou evidována v dokumentu:

`12_ARCHITEKTONICKA_ROZHODNUTI.md`

Každé takové rozhodnutí má označení ACP, důvod, dopady a stav.
