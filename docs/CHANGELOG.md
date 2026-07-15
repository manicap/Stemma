# Historie změn dokumentace

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
