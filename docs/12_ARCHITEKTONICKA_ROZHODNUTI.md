# Architektonická rozhodnutí

**Dokument:** 12  
**Verze:** 0.4
**Stav:** platný registr rozhodnutí  
**Datum vytvoření:** 15. 7. 2026  
**Datum revize:** 17. 8. 2026

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

---

## ACP-006 — Experimentální autonomní agentní vývojový režim

**Stav:** Schváleno

### Kontext

Dosavadní implementace byla řízena velmi malými ručně zadávanými kroky. Tento postup poskytoval vysokou kontrolu, ale zároveň přesouval značnou část orchestrace vývoje na uživatele a oddaloval okamžik, kdy lze aplikaci ověřit jako skutečně použitelný celek.

Pro ověření agentního způsobu práce byla z aktuálního stavu `feature/mvp` vytvořena experimentální větev `agent/rc-0.1`. Původní stav je zachován ve `feature/mvp` a v návratovém bodu `backup/pre-agent-2026-08-17`.

### Rozhodnutí

Na větvi `agent/rc-0.1` se vývoj řídí cílovým stavem **RC 0.1** definovaným v `07_ROADMAPA.md`, nikoli nutností ručně schvalovat každý dílčí implementační krok.

Hlavní agent na této větvi smí bez rutinního potvrzování uživatelem:

- ověřit skutečný stav implementace proti dokumentaci,
- zvolit nejmenší další bezpečný vertikální řez směrem k RC 0.1,
- implementovat vratná řešení v rámci schválené architektury,
- doplnit a spouštět testy a povinné kontroly,
- používat subagenty nebo oddělené kontrolní průchody pro dokumentaci, QA, bezpečnost a UI/UX,
- opravit zjištěné vady a znovu provést ověření,
- aktualizovat existující dokumentaci, pokud implementace materiálně změnila stav projektu,
- po úspěšném ověření vytvořit koherentní commit a pushnout jej na `origin/agent/rc-0.1`,
- pokračovat dalším řezem bez čekání na nový uživatelský pokyn.

Agent nesmí bez explicitního souhlasu uživatele:

- měnit schválenou architekturu nebo existující ACP,
- měnit význam systémových hodnot, bezpečnostní politiku nebo pravidla přístupových práv,
- provádět destruktivní či nevratné operace nad reálnými daty,
- nasazovat nebo měnit reálné produkční prostředí,
- používat force-push nebo přepisovat sdílenou historii,
- mergeovat nebo rebasovat `agent/rc-0.1` do `feature/mvp` či `main`,
- posouvat nebo používat `backup/pre-agent-2026-08-17` jako pracovní větev.

Při skutečném rozporu autoritativní dokumentace, chybějícím materiálním produktovém nebo bezpečnostním rozhodnutí, potřebě nového ACP, destruktivním zásahu nebo nevyřešitelném validačním bloku agent práci zastaví a eskaluje jedno souhrnné rozhodnutí uživateli.

### Důvod

- snížit množství rutinní orchestrace přenesené na uživatele,
- průběžně směřovat k uživatelsky ověřitelnému výsledku místo pouze k interním milníkům,
- zachovat dokumentově řízený vývoj a schválené architektonické hranice,
- oddělit implementaci od nezávislé kontroly,
- umožnit experiment kdykoli ukončit bez zásahu do původní pracovní větve.

### Dopady

- `AGENTS.md` je na `agent/rc-0.1` závaznou exekuční politikou a konkretizuje pracovní smyčku a eskalační hranice tohoto ACP.
- `07_ROADMAPA.md` obsahuje měřitelnou definici RC 0.1 a jeho non-goals.
- Agent může na experimentální větvi volit vertikální řezy přes více původních fází roadmapy, pokud respektuje jejich schválené závislosti; tím se automaticky nemění stav nedokončených milníků.
- Dokončení RC 0.1 neznamená dokončení celé Stemmy ani automatické schválení produkčního nasazení.
- `feature/mvp` zůstává zachovaným non-agentním vývojovým základem, dokud uživatel výslovně nerozhodne o integraci výsledků experimentu.

---

## ACP-007 — Neprozrazující odvozování prezentačních údajů

**Stav:** Schváleno

### Kontext

Věk, stav žijící/zemřelý, římské pořadí a podobné údaje nejsou samostatnými
uloženými fakty. Vznikají z osob, událostí a dalších zdrojových záznamů, které
mají vlastní přístupovou úroveň a lifecycle. Globální odvození by mohlo
nepřímo potvrdit existenci chráněné osoby nebo události.

### Rozhodnutí

Odvozený údaj zobrazený konkrétnímu actorovi smí vycházet pouze ze zdrojových
osob, událostí a dalších záznamů, které jsou tomuto actorovi samy viditelné
podle aktuální access a lifecycle policy.

Skrytá skutečnost nesmí být nepřímo prozrazena věkem, stavem
žijící/zemřelý, římským pořadím ani jiným odvozeným údajem. Prezentační
římské pořadí se proto počítá pouze ve viditelné kohortě a může se podle
oprávnění actora lišit. Tyto hodnoty se neukládají jako vlastnosti osoby.

### Důvod

- zachovat serverovou autorizaci i při agregaci a odvozování,
- zabránit úniku existence skrytých osob a událostí přes mezery v pořadí,
  věk nebo životní stav,
- udržet jeden bezpečnostní princip pro současné i budoucí derived hodnoty.

### Dopady

- každý veřejný selector odvozených údajů musí nejprve uplatnit aktuální
  access a lifecycle policy na všechny zdroje,
- archivovaný nebo měkce odstraněný zdroj se v běžném RC detailu nepoužije,
- stejná osoba může mít pro různé actory jiný prezentační stav nebo římskou
  číslici, pokud mají rozdílnou viditelnost zdrojů,
- při nejednoznačných nebo neúplných viditelných zdrojích se zobrazí pouze
  údaj, který lze spolehlivě odvodit bez falešné přesnosti.
