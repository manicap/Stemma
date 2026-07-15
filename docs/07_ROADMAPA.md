# Roadmapa projektu

**Dokument:** 07  
**Verze:** 0.4  
**Stav:** návrh postupu  
**Datum revize:** 15. 7. 2026

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

### Následující implementační kroky

1. potvrdit podporované verze Pythonu a Djanga,
2. založit Django projekt a vlastní uživatelský model,
3. vytvořit společné výčty a abstraktní modely,
4. implementovat jádro Osoba, Místo, Událost a Vazba,
5. vytvořit malé strukturální a datové migrace,
6. doplnit bydliště a hrobová místa,
7. doplnit přílohy, zdroje a jejich propojení,
8. doplnit zdravotní záznamy,
9. doplnit audit a projektová oprávnění,
10. vytvořit testy databázové integrity,
11. připravit vývojová ukázková data.

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
