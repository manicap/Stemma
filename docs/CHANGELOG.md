# Historie změn dokumentace

## Verze 0.8 – 16. 7. 2026

- dokončen milník M1 – společný základ aplikace `common`,
- implementováno pět pevných výčtů a sedm abstraktních modelů,
- doplněna validace neúplných a nejistých dat se stabilními chybovými kódy,
- doplněno automatické odvozování `sort_date` a `sort_date_end` bez falešné historické přesnosti,
- ověřeno 26 testů aplikace `common` a 28 testů celého projektu,
- potvrzen čistý stav migrací: `No changes detected`,
- roadmapa přesunuta na M2 – jádro Osoba, Místo, Událost a Vazba,
- aktualizován implementační stav v databázovém návrhu a evidence rozhodnutí,
- přidán editovatelný HTML zdroj a PDF stavového A4 sheetu,
- nebyla zjištěna potřeba nového ACP.

## Verze 0.7 – 15. 7. 2026

- zahájena implementace MVP ve větvi `feature/mvp`,
- dokončen milník M0 – založení Django projektu,
- potvrzen podporovaný základ Python 3.14 a Django 5.2 LTS,
- zaznamenáno ověřené prostředí Python 3.14.6, Django 5.2.16 a SQLite 3.50.4,
- založen konfigurační balíček `config`,
- vytvořena aplikace `accounts` a vlastní model `accounts.User`,
- vytvořena a aplikována migrace `accounts.0001_initial`,
- doplněna registrace uživatele v Django Adminu a základní testy,
- zavedena lokální tajná konfigurace mimo Git a veřejný vzor nastavení,
- doplněn `requirements.txt` a pravidla reprodukovatelného prostředí,
- uzavřena otevřená otázka podporovaných verzí,
- nebyla zjištěna potřeba nového ACP.

## Verze 0.6 – 15. 7. 2026

- dokončen logický a technický databázový návrh,
- uzavřen společný model neúplných a nejistých dat,
- upřesněny entity osoby, jmen, míst, událostí, vazeb, bydlišť a hrobových míst,
- potvrzen zdravotní záznam jako samostatná entita bez duplicitní obecné události,
- potvrzeny explicitní spojovací modely příloh a zdrojů,
- doplněn model auditní operace a změn jednotlivých polí,
- navrženo rozdělení Django aplikací,
- navrženy abstraktní modely, doménové služby a selektory,
- určeno rozdělení validace mezi databázi, modely a servisní vrstvu,
- navrženo pořadí migrací a základní indexy,
- vytvořen verzovaný ER diagram a jednoduchý A4 přehled databáze,
- databázová etapa označena jako připravená k implementaci,
- nebyla zjištěna potřeba nového ACP.

## Verze 0.5 – 15. 7. 2026

- GitHub určen jako jediné autoritativní úložiště projektu,
- projektové zdroje ChatGPT definovány jako pracovní kopie,
- přidán registr `12_ARCHITEKTONICKA_ROZHODNUTI.md`,
- zpětně zapsána rozhodnutí ACP-001 až ACP-005,
- databázový handoff doplněn o postup pro případnou změnu architektury.

## Verze 0.4 – 15. 7. 2026

- UI/UX označeno jako dokončený schválený pracovní základ,
- projekt přesunut do databázové a technické fáze,
- roadmapa doplněna o konkrétní databázové výstupy,
- přidán `11_DATABAZOVY_NAVRH.md`,
- doplněna pravidla pro vznik Django modelů a migrací,
- připraveno předání do samostatné databázové konverzace.

## Verze 0.3 – 15. 7. 2026

- přidán `10_UI_UX_NAVRH.md`,
- uzavřena základní struktura seznamu a detailu osoby,
- definovány karty Přehled, Vztahy, Události, Bydliště, Zdraví a Materiály,
- doplněno responzivní chování,
- definována editace, archivace, prázdné stavy, upozornění a ochrana neuložených změn,
- definován světlý a tmavý motiv,
- doplněny kategorie osob do datového modelu.

## Verze 0.2 – 14. 7. 2026

- zvolen Python a Django,
- zvoleny serverově renderované šablony a HTMX,
- zvolena SQLite,
- odmítnuta SPA architektura,
- doplněn GitHub repozitář,
- přidán `09_CODING_STANDARD.md`.

## Verze 0.1 – 14. 7. 2026

Sjednocení funkčního návrhu, datového modelu, oprávnění a architektonických principů.

## Verze 0.0 – 14. 7. 2026

Vytvořen počáteční balíček.
