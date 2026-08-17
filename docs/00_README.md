# Rodinná databáze – dokumentace projektu

**Verze dokumentace:** 0.11
**Stav:** pracovní návrh v implementaci; experimentální RC 0.1
**Datum revize:** 17. 8. 2026

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

## Stav verze 0.11

Verze 0.11 doplňuje reprodukovatelné lokální spuštění RC 0.1:

- čistý checkout má jednoznačný návod pro Python 3.14, `venv`, závislosti,
  lokální tajný klíč, migrace a vývojový server,
- bezpečný lokální `seed_demo_data` poskytuje syntetická data pro ověření
  tří přístupových úrovní bez účtů, hesel nebo jiných tajemství,
- příkaz podporuje náhled bez zápisu, nepřepisuje ani nemaže existující data
  a mimo lokální režim `DEBUG=True` selže,
- celý Windows postup prošel v izolovaném čistém snapshotu včetně instalace,
  migrací, opakovaného seedu, systémové kontroly a HTTP 200 vývojového serveru.

## Stav verze 0.10

Verze 0.10 zaznamenává první skutečný uživatelský vertikální řez RC 0.1:

- autorizovaný seznam a detail osoby čtou skutečná databázová data,
- přímá URL, HTMX i Django Admin respektují centrální access policy,
- neexistující a neviditelný cíl mají jednotnou bezpečnou 404 odpověď,
- vznikl responzivní dvousloupcový základ, mobilní vysouvací seznam,
  funkční světlý a tmavý motiv a běžné empty/loading/error stavy,
- HTMX 2.0.10 je uložen lokálně v projektové statice včetně licence,
- desktopový i mobilní list/detail průchod byl ověřen ve skutečném browseru,
- B, C a G zůstávají dílčí, dokud nejsou doplněny odvozené údaje,
  login, editace a úplné browser ověření navazujícího RC průchodu.

## Stav verze 0.9

Verze 0.9 zavádí experimentální autonomní vývojový režim pro první skutečně použitelný průřez aplikace:

- zachovává `feature/mvp` jako původní non-agentní vývojový základ,
- používá `backup/pre-agent-2026-08-17` jako neměnný návratový bod před experimentem,
- zavádí aktivní experimentální větev `agent/rc-0.1`,
- schvaluje ACP-006 pro autonomní agentní workflow pouze na této větvi,
- definuje RC 0.1 jako měřitelný end-to-end průchod: spuštění, skutečný seznam osob, detail osoby, login/logout, jednoduchá editace, serverová oprávnění a použitelné UI,
- umožňuje hlavnímu agentovi samostatně volit malé vertikální řezy, testovat, používat nezávislé review role, opravovat chyby, commitovat a pushovat ověřené řezy na `agent/rc-0.1`,
- zachovává povinnou eskalaci při změně architektury, ACP, bezpečnostní policy, destruktivním zásahu, produkčním nasazení nebo skutečném rozporu dokumentace,
- dokončení RC 0.1 samo neznamená dokončení celé Stemmy ani povolení produkčního nasazení.

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

## Reprodukovatelné lokální spuštění

Požadovaným základem je Python 3.14. Všechny příkazy se spouštějí v kořeni
čistého checkoutu. Lokální databáze a tajný klíč se do Gitu neukládají.

### Windows PowerShell

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item config\settings_local.example.py config\settings_local.py
.\.venv\Scripts\python.exe -c "from secrets import token_urlsafe; print(token_urlsafe(50))"
```

Poslední příkaz vypíše náhodný lokální klíč. V novém
`config/settings_local.py` jím nahraďte text
`replace-with-a-random-secret-key` a pokračujte:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo_data
.\.venv\Scripts\python.exe manage.py runserver
```

### Linux a macOS

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp config/settings_local.example.py config/settings_local.py
python -c "from secrets import token_urlsafe; print(token_urlsafe(50))"
```

V `config/settings_local.py` nahraďte stejný zástupný text vypsaným klíčem
a spusťte:

```bash
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver
```

Aplikace je poté dostupná na `http://127.0.0.1:8000/`.

`seed_demo_data` vytváří tři jednoznačně označené syntetické osoby pro
veřejnou, přihlášenou a omezenou úroveň. Příkaz funguje pouze s lokálním
`DEBUG=True`; mimo tento režim selže bez zápisu. Opakované spuštění při
zachování vložených markerů nevytváří duplicity, existující ukázkové záznamy
nepřepisuje a nic nemaže. Plán lze bez zápisu zkontrolovat příkazem
`python manage.py seed_demo_data --dry-run`. Demo uživatelské účty nejsou
součástí tohoto kroku a příkaz neukládá žádná hesla ani tajemství.

## Aktuální fáze projektu

- Návrh UI/UX je uzavřen jako schválený pracovní základ.
- Databázový a technický návrh je dokončen jako schválený pracovní základ.
- Původní implementační posloupnost zůstává vedena v `feature/mvp`; M0 a M1 jsou dokončené a dokumentovaná implementace je v M2.
- Pro ověření autonomního agentního vývoje běží oddělený experiment v `agent/rc-0.1` podle ACP-006.
- Aktivním cílem této experimentální větve je RC 0.1 definované v `07_ROADMAPA.md`; nejde o náhradu stavů původních milníků.
- `backup/pre-agent-2026-08-17` je návratový bod před zahájením agentního experimentu a neslouží k vývoji.
- Hlavním technickým dokumentem zůstává `11_DATABAZOVY_NAVRH.md` a exekuční pravidla agentní větve určuje kořenový `AGENTS.md`.

## Autoritativní úložiště

Jediným autoritativním úložištěm projektu je GitHub:

`https://github.com/manicap/Stemma`

Projektové zdroje v ChatGPT jsou pracovní kopií aktuální dokumentace pro právě řešenou etapu. Historii, platné soubory a konečný stav projektu uchovává GitHub.

## Architektonická rozhodnutí

Významná a dlouhodobá rozhodnutí jsou evidována v dokumentu:

`12_ARCHITEKTONICKA_ROZHODNUTI.md`

Každé takové rozhodnutí má označení ACP, důvod, dopady a stav.
