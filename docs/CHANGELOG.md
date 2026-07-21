# Historie změn dokumentace

## Verze 0.17 – 21. 7. 2026

- konkretizováno veřejné create/update API doménové služby vazeb,
- schválen frozen vstup `RelationshipInput` s výchozím
  `DateQualifier.NONE`,
- určena editovatelná pole, práce s `created_by` a aktuálním databázovým
  stavem,
- schválena normalizace symetrických dvojic a lifecycle pravidla,
- konkretizováno bezpečné rozlišení duplicitního a neočekávaného
  `IntegrityError`,
- implementován krok M2.5c bez změny modelů, migrace nebo nového ACP.

## Verze 0.16 – 20. 7. 2026

- konkretizován a implementován historický model `Relationship`,
- potvrzen význam osob A a B a použití úplného `PartialDateModel`,
- povoleno více samostatných období stejného typu mezi stejnými osobami,
- schválena normalizace symetrických dvojic podle PK v budoucí službě
  a modelová kontrola kanonického pořadí,
- doplněn zákaz vztahu osoby k sobě a dva podmíněné unikátní constrainty,
- rozlišeno započítání archivace a měkkého odstranění do unikátnosti,
- vytvořena strukturální migrace `people.0008_relationship` a integrační
  testy bez potřeby nového ACP.

## Verze 0.15 – 20. 7. 2026

- konkretizován pevný výčet sedmi kategorií vztahů a uživatelsky
  rozšiřitelný číselník `RelationshipType`,
- schválen význam uloženého směru, genderovaných názvů, symetrie, podpory
  časového rozmezí a odvoditelnosti,
- schválen katalog čtrnácti systémových typů vztahů,
- schválena modelová validace a databázový constraint symetrických názvů,
- opraveno skutečné pořadí migrací aplikace `people`,
- potvrzeno, že konkrétní `Relationship` vznikne až v následujícím kroku
  M2.5 a že konkretizace nevyžaduje nové ACP.

## Verze 0.14 – 20. 7. 2026

- konkretizován veřejný kontrakt služby `replace_event_participants()`,
- implementována atomická náhrada celé sady účastníků události,
- doplněna validace aktivních rolí a aktuální konfigurace
  `AllowedEventRole`,
- oddělena průběžná kontrola `max_count` od kontroly `min_count` při
  požadavku na úplnost,
- potvrzeno striktní ověření nové sady bez automatických zpětných změn
  historických účastí,
- krok M2.4e nevytvořil databázovou migraci.

## Verze 0.13 – 20. 7. 2026

- konkretizován minimalistický spojovací model `EventParticipant`,
- potvrzeny povinné vazby na `Event`, `Person` a `ParticipantRole`,
- schválena jedinečnost trojice událost, osoba a role,
- oddělena databázová integrita účasti od budoucí servisní validace
  `AllowedEventRole`, aktivity role a počtů účastníků,
- implementován krok M2.4d včetně strukturální migrace a testů.

## Verze 0.12 – 18. 7. 2026

- konkretizován základní model `Event`, jeho společná a vlastní pole,
- schválena validace podpory rozmezí, strukturovaného místa a lokalizačního
  detailu,
- potvrzen snapshotový význam defaultů `EventType` a jejich budoucí použití
  v doménové službě bez zpětného přepisování existujících událostí,
- odděleny migrace základního `Event` a budoucího `EventParticipant`,
- implementován krok M2.4c včetně strukturální migrace a testů.

## Verze 0.11 – 18. 7. 2026

- konkretizován číselník `ParticipantRole` a jedenáct systémových rolí,
- konkretizován konfigurační model `AllowedEventRole`, jeho integritní
  omezení a genderově neutrální role `spouse`,
- schválena matice rolí pro dvanáct systémových typů událostí,
- implementační krok M2.4b rozdělen na jednu strukturální a dvě datové
  migrace,
- implementován krok M2.4b včetně modelů, systémových dat a testů,
- nebyla zjištěna potřeba nového ACP.

## Verze 0.10 – 17. 7. 2026

- konkretizován model `EventType`, jeho výchozí nastavení a dvanáct
  systémových typů událostí,
- oddělena strukturální a datová migrace typů událostí,
- zdravotní skutečnosti sjednoceny jako zdravotní záznamy a příčina
  úmrtí přesunuta do specializovaného `DeathDetail`,
- nebyla zjištěna potřeba nového ACP.

## Verze 0.9 – 17. 7. 2026

- konkretizována implementovatelná struktura modelu `Place`, jeho metadata,
  hierarchie, souřadnice a validační pravidla,
- potvrzen textový charakter země nebo historického státního útvaru a
  explicitní zadávání normalizovaného názvu,
- nebyla zjištěna potřeba nového ACP.

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
