# Architektonická rozhodnutí

**Dokument:** 12  
**Verze:** 0.2  
**Stav:** platný registr rozhodnutí  
**Datum vytvoření:** 15. 7. 2026

## Účel

Dokument eviduje významná rozhodnutí, která dlouhodobě ovlivňují architekturu, implementaci nebo workflow projektu Stemma.

Stavy:

- **Navrženo**
- **Schváleno**
- **Nahrazeno**
- **Zamítnuto**

---

## ACP-001 — Python a Django

**Stav:** Schváleno

### Kontext

Projekt potřebuje rychlý vývoj, vyzrálou autentizaci, administraci, databázové migrace a možnost používat stejný jazyk také pro importy, exporty a údržbové skripty.

### Rozhodnutí

Hlavním jazykem je Python 3.14. Webová aplikace bude postavena na Django 5.2 LTS.

Milník M0 byl ověřen s Pythonem 3.14.6 a Django 5.2.16. Přímé závislosti jsou evidovány v `requirements.txt`.

### Důvod

- rychlý vývoj,
- vyzrálý framework,
- dobrá čitelnost,
- Django Admin,
- silná podpora nástrojů a Codexu,
- jeden jazyk pro web i podpůrné utility.

### Dopady

Projekt přijímá konvence Djanga a Python ekosystému. Podporovanou řadou je Python 3.14 a Django 5.2 LTS; aktualizace opravných verzí probíhají průběžně po ověření testy. Konkretizace verzí nemění podstatu ACP-001 a nevyžaduje nové ACP.

---

## ACP-002 — Narození a úmrtí jako události

**Stav:** Schváleno

### Kontext

Narození a úmrtí mají vlastní datum, místo, zdroje, přílohy, účastníky a další metadata.

### Rozhodnutí

Narození a úmrtí nejsou běžná pole entity Osoba. Jsou speciálními typy událostí.

### Důvod

- jednotný model životních událostí,
- možnost připojit zdroje a přílohy,
- odstranění duplicit,
- lepší rozšiřitelnost.

### Dopady

Stav žijící/zemřelý, věk a roky života se odvozují. Každá osoba může mít nejvýše jednu aktivní událost Narození a jednu aktivní událost Úmrtí.

---

## ACP-003 — Serverové HTML a HTMX místo SPA

**Stav:** Schváleno

### Kontext

Aplikace má být rychlá i na starších počítačích a telefonech a bude mít jen několik uživatelů.

### Rozhodnutí

Rozhraní bude serverově renderované pomocí Django templates. HTMX se použije pro dílčí aktualizace. Aplikace nebude SPA.

### Důvod

- malá zátěž klienta,
- minimum JavaScriptu,
- rychlé první načtení,
- jednodušší vývoj a ladění,
- menší počet vrstev.

### Dopady

Server vrací HTML nebo HTML fragmenty. Velký frontendový framework se nepřidá bez nového schváleného ACP.

---

## ACP-004 — SQLite jako výchozí databáze

**Stav:** Schváleno

### Kontext

Projekt má přibližně pět až šest uživatelů, převážně čtecí provoz a požadavek na jednoduché zálohování.

### Rozhodnutí

Výchozí databází pro vývoj a první provozní verzi bude SQLite.

### Důvod

- jednoduchý provoz,
- nízká režie,
- jeden databázový soubor,
- dostatečný výkon,
- snadné zálohování.

### Dopady

Datový model se nesmí zbytečně vázat na nestandardní vlastnosti SQLite. PostgreSQL se použije pouze při skutečné provozní potřebě.

---

## ACP-005 — GitHub jako autoritativní úložiště

**Stav:** Schváleno

### Kontext

Projektové zdroje ChatGPT nelze automaticky synchronizovat s GitHubem a uchovávání více verzí ve zdrojích vytváří duplicity.

### Rozhodnutí

Jediným autoritativním úložištěm projektu je:

`https://github.com/manicap/Stemma`

Projektové zdroje v ChatGPT jsou pouze aktuální pracovní kopií pro danou etapu.

### Důvod

- jediný zdroj pravdy,
- úplná historie,
- jednoduché verzování,
- připravenost pro Codex,
- odstranění duplicitních verzí ve zdrojích.

### Dopady

Každý nový balíček dokumentace obsahuje Git příkaz pro commit a push. Platný konečný stav je vždy stav v hlavní větvi repozitáře.
