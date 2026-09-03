# Rodinná databáze – dokumentace projektu

**Verze dokumentace:** 0.33
**Stav:** RC 0.1 a M2 dokončeny; zahájena infrastruktura `materials`
**Datum revize:** 3. 9. 2026

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

## Stav verze 0.33

Verze 0.33 přidává actor-aware zdroje konkrétního `Residence`:

- cesta kontroluje bydliště, jeho osobu, zdrojovou vazbu i zdroj,
- archivované bydliště zůstává historicky čitelné a lifecycle osoby respektuje
  její explicitní oprávnění,
- sdílený zdroj neodhalí chráněné bydliště a připojené místo není samostatnou
  autorizační vrstvou.

## Stav verze 0.32

Verze 0.32 přidává actor-aware přílohy konkrétního `Residence`:

- cesta kontroluje bydliště, jeho osobu, vazbu přílohy i přílohu,
- archivované bydliště zůstává historicky čitelné, odstraněné nikoli; lifecycle
  osoby respektuje její explicitní oprávnění,
- vydají se pouze aktivní přílohy ve stavu `available` a sdílená příloha
  neodhalí chráněné bydliště.

## Stav verze 0.31

Verze 0.31 přidává actor-aware přílohy konkrétního `Relationship`:

- cesta kontroluje vztah, obě propojené osoby, vazbu přílohy i přílohu,
- archivovaný vztah zůstává historicky čitelný, odstraněný vztah nebo osoba
  cestu uzavře a archivovaná osoba vyžaduje explicitní permission,
- vydají se pouze aktivní přílohy ve stavu `available` a sdílená příloha
  neodhalí vztah se skrytým účastníkem.

## Stav verze 0.30

Verze 0.30 přidává actor-aware zdroje konkrétního `Relationship`:

- cesta kontroluje vztah, obě propojené osoby, zdrojovou vazbu i zdroj,
- archivovaný vztah zůstává historicky čitelný, odstraněný nikoli; archivovaná
  osoba vyžaduje explicitní permission a odstraněná osoba cestu vždy uzavře,
- sdílený zdroj neodhalí vztah se skrytým účastníkem.

## Stav verze 0.29

Verze 0.29 rozšiřuje kontextové actor-aware čtení zdrojů na `Event`:

- permissionless historie vrací nesmazané vazby konkrétní události,
- autorizovaná varianta vyžaduje viditelnou aktivní událost a filtruje access
  i lifecycle vazby a zdroje,
- sdílený zdroj nezpřístupní chráněnou událost a celý kontext se načítá bez
  N+1.

## Stav verze 0.28

Verze 0.28 přidává první actor-aware čtení zdrojů v kontextu `PersonName`:

- permissionless selector zachovává interní historii nesmazaných vazeb,
- actor-aware selector současně kontroluje osobu, konkrétní jméno, vazbu a
  zdroj včetně access a lifecycle celé cesty,
- jiná viditelná vazba ke stejnému zdroji nezpřístupní ani nepotvrdí chráněné
  jméno; obecný selector podle `Source.id` nevzniká.

## Stav verze 0.27

Verze 0.27 doplňuje interní transakční zápisy zdrojových vazeb:

- typované create/update služby pokrývají všech šest explicitních cílů,
- endpointy, zdroj, role i autor se načítají znovu a zápis respektuje jejich
  lifecycle a aktivitu role,
- služby samy neudělují actor oprávnění; případné budoucí aplikační volání
  musí autorizovat původní kontext i každý měněný endpoint.

## Stav verze 0.26

Verze 0.26 přidává integritní základ explicitních zdrojových vazeb:

- šest samostatných modelů propojuje `Source` s `PersonName`, `Event`,
  `Relationship`, `Residence`, `GraveSite` a `Attachment`,
- vazba ukládá `SourceRole`, citovanou část, úryvek, výklad a povinnou pevnou
  sílu podpory; nevzniká generický vztah,
- migrace `materials.0006_source_links` neobsahuje seed data a vazby zatím
  nejsou vystavené adminem, službou, selectorem ani UI.

## Stav verze 0.25

Verze 0.25 přidává konkrétní metadata znovupoužitelného zdroje:

- `Source` vyžaduje pouze `SourceType` a neprázdný název; ostatní
  bibliografická pole mohou zůstat neúplná,
- historický nebo publikační údaj používá společný model neúplného data a
  zdroj nese vlastní access, autorství a lifecycle bez globálního hodnocení
  důvěryhodnosti,
- migrace `materials.0005_sources` vytváří jedinou tabulku `Source` bez seed
  dat, vazeb nebo nových systémových hodnot,
- model zatím není registrován v adminu ani vystaven v UI; bezpečné čtení
  vznikne až kontextem explicitní vazby na cílový doménový objekt.

## Stav verze 0.24

Verze 0.24 zahajuje zdroje dvěma prázdnými rozšiřitelnými katalogy:

- `SourceType` klasifikuje druh znovupoužitelného informačního pramene a
  `SourceRole` význam zdroje vůči konkrétnímu propojenému objektu,
- migrace `materials.0004_source_lookups` je čistě strukturální a nevkládá
  neschválené systémové hodnoty,
- globální důvěryhodnost zdroje se v této etapě nemodeluje a kontextová vazba
  nesmí přes jiný přístupný cíl prozradit chráněný objekt,
- konkrétní `Source`, bibliografická pole a explicitní vazby následují v
  samostatných řezech.

## Stav verze 0.23

Verze 0.23 rozšiřuje bezpečné kontextové čtení příloh na události:

- permissionless selector vrací interní historii nesmazaných vazeb události,
- actor-aware selector vyžaduje viditelnou, nearchivovanou a nesmazanou
  událost a současně access a lifecycle vazby i přílohy se stavem `available`,
- osoba i událost používají stejné centrální actor semantics a výsledkové
  dotazy přednačítají související metadata bez N+1,
- selector nevydává soubor ani storage URL a budoucí doručení musí konkrétní
  kontext znovu autorizovat.

## Stav verze 0.22

Verze 0.22 přidává první bezpečné kontextové čtení příloh osoby:

- permissionless selector zpřístupňuje interní historii vazeb bez produktové
  URL a actor-aware selector kombinuje access osoby, vazby a přílohy,
- běžný výsledek vyžaduje nearchivovanou a měkce neodstraněnou vazbu i
  přílohu a fyzický stav `available`; lifecycle vstupní osoby zachovává
  existující oprávnění,
- šest explicitních vazeb příloh ke stávajícím doménám má strukturální migraci
  a transakční create/update služby,
- zdroje, ostatní actor-aware kontexty, upload, doručení a UI zůstávají
  navazujícími řezy.

## Stav verze 0.21

Verze 0.21 přidává explicitní vazby příloh ke stabilnímu M2 jádru:

- šest modelů propojuje `Attachment` s osobou, událostí, vazbou, bydlištěm,
  hrobovým místem nebo místem bez generického vztahu,
- vazby mají vlastní access, autorství a lifecycle a používají `PROTECT`,
- transakční služby vynucují schválená create/update lifecycle pravidla z
  čerstvého databázového stavu,
- osoba smí mít nejvýše jednu primární vazbu s `deleted_at IS NULL`; příznak
  sám neprohlašuje přílohu za fotografii,
- nevzniká doručovací URL, selector, admin, UI ani katalogová seed hodnota.

## Stav verze 0.20

Verze 0.20 přidává schválený metadata model jedné fyzické přílohy:

- pevný `FileStatus` rozlišuje `pending`, `available`, `missing` a
  `quarantined`; pouze `available` smí být v budoucnu doručován,
- `Attachment` ukládá kategorii, popisná metadata, unikátní neprůhledný
  `storage_key`, MIME typ, velikost, indexovaný neunikátní SHA-256, technická
  JSON metadata, neúplné datum, access, autorství a lifecycle,
- konkrétní storage backend, upload služba, přímé doručení, vazby, selectory,
  admin a UI v tomto řezu nevznikají,
- strukturální migrace `materials.0002_attachments` a cílené testy ověřují
  pole, validaci, constrainty, nezávislost file statusu a lifecycle i
  fail-closed absenci adminu.

## Stav verze 0.19

Verze 0.19 zahajuje navazující infrastrukturní milník bezpečným scaffoldem:

- založena a registrována Django aplikace `materials`,
- `AttachmentCategory` a `AttachmentRole` jsou prázdné, uživatelsky
  rozšiřitelné katalogy nad společným `LookupModel`,
- strukturální migrace `materials.0001_attachment_lookups` nevkládá žádné
  neschválené systémové hodnoty a oba katalogy spravuje admin se společnou
  ochranou identity systémových řádků,
- cílené testy hlídají registraci, přesnou strukturu, migraci a admin guard,
- aplikace zatím záměrně neobsahuje přílohu, zdroj, vazby, služby, selectory,
  souborové úložiště ani UI.

## Stav verze 0.18

Verze 0.18 zaznamenává skutečné uzavření infrastrukturního milníku M2:

- audit konkrétních modelů, číselníků, migrací, constraintů, modelové
  validace, služeb, selectorů a testů potvrdil jádro Person, Place,
  Event/EventParticipant/DeathDetail a Relationship,
- všechny existující aplikační zápisy M2 entit procházejí doménovou hranicí;
  nepřipravené business admin plochy zůstávají read-only nebo fail-closed,
- aplikační čtení osob a odvozených údajů používá centrální actor-aware
  access/lifecycle policy a žádná slabší paralelní veřejná cesta nebyla
  nalezena,
- poslední skutečnou mezeru uzavřel `DeathDetail` v commitu `21c5cc1`; plná
  brána poté prošla 1 083 testy, kontrolou systému a kontrolou migrací,
- nejbližším dalším infrastrukturním milníkem jsou jednou ukládané přílohy a
  zdroje s explicitními vazbami na stabilní M2 jádro; jejich implementace v
  tomto stavovém řezu nezačíná.

## Stav verze 0.17

Verze 0.17 zavádí schválený UI foundation podle ACP-008:

- kořenová URL zobrazuje actor-specific Přehled a sekce Osoby se přesouvá na
  `/osoby/` při zachování stávajících detailových URL,
- stabilní globální navigace odděluje konkrétní pracovní sekci od kontextového
  list/detail pohledu uvnitř Osob,
- budoucí Rodokmen, Dokumenty, Místa, Materiály / zdroje a Můj prostor jsou
  pouze jasně označené plánované oblasti bez falešných dat nebo funkčnosti,
- výchozí je tmavý modrošedý motiv; light mode zůstává plnohodnotný a lokální
  preference se zachovává mezi návštěvami,
- browser review ověřil nový shell na desktopu 1440×900, tabletovém mezistupni
  768×900 a mobilu 390×844, oba motivy, samostatné drawery a absenci
  horizontálního overflow,
- úplná projektová brána prošla 1020 testy, systémovou kontrolou, kontrolou
  migrací a nezávislými QA, security a UI/dokumentačními review,
- datový model, oprávnění, selector/service kontrakty ani existující ACP se
  nemění.

## Stav verze 0.16

Verze 0.16 uzavírá kontrolní bránu experimentálního RC 0.1:

- skutečný browser průchod ověřil anonymní stav, Čtenáře a Editora,
  actor-specific seznam/detail, login, serverovou validaci, HTMX uložení a
  logout,
- desktop 1280×720 i mobil 390×844 prošly list/detail tokem, mobilním panelem
  bez horizontálního overflow a světlým i tmavým motivem,
- Čtenář nemá editační akci a jeho přímý pokus o editační URL končí 403,
- projektová brána prošla 1012 testy, systémovou kontrolou, kontrolou migrací,
  nezávislým QA a security review i kontrolou diffu a artefaktů,
- RC 0.1 je připraven pouze na `agent/rc-0.1`; produkční nasazení ani merge
  do `feature/mvp` nebo `main` tím nejsou schváleny.

## Stav verze 0.15

Verze 0.15 doplňuje bezpečné odvozené údaje seznamu a detailu osoby:

- schválený ACP-007 zakazuje odvozovat prezentovaný údaj ze zdroje, který
  aktuální actor sám nevidí,
- selector za běhu počítá viditelné narození, úmrtí, spolehlivý věk, životní
  stav a římské pořadí bez ukládání těchto hodnot na osobu,
- neúplná data nezískávají falešnou přesnost, duplicitní životní události se
  neřeší náhodným výběrem a skrytý jmenovec nevytváří mezeru v pořadí,
- `seed_demo_data` poskytuje dvě shodně pojmenované osoby a tři životní
  události pro ruční ověření data, věku, stavu a římských číslic.

## Stav verze 0.14

Verze 0.14 doplňuje reprodukovatelný lokální bootstrap rolových identit:

- interaktivní příkaz `bootstrap_demo_accounts` funguje pouze s `DEBUG=True`,
- vytvoří nebo resetuje vyhrazeného Čtenáře, Editora a Správce a opraví jim
  přesné skupiny, přímá oprávnění i neprivilegované stavové příznaky,
- heslo zadává tester skrytě a potvrzuje je; příkaz je nevypisuje ani neukládá
  v otevřené podobě do zdrojů a používá standardní Django validátory,
- opakované spuštění nevytváří duplicity a slouží jako jednoznačný lokální
  reset přihlašovacích údajů.

## Stav verze 0.13

Verze 0.13 doplňuje jednoduchou editaci osoby pro RC 0.1:

- Editor a Správce mohou z viditelného detailu otevřít formulář základních
  údajů a uložit jej přes transakční doménovou službu,
- server znovu vynucuje viditelnost objektu, aktuální stav účtu,
  `people.change_person`, CSRF a povolené HTTP metody,
- RC formulář nemění přístupovou úroveň, stav ověření, lifecycle ani údaje
  narození a úmrtí; klientsky podstrčené hodnoty se ignorují,
- HTMX po uložení aktualizuje detail i odpovídající položku seznamu,
  validace zůstává u formuláře a rozpracované změny jsou chráněné varováním,
- úplný browser průchod zůstává před závěrečným uzavřením oblastí D, E a G.

## Stav verze 0.12

Verze 0.12 doplňuje autentizační a rolový základ RC 0.1:

- horní lišta nabízí anonymnímu uživateli přihlášení a přihlášenému účtu
  identitu a bezpečné POST odhlášení,
- přihlášení zachovává pouze bezpečný lokální návratový cíl a neaktivní účet
  se nemůže přihlásit,
- role Čtenář zůstává pouze pro čtení, zatímco Editor a Správce získávají
  konkrétní `people.change_person` pro navazující editační průchod,
- seznam po přihlášení okamžitě respektuje centrální obsahovou policy;
  úplné browser ověření login–edit–logout zůstává součástí dokončení RC.

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
.\.venv\Scripts\python.exe manage.py bootstrap_demo_accounts
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
python manage.py bootstrap_demo_accounts
python manage.py runserver
```

Aplikace je poté dostupná na `http://127.0.0.1:8000/`.

`seed_demo_data` vytváří pět jednoznačně označených syntetických osob pro
veřejnou, přihlášenou a omezenou úroveň. Dvě veřejné osoby jménem Josef
Dvořák mají tři označené životní události, takže v seznamu a detailu lze
ověřit římské pořadí, narození, úmrtí, stav i spolehlivě odvozený věk.
Příkaz funguje pouze s lokálním
`DEBUG=True`; mimo tento režim selže bez zápisu. Opakované spuštění při
zachování vložených markerů nevytváří duplicity, existující ukázkové záznamy
nepřepisuje a nic nemaže. Plán lze bez zápisu zkontrolovat příkazem
`python manage.py seed_demo_data --dry-run`.

`bootstrap_demo_accounts` následně interaktivně vyžádá jedno nové lokální
heslo a jeho potvrzení. Heslo se při psaní nezobrazuje, nepatří do argumentu
příkazu ani do repozitáře a musí projít standardními Django validátory. Příkaz
vytvoří nebo resetuje tyto lokální identity:

- Čtenář: `stemma-demo-reader`,
- Editor: `stemma-demo-editor`,
- Správce: `stemma-demo-administrator`.

Každé další spuštění stejným postupem bezpečně nastaví nové heslo všem třem
účtům a opraví jejich skupiny, systémovou oprávňovací matici i přímá oprávnění.
Příkaz funguje pouze s lokálním
`DEBUG=True`; vyhrazená uživatelská jména ani zadané heslo se nesmějí používat
v produkčním prostředí.

## Aktuální fáze projektu

- Návrh UI/UX je uzavřen jako schválený pracovní základ.
- Databázový a technický návrh je dokončen jako schválený pracovní základ.
- M0, M1 a M2 jsou na `agent/rc-0.1` skutečně dokončené; `feature/mvp`
  zůstává nedotčeným pre-agentním integračním základem.
- Pro ověření autonomního agentního vývoje běží oddělený experiment v `agent/rc-0.1` podle ACP-006.
- RC 0.1 je na experimentální větvi připravené podle `07_ROADMAPA.md`; tento
  stav ani dokončení M2 nepovolují produkční nasazení nebo merge.
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
