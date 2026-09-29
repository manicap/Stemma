# Architektonická rozhodnutí

**Dokument:** 12  
**Verze:** 0.7
**Stav:** platný registr rozhodnutí  
**Datum vytvoření:** 15. 7. 2026  
**Datum revize:** 29. 9. 2026

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

---

## ACP-008 — Globální aplikační shell a sekční navigace

**Stav:** Schváleno

### Kontext

Dosavadní RC obrazovka byla záměrně person-centric a používala seznam osob
vlevo a detail vpravo jako jediný hlavní pohled. Stemma však dlouhodobě
zahrnuje i celorodinné oblasti, které nejsou kontextem jedné osoby. Seznam
osob proto nesmí plnit současně roli globální navigace celé aplikace.

### Rozhodnutí

Stemma používá stabilní globální aplikační shell. Kořenová URL patří Přehledu;
globální navigace odděluje Přehled, Osoby, Rodokmen, Dokumenty, Místa,
Materiály / zdroje a Můj prostor. Osoby zůstávají samostatnou pracovní sekcí
s kontextovým seznamem vlevo a detailem vpravo. Neimplementované oblasti jsou
jasně označené jako plánované a nesmějí prezentovat falešná data nebo funkce.

Shell zůstává server-rendered a progresivní interakce v sekci Osoby nadále
používají HTMX podle ACP-003. Na mobilu jsou globální navigace, seznam osob a
detail samostatně použitelné vrstvy; aplikace se nesnaží zobrazit tři sloupce
vedle sebe.

### Důvod

- oddělit globální informační architekturu od person-centric kontextu,
- vytvořit stabilní základ pro budoucí celorodinné moduly bez jejich předčasné
  implementace,
- zachovat fungující list/detail tok Osob i stávající bezpečnostní hranice,
- umožnit jednotný responzivní a tematický designový systém celé aplikace.

### Dopady

- `/` je Přehled a pracovní seznam osob je na `/osoby/`; existující detailové
  URL `/osoby/<id>/` zůstávají stabilní,
- globální navigace je součástí sdílené základní šablony, nikoli seznamu osob,
- Přehled smí zobrazit pouze skutečná data filtrovaná pro aktuálního actora,
- výchozí motiv je tmavý; explicitní dark/light volba se zatím ukládá lokálně
  v prohlížeči a později se začlení do uživatelského Nastavení,
- ACP nemění datový model, přístupovou policy ani význam doménových hodnot.

---

## ACP-009 — Invalidačně řízená vývojová brána

**Stav:** Schváleno

### Kontext

ACP-006 schválil autonomní agentní režim na větvi `agent/rc-0.1`, ale jeho
původní provedení vedlo k plošnému opakování celé testovací sady, systémové a
migrační kontroly i všech review po každém dílčím kroku. Pořadí workflow samo o
sobě přitom nemění vstupy již úspěšné kontroly. Opakování bez změny relevantního
vstupu prodlužuje zpětnou vazbu, aniž by zvyšovalo průkaznost výsledku.

Projekt zatím nemá CI ani samostatný nástroj pro sestavení gate. Závazný
prováděcí kontrakt proto zůstává v `AGENTS.md` a musí být s tímto rozhodnutím
konzistentní.

### Rozhodnutí

Validační a review část ACP-006 se mění na stupňovitou invalidation-based gate:

- úspěšný výsledek kontroly zůstává platný, dokud se nezmění její relevantní
  vstup,
- kontrola se neopakuje pouze kvůli pořadí kroků workflow,
- nejdražší kontroly běží až nad stabilním diffem,
- klasifikace změny určuje povinné testy, systémové kontroly a review,
- nejasný nebo sdílený dopad se klasifikuje přísněji,
- explicitní acceptance kritérium nebo pokyn uživatele může vždy požadovat
  přísnější bránu.

Podrobné úrovně 0–5, invalidační matice a review matice jsou závazně popsány v
`AGENTS.md`. Bezpečnostní review a odpovídající testy zůstávají povinné pro
permissions, actor-aware API, health data, auth/session/CSRF, lifecycle,
file/storage delivery, chráněné přímé HTTP URL a visibility filtry.

Finální acceptance brána RC 0.1 v `07_ROADMAPA.md` se tímto rozhodnutím nemění.
Optimalizace se týká průběžných řezů a oprav; nesnižuje požadavky stanovené pro
uzavření release nebo milníku.

### Důvod

- zachovat stejnou bezpečnostní a testovací jistotu s menším počtem redundantních
  běhů,
- zkrátit zpětnou vazbu během implementace,
- oddělit levné focused ověření od jedné finální brány nad stabilním diffem,
- provádět specializované review tehdy, když je skutečně invaliduje obsah změny.

### Dopady

- ACP-009 upravuje pouze validační a review orchestraci ACP-006; jeho rozsah
  autonomie, eskalační hranice, ochrana větví a zákaz neautorizovaných změn
  zůstávají v platnosti,
- pro autonomní workflow nahrazuje starší dopad ACP-005, který požadoval v
  každém dokumentačním balíčku Git příkaz a označoval hlavní větev za jediný
  platný konečný stav; autoritativní je pushnutý stav aktuální schválené pracovní
  větve a příkazy se ve výstupu uvádějí jen na vyžádání,
- Markdown-only změna sama neinvaliduje Django testy, systémovou ani migrační
  kontrolu; dokumentační oprava po review neruší dřívější PASS executable diffu,
- test-only změna vyžaduje celou sadu jen při dopadu na sdílené fixtures,
  helpery, settings, discovery nebo globální stav,
- změna modelu invaliduje migrační kontrolu, změna permissions bezpečnostní
  review a změna query shape query-count/N+1 ověření,
- po lokální opravě se opakuje pouze dotčená kontrola a relevantní reviewer,
  pokud oprava nezasáhne další doménu,
- samostatný `docs/13_PRACOVNI_POSTUP_LLM.md` nevzniká, protože by duplikoval
  závazný kontrakt v `AGENTS.md`, tento registr a existující procesní dokumenty,
- automatizace gate, CI, test tags, Ruff a nový test runner zůstávají možnými
  budoucími optimalizacemi a nejsou součástí tohoto rozhodnutí ani řezu.

---

## ACP-010 — Archivace a obnovení archivovaného zdravotního záznamu

**Stav:** Schváleno

### Kontext

Společný `LifecycleModel` poskytuje technická pole archivace a měkkého
odstranění, ale neurčuje povolené přechody jednotlivých domén. `HealthRecord`
dosud nemá zapisovací lifecycle API a běžné actor-aware selectory archivované i
měkce odstraněné záznamy záměrně skrývají. Bez výslovného kontraktu by budoucí
implementace musela domýšlet význam obnovy, oprávnění, chybové rozhraní,
concurrency i dopad na zdravotní přílohy a zdroje.

### Rozhodnutí

Obecným principem zůstává, že archivace a měkké odstranění jsou odlišné
lifecycle operace a metadata aktuálního stavu nejsou historickým auditním
logem. Pro `HealthRecord` se schvalují tři vzájemně výlučné logické stavy:

- `ACTIVE`: `archived_at IS NULL` a `deleted_at IS NULL`,
- `ARCHIVED`: `archived_at IS NOT NULL` a `deleted_at IS NULL`,
- `SOFT_DELETED`: `archived_at IS NULL` a `deleted_at IS NOT NULL`.

Nové health lifecycle API nesmí vytvořit stav s oběma časovými poli
neprázdnými, přestože jej současné databázové schéma technicky nezakazuje.
Nyní jsou schváleny pouze ne-idempotentní přechody `ACTIVE -> ARCHIVED` přes
`archive_health_record(...)` a `ARCHIVED -> ACTIVE` přes jednoznačně nazvané
`restore_archived_health_record(...)`. Obecné neurčité označení `restore` se
pro health nepoužije.

Obě budoucí operace musí přijmout explicitní kontext osoby a actora. Vyžadují
čerstvě načteného uloženého aktivního actora se stávající permission
`health.change_healthrecord`, platnou aktivní a actorovi dostupnou osobu,
záznam patřící právě této osobě, obsahový přístup podle centralizované health
policy a aktivní `HealthRecordType`. Samotná modelová permission, autorství ani
`is_staff` přístup nerozšiřují; aktivní superuser se řídí stávající centrální
policy. Archivovaná, měkce odstraněná nebo neviditelná osoba lifecycle zápis
neumožní.

Operace musí proběhnout atomicky nad čerstvým uzamčeným řádkem a před zápisem
znovu ověřit authorization i lifecycle preconditions. Interní lifecycle-aware
loader nebo rovnocenná bezpečná hranice smí načíst skrytý fyzický řádek jen v
již autorizovaném kontextu konkrétní osoby; běžný selector není loaderem
archivovaného cíle. Actor nebo chybějící permission vedou k
`PermissionDenied`. Skrytý, cizí, fyzicky chybějící nebo jinak
neautorizovatelný cíl vede jednotně k `HealthRecord.DoesNotExist`; stejně se
na této lifecycle hranici normalizuje neplatný, neaktivní nebo nepřístupný
kontext osoby a nesoulad osoby se záznamem. Teprve po
bezpečné autorizaci cíle vrací nesprávný výchozí stav `ValidationError` se
stabilním kódem `health_record_not_active` pro archive nebo
`health_record_not_archived` pro restore archived. Tím se existence cíle
neprozrazuje.

Archive smí měnit pouze `archived_at`, `archived_by`, volitelný
`archive_reason` a standardní `updated_at`. Důvod se ukládá po oříznutí
vnějšího whitespace; chybějící nebo prázdný důvod je `""`.
`restore_archived_health_record(...)` přijímá pouze přesně stav `ARCHIVED`,
nastaví `archived_at = NULL`, `archived_by = NULL`, `archive_reason = ""` a
aktualizuje `updated_at`. `archived_by` označuje actora aktuální archivace,
nikoli historii; `created_by` se nikdy nemění.

Oba přechody jsou vůči `HealthRecordAttachment`, `HealthRecordSource`,
`Attachment` a `Source` striktně non-cascade: nemění jejich pole ani lifecycle,
nevytvářejí a nemažou vazby. Po archivaci běžné health selectory skryjí rodiče,
a proto přes běžnou prezentaci také jeho materiály. Po obnovení se záznam i
nezměněné aktivní vazby znovu řídí standardními selectory.

Přechody `ACTIVE -> SOFT_DELETED`, `ARCHIVED -> SOFT_DELETED`,
`SOFT_DELETED -> ACTIVE` a `SOFT_DELETED -> ARCHIVED` nejsou schváleným
implementačním scope. Soft-delete bude případná samostatná operace s vlastním
názvem, permission a rozhodnutím o vratnosti; `health.delete_healthrecord` je
jen předběžný kandidát, nikoli schválený kontrakt. Toto ACP nedefinuje URL,
POST endpoint, HTMX odpověď, redirect, tlačítko ani potvrzovací dialog.

### Důvod

- oddělit archivaci od měkkého odstranění a odstranit nejednoznačnost obnovy,
- zachovat existující centralizovanou health access policy i fail-closed
  chování přímých identifikátorů,
- zabránit konfliktům a TOCTOU při souběžných lifecycle zápisech,
- zachovat přílohy a zdroje jako samostatné objekty bez skrytého cascade,
- připravit přesný backendový kontrakt bez předčasného návrhu transportu.

### Nevýhody

- vzájemná výlučnost stavů zůstává do případného samostatně schváleného
  databázového constraintu vynucená pouze novým aplikačním API; starší přímý
  ORM zápis může stále vytvořit kombinovaný neplatný stav,
- bezpečný lifecycle-aware loader skrytého cíle zvyšuje citlivost a testovací
  náročnost backendové implementace oproti použití běžného selectoru.

### Dopady

- navazující backendový řez musí vytvořit actor-aware use-cases a bezpečnou
  interní hranici pro skrytý lifecycle target podle tohoto kontraktu,
- běžné create/update Health UI ani read selectory se tímto dokumentačním
  rozhodnutím nemění,
- historie přechodů bude patřit do budoucí auditní infrastruktury, nikoli do
  aktuálních archive metadata,
- databázový constraint, migrace, nové permission, HTTP a UI v tomto řezu
  nevznikají,
- soft-delete a jeho případná obnova zůstávají explicitně odloženým
  architektonickým rozhodnutím.
