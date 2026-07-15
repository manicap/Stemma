# Roadmapa projektu

**Dokument:** 07  
**Verze:** 0.6
**Stav:** realizace MVP
**Datum revize:** 16. 7. 2026

## Fáze 1 – Konsolidace návrhu ✅

- uzavřen funkční a základní datový model,
- uzavřeny hlavní entity a architektonické principy.

## Fáze 2 – Návrh UI/UX ✅

- uzavřen schválený pracovní základ hlavního rozhraní,
- definovány světlý a tmavý motiv,
- definována responzivita, editace a ochrana neuložených změn.

## Fáze 3 – Databázový a technický návrh ✅

### Dokončené výstupy

- katalog entit a jejich odpovědností,
- přesný katalog polí,
- kardinality a povinné vazby,
- společný model neúplného data,
- pravidla integrity a unikátnosti,
- pravidla archivace a měkkého odstranění,
- přílohy a zdroje s explicitními vazbami,
- ochrana zdravotních údajů,
- návrh auditního modelu,
- návrh indexů,
- ER diagram,
- struktura Django aplikací,
- rozdělení validace mezi databázi, modely a služby,
- návrh pořadí migrací,
- architektonická revize.

### Implementační milníky

#### M0 – založení Django projektu ✅

- potvrzen Python 3.14 a Django 5.2 LTS,
- založeno reprodukovatelné prostředí `venv` + `pip`,
- založen Django projekt s balíčkem `config`,
- vytvořena aplikace `accounts`,
- vytvořen vlastní model `accounts.User` a migrace `accounts.0001_initial`,
- doplněna registrace v Django Adminu a základní testy,
- nastavena SQLite, čeština, časové pásmo `Europe/Prague` a lokální tajná konfigurace mimo Git,
- změny commitnuty a pushnuty do `feature/mvp`.

#### M1 – společný základ ✅

- založena a registrována aplikace `common`,
- vytvořeny pevné výčty pro pohlaví, přístup, ověření a neúplná data,
- vytvořeno sedm abstraktních modelů společných polí a číselníků,
- doplněna validace neúplných a nejistých dat,
- doplněn výpočet technických mezí `sort_date` a `sort_date_end`,
- doplněny testy; M1 nevytváří vlastní databázovou tabulku ani migraci,
- změny implementovány a ověřeny ve větvi `feature/mvp`.

#### M2 – jádro Osoba, Místo, Událost a Vazba ◀ aktuální

1. založit doménové aplikace potřebné pro jádro,
2. implementovat základní číselníky a model Osoba,
3. implementovat Místo,
4. implementovat Událost a účastníky události,
5. implementovat Vazbu mezi osobami,
6. vytvářet malé strukturální a datové migrace,
7. doplňovat testy databázové integrity a doménových pravidel.

#### Následující implementační kroky

1. dokončit M2 – jádro Osoba, Místo, Událost a Vazba,
2. doplnit bydliště a hrobová místa,
3. doplnit přílohy, zdroje a jejich propojení,
4. doplnit zdravotní záznamy,
5. doplnit audit a projektová oprávnění,
6. rozšiřovat testy databázové integrity,
7. připravit vývojová ukázková data.

## Fáze 4 – Interaktivní prototyp

- layout nad skutečnými Django views a šablonami,
- ukázkový seznam osob,
- přepínání detailu pomocí HTMX,
- základní záložky,
- ukázkové formuláře,
- test použitelnosti.

## Fáze 5 – MVP

- přihlášení,
- osoby,
- narození a úmrtí,
- základní vazby,
- fotografie,
- vyhledávání,
- historie změn,
- základní oprávnění.

## Fáze 6 – První použitelná verze

- všechny běžné události,
- bydliště,
- dokumenty a přílohy,
- zdravotní záznamy,
- hrobová místa,
- zdroje,
- rodokmen,
- časová osa,
- záloha a export.

## Fáze 7 – Testování v rodině

- ověření s méně technickými uživateli,
- kontrola formulářů,
- kontrola čitelnosti,
- kontrola oprávnění,
- kontrola zálohování,
- úpravy podle používání.

## Fáze 8 – Budoucí rozšíření

- import/export GEDCOM,
- mapa míst,
- pokročilý rodokmen,
- návrhy duplicit,
- veřejné sdílení vybraných částí,
- pokročilé vyhledávání,
- univerzální model tvrzení,
- automatizované zpracování dokumentů.
