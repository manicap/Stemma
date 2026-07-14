# Rodinná databáze – dokumentace projektu

**Verze dokumentace:** 0.2  
**Stav:** pracovní návrh  
**Datum revize:** 14. 7. 2026

## Účel balíčku

Tento balíček je aktuálním zdrojem pravdy pro projekt **Rodinná databáze – Návrh a vývoj**.

Projekt není zamýšlen pouze jako rodokmen, ale jako dlouhodobě rozšiřitelný rodinný informační systém pro evidenci osob, událostí, vazeb, míst, zdrojů, dokumentů, fotografií a citlivých rodinných informací.

## Obsah

1. `01_VIZE_A_ROZSAH_v0.1.md`
2. `02_FUNKCNI_SPECIFIKACE_v0.1.md`
3. `03_DATOVY_MODEL_v0.1.md`
4. `04_UZIVATELSKE_ROLE_A_PRAVA_v0.1.md`
5. `05_PRAVIDLA_DOKUMENTACE_v0.1.md`
6. `06_ROZHODNUTI_A_OTEVRENE_OTAZKY_v0.1.md`
7. `07_ROADMAPA_v0.1.md`
8. `08_ARCHITEKTONICKE_PRINCIPY_v0.1.md`
9. `09_CODING_STANDARD.md`
10. `CHANGELOG.md`

## Jak dokumentaci používat

- Za platnou se považuje vždy nejnovější verze dokumentu.
- Při rozporu mezi chatem a dokumentací má přednost novější dokumentace, pokud uživatel výslovně neurčí jinak.
- Důležitá nová rozhodnutí se po schválení zapracují do dokumentace.
- Dokumentace se neaktualizuje po každé drobnosti, ale vždy dříve, než by hrozila ztráta kontextu.
- Starší verze se nemažou; přesouvají se do archivu.

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

- Python
- Django
- serverově renderované Django šablony
- HTMX pro dílčí aktualizace rozhraní
- SQLite pro vývoj a první provozní verzi
- minimum vlastního JavaScriptu
- žádná SPA architektura

Django bylo zvoleno jako kompromis mezi rychlostí výsledné aplikace, rychlostí vývoje, spolehlivostí a možností používat Python také pro importy, exporty, automatizaci a budoucí práci s dokumenty.

## Repozitář

Oficiální GitHub repozitář projektu:

`https://github.com/manicap/Stemma`
