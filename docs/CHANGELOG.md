# Historie změn dokumentace

## Verze 0.42 – 17. 8. 2026

- přidán `PersonForm` pro jméno, příjmení, pohlaví, kategorii a poznámku;
  bezpečnostní metadata ani údaje narození a úmrtí nevystavuje,
- doplněn transakční `update_person()` s `select_for_update()`, čerstvým
  actorem a cílem, opakovanou permission/visibility kontrolou, modelovou
  validací a zachováním security, lifecycle i technických metadat,
- edit view kombinuje objektovou viditelnost s aktuálním
  `people.change_person`, CSRF a omezením HTTP metod; skrytý cíl neprozradí,
- HTMX úspěch obnoví detail i položku seznamu přes OOB fragment, validační
  chyba zachová formulář a rozpracovaná editace má ochranné varování,
- cílené testy pokrývají service i webovou permission matici, tampering,
  rollback, invalidní formulář a fragmentovou aktualizaci,
- aktualizovány dokumenty 00, 02, 04, 07 a 11; modely, migrace ani ACP se
  nemění.

## Verze 0.41 – 17. 8. 2026

- doplněn standardní Django session login s bezpečným lokálním `next` a
  odmítnutím neaktivního účtu,
- horní lišta rozlišuje anonymní přihlášení a identitu přihlášeného účtu;
  logout je pouze CSRF chráněný POST,
- nová datová migrace přiřazuje konkrétní `people.change_person` rolím
  Editor a Správce, zatímco Čtenář zůstává pouze pro čtení,
- cílené testy pokrývají login, externí návratovou URL, invalidní a neaktivní
  účet, logout, CSRF a obsahové rozdíly rolí,
- aktualizovány dokumenty 00, 02, 04 a 07; modelová pole ani ACP se nemění.

## Verze 0.40 – 17. 8. 2026

- doplněn jednoznačný postup čistého lokálního spuštění pro Windows,
  Linux a macOS od Pythonu 3.14 přes `venv`, instalaci, lokální tajný klíč,
  migrace a vývojový server,
- přidán bezpečný lokální příkaz `seed_demo_data` se třemi syntetickými
  osobami pro veřejnou, přihlášenou a omezenou úroveň a režimem `--dry-run`;
  při `DEBUG=False` příkaz selže bez zápisu,
- příkaz existující ukázkové záznamy nepřepisuje, nic nemaže a nevytváří
  účty, hesla ani jiná tajemství,
- zápis ukázkových osob používá novou validační doménovou hranici
  `PersonInput` + `create_person()` v transakci,
- izolovaný Windows clean-snapshot smoke test ověřil nový venv, instalaci,
  migrace, dry-run, opakovanou idempotenci, systémovou kontrolu a HTTP 200
  skutečného vývojového serveru; POSIX kroky prošly statickou kontrolou,
- aktualizovány dokumenty 00, 07 a 11; modely, migrace ani ACP se nemění.

## Verze 0.39 – 17. 8. 2026

- přidány autorizované selectory `get_visible_people(*, actor)` a
  `get_visible_person(*, person_id, actor)` pro výchozí RC seznam a detail,
- oba průchody respektují centrální access policy a standardně vylučují
  archivované i měkce odstraněné osoby,
- neexistující a neviditelná osoba mají shodnou HTTP 404 odpověď pro plnou
  stránku, HTMX i přímou URL,
- hlavní obrazovka nyní čte skutečná data přes Django views a templates,
- doplněn dvousloupcový desktopový základ, mobilní vysouvací seznam,
  světlý a tmavý motiv a běžné empty, loading a error stavy,
- list/detail průchod byl ověřen v reálném browseru na desktopu i mobilním
  viewportu včetně opakované HTMX výměny a zavření mobilního panelu,
- HTMX 2.0.10 je lokálně verzovaný v projektové statice s BSD licencí,
- Person i navazující `PersonName` a `Relationship` v Django Adminu
  respektují viditelnost vlastního záznamu a propojených osob a jsou do
  zavedení doménové editační služby pouze pro čtení,
- roadmapa výslovně ponechává oblasti B, C a G částečné do odvozených
  údajů, login/editace a úplného browser ověření navazujícího RC průchodu,
- aktualizovány dokumenty 00, 02, 04, 07 a 11; nové ACP ani migrace
  nevznikly.

## Verze 0.38 – 17. 8. 2026

- založen oddělený experimentální vývojový směr `agent/rc-0.1` se zachováním původního non-agentního základu `feature/mvp` a návratového bodu `backup/pre-agent-2026-08-17`,
- schválen ACP-006 pro autonomní agentní vývoj pouze na `agent/rc-0.1`,
- hlavní agent může v rámci schválené architektury samostatně volit malé vertikální řezy, implementovat je, testovat, používat nezávislé review role, opravovat nálezy a po úspěšném ověření commitovat a pushovat na agentní větev,
- explicitně zachována eskalace změn architektury a ACP, významu systémových hodnot, bezpečnostní a přístupové policy, destruktivních zásahů, produkčního nasazení a integrace do `feature/mvp` či `main`,
- `07_ROADMAPA.md` nově definuje RC 0.1 jako měřitelný end-to-end průřez se všemi povinnými acceptance kritérii a explicitními non-goals,
- RC 0.1 vyžaduje reprodukovatelné spuštění, skutečný seznam a detail osoby, login/logout a role, jednoduchou editaci základních údajů `Person`, serverovou autorizační bránu, použitelné desktopové a mobilní UI, skutečné browser ověření a úplnou kontrolní bránu projektu,
- dokončení RC 0.1 samo neznamená dokončení celé roadmapy ani povolení produkčního nasazení,
- aktualizovány `00_README.md`, `06_ROZHODNUTI_A_OTEVRENE_OTAZKY.md`, `07_ROADMAPA.md`, `12_ARCHITEKTONICKA_ROZHODNUTI.md` a kořenový `AGENTS.md` tak, aby agentní workflow a cílový stav měly jediný konzistentní kontrakt.

## Verze 0.37 – 23. 7. 2026

- přidány keyword-only autorizované selectory
  `get_visible_person_grave_site_links(*, person, actor)` a
  `get_visible_grave_site_person_links(*, grave_site, actor)` vracející
  lazy `QuerySet[PersonGraveSite]`,
- vstupní osoba nebo hrobové místo je chráněný cíl: fyzická neexistence
  zachovává `person_unsaved` či `grave_site_unsaved`, zatímco neviditelný
  existující vstup vyvolá `PermissionDenied`,
- vstupní osoba používá čerstvý access a existující lifecycle permissions;
  vstupní hrobové místo dovoluje archivaci i všechny statusy, ale odmítá
  soft-delete,
- každý výsledný řádek databázově vyžaduje viditelnou access úroveň vazby,
  osoby i hrobového místa; neviditelné řádky a protistrany se tiše
  odfiltrují,
- výsledné osoby respektují `people.view_archived_person` a
  `people.view_deleted_person`, archivované vazby a místa se vracejí a
  soft-deleted vazby či místa nikoli,
- status, verification, typ, role ani připojené `Place` se samostatně
  neautorizují,
- zachováno přesné ordering, `select_related()`, lazy vyhodnocení,
  legitimní duplicity a konstantní dotazový profil bez N+1,
- přidáno 37 cílených testů API, actor a vstupních chyb, fresh-state,
  tří access vrstev, lifecycle, filtrování, řazení, duplicit, dotazů,
  neměnnosti a permissionless regresí,
- nevznikla migrace, nový permission codename, obecný permission framework
  ani ACP.

## Verze 0.36 – 23. 7. 2026

- přidán keyword-only autorizovaný selector
  `get_visible_grave_sites(*, actor)` vracející lazy
  `QuerySet[GraveSite]`,
- selector používá centrální `can_view_access_level()` nejvýše jednou pro
  každou známou úroveň a databázový filtr `access_level__in`,
- zachován společný actor kontrakt `actor_invalid` a `actor_unsaved` i
  rozhodování podle čerstvého databázového stavu uloženého actora,
- AnonymousUser a neaktivní uživatel vidí pouze `public`, `is_staff`
  přístup nerozšiřuje, vyšší úrovně mají oddělená oprávnění a aktivní
  superuser vidí všechny,
- selector navazuje na `get_grave_sites()`, tiše filtruje neviditelné
  záznamy a zachovává zahrnutí archivovaných i vyloučení soft-deleted
  míst,
- status, ověření, typ a připojené `Place` se samostatně neautorizují,
- zachováno modelové ordering, `select_related()` a lazy konstantní
  dotazový profil bez N+1,
- doplněny testy API, actor chyb, access matice, fresh-state chování,
  lifecycle, statusů, typů, lokalizace, Place policy, řazení, laziness,
  dotazů a neměnnosti,
- nevznikla migrace, permission codename, změna centrální policy ani ACP;
  autorizované selectory `PersonGraveSite` následují v M2.7f-2.

## Verze 0.35 – 23. 7. 2026

- přidány keyword-only permissionless selectory
  `get_person_grave_site_links(*, person)` a
  `get_grave_site_person_links(*, grave_site)` vracející lazy
  `QuerySet[PersonGraveSite]`,
- vstupní osoba nebo hrobové místo musí mít PK a existující databázový
  řádek; chyby používají `person_unsaved` a `grave_site_unsaved`,
- lifecycle a status existujícího vstupu ani protistrany se nefiltrují;
  z výsledku se vylučují pouze měkce odstraněné vazby,
- zahrnuty archivované vazby, všechny access a verification hodnoty,
  aktivní, neaktivní, systémové i uživatelské role, více rolí a duplicitní
  tvrzení,
- doplněno deterministické řazení podle místa nebo osoby, role a PK,
- `select_related()` pro osobu, místo, typ místa, `Place`, roli a autora
  zachovává po validačním `exists()` jeden lazy SELECT bez N+1,
- selectory nemají actor, nevolají permission policy ani modelovou
  revalidaci, nededuplikují a nic nezapisují,
- doplněny testy API, vstupních chyb, lifecycle, access, verification,
  rolí, typů, statusů, řazení, laziness, query profilu a neměnnosti,
- nevznikla migrace, autorizovaný selector ani ACP; autorizované varianty
  následují v M2.7f.

## Verze 0.34 – 23. 7. 2026

- přidán bezparametrový permissionless `get_grave_sites()` vracející lazy
  `QuerySet[GraveSite]`,
- selector vylučuje pouze `deleted_at IS NOT NULL` a zahrnuje archivované,
  zaniklé, neveřejné a neověřené záznamy i aktivní, neaktivní, systémové a
  uživatelské typy,
- zachováno modelové řazení podle hřbitova, oddílu, řady, čísla a PK,
- `select_related()` pro typ, `Place` a autora zajišťuje jeden konstantní
  SELECT bez N+1; samotné zavolání zůstává lazy,
- selector nevaliduje historické řádky, neprefetchuje vazby osob, nevolá
  permission policy a nic nezapisuje,
- doplněny testy API, lifecycle, statusů, access, verification, typů,
  lokalizací, řazení, laziness, query profilu a neměnnosti,
- nevznikla migrace, selector `PersonGraveSite`, autorizované čtení ani
  ACP.

## Verze 0.33 – 23. 7. 2026

- přidán frozen slotted úplný snapshot `PersonGraveSiteInput` a
  keyword-only služby `create_person_grave_site()` a
  `update_person_grave_site()`,
- update může opravit osobu, hrobové místo, roli, poznámku, access i
  verification; autorství, vytvoření a lifecycle nejsou editovatelné,
- služby čerstvě načítají všechny FK a autora, používají
  `transaction.atomic()`, při update `select_for_update()` a vždy
  `full_clean()` před `save()`,
- poznámka se stripuje pouze na servisní hranici; create vyžaduje aktivní
  roli a update dovoluje zachovat stejnou neaktivní nebo přejít na aktivní,
- archivovanou vazbu lze upravit, soft-deleted nikoli; archivovaná nebo
  soft-deleted osoba a `GraveSite` i zaniklý fyzický status jsou povoleny,
- služby nemají compatibility matici, párování přesunových rolí,
  deduplikaci ani mapování obecného `IntegrityError`,
- doplněny testy veřejného API, rolí, fresh-state FK, normalizace,
  lifecycle, duplicit, kardinality, rollbacku, locking a absence
  vedlejších zápisů,
- nevznikla migrace, selector, autorizované čtení ani ACP.

## Verze 0.32 – 23. 7. 2026

- přidán frozen slotted úplný snapshot `GraveSiteInput` a keyword-only
  služby `create_grave_site()` a `update_grave_site()`,
- služby čerstvě načítají typ, volitelné místo, autora a aktualizovaný
  `GraveSite`, používají `transaction.atomic()`, při update
  `select_for_update()` a vždy `full_clean()` před `save()`,
- všech sedm textových polí se stripuje pouze na servisní hranici;
  souřadnice zůstávají `Decimal | None` a jejich validaci zachovává model,
- create vyžaduje aktivní typ; update dovoluje zachovat stejný neaktivní
  typ, přejít na aktivní, změnit nebo odebrat `Place` a souřadnice a
  upravit archivovaný záznam, ale odmítá jiný neaktivní typ a
  soft-deleted `GraveSite`,
- update zachovává čerstvé autorství a lifecycle metadata; existující
  archivovaný nebo soft-deleted `Place` je povolen,
- služby nededuplikují ani nemapují obecný `IntegrityError`; přidány testy
  veřejného API, fresh-state validace, normalizace, lokalizace, souřadnic,
  lifecycle, rollbacku, locking a absence vedlejších zápisů,
- nevznikla migrace, služba `PersonGraveSite`, selector, autorizované
  čtení ani ACP.

## Verze 0.31 – 23. 7. 2026

- přidán explicitní `places.PersonGraveSite` jako jedno samostatné tvrzení
  o osobě, hrobovém místě a rozšiřitelné roli propojení,
- model dědí timestamp, access, verification, author a lifecycle metadata,
  ale nepoužívá `PartialDateModel`; čas pohřbu, rozptylu a přesunu patří do
  událostí,
- povinné FK na `Person`, `GraveSite` a `PersonGraveSiteRole` používají
  `PROTECT` a reverzní relace `grave_site_links`, `person_links` a
  `person_grave_site_links`,
- model dovoluje neaktivní i uživatelskou roli, více rolí stejné osoby u
  jednoho místa a více shodných tvrzení; nemá unikátnost, deduplikaci,
  compatibility validaci ani explicitní index,
- přidána poznámka, obranný textový výstup, lokální admin konfigurace a
  strukturální migrace `places.0009_persongravesite`,
- doplněny testy struktury, mixinů, rolí, kardinality, duplicit,
  lifecycle, nezávislého access/verification, `PROTECT`, textu a adminu;
  služby, selectory a autorizované čtení zůstávají pro další krok.

## Verze 0.30 – 23. 7. 2026

- přidán konkrétní `places.GraveSite` pro jeden fyzický nebo pamětní
  objekt, oddělený od obecného `Place`, událostí a budoucí vazby osoby,
- model dědí timestamp, access, verification, author a lifecycle metadata,
  ale záměrně nepoužívá `PartialDateModel`,
- přidán povinný chráněný typ, fyzický status, volitelný chráněný `Place`,
  textová lokalita, hřbitov, oddíl, řada, číslo, nápis, souřadnice a
  poznámka,
- lokalizační validace vyžaduje alespoň strukturovanou či textovou
  lokalitu nebo úplnou dvojici souřadnic; souřadnice se kontrolují na
  úplnost a zeměpisné rozsahy,
- model dovoluje neaktivní i uživatelský typ, nemá unikátnost, deduplikaci
  ani explicitní index a zachovává nezávislost statusu, ověření a
  lifecycle,
- přidána lokální admin konfigurace, strukturální migrace
  `places.0008_gravesite` a testy struktury, validace, `PROTECT`, duplicit,
  lifecycle a obranného textového výstupu; `PersonGraveSite`, služby,
  selectory a permissions zůstávají pro navazující kroky.

## Verze 0.29 – 22. 7. 2026

- zahájen M2.7 potvrzením budoucích modelů `GraveSite` a
  `PersonGraveSite`, které v tomto kroku ještě nevznikají,
- přidán pevný `GraveSiteStatus` s fyzickými stavy `existing`,
  `destroyed` a `unknown`, oddělenými od ověření, archivace a měkkého
  odstranění,
- přidány rozšiřitelné katalogy `GraveSiteType` s osmi systémovými typy a
  `PersonGraveSiteRole` se sedmi systémovými rolemi,
- symbolický hrob je typ `cenotaph`, zatímco vztah osoby vyjadřuje
  `commemorated`; přemístění ostatků používá oddělené směrové role pro
  původní a cílové místo,
- strukturální migrace `places.0006_grave_site_lookups` a datová
  `places.0007_initial_grave_site_lookups` oddělují schéma od systémových
  dat; společná kontrola kolizí proběhne před prvním zápisem a reverse
  zachová uživatelské i odsystemizované hodnoty,
- doplněna lokální admin konfigurace a testy choices, modelů, systémových
  katalogů, idempotence, kolizí a reverse; M2.7a neimplementuje hlavní
  hrobové místo, vazbu osoby, služby, selectory ani permissions a
  nevyžaduje ACP.

## Verze 0.28 – 22. 7. 2026

- přidán autorizovaný lazy selector
  `get_visible_person_residences(*, person, actor)` nad nezměněným
  permissionless přehledem M2.6d,
- actor a vstupní osoba se ověřují podle aktuálního databázového stavu;
  lifecycle osoby používá `people.view_archived_person` a
  `people.view_deleted_person` a neviditelný vstup obecnou
  `PermissionDenied`,
- Residence se databázově filtrují přes povolené `AccessLevel`; archivované
  zůstávají zahrnuté a měkce odstraněné vyloučené bez zavedení nových
  lifecycle oprávnění,
- zachována úplná historie, neaktivní a uživatelské typy, původní ordering,
  `select_related()`, lazy vyhodnocení a konstantní dotazový profil bez
  N+1,
- doplněny stabilní chyby actora a osoby a testy permission matice,
  zastaralých instancí, laziness, řazení, vedlejších zápisů a query profilu;
  M2.6e nemění modely, služby ani migrace a nevyžaduje ACP.

## Verze 0.27 – 22. 7. 2026

- přidán permissionless `get_person_residences(*, person)` vracející lazy
  `QuerySet[Residence]` úplné historie jedné osoby,
- selector přijímá běžnou, archivovanou i měkce odstraněnou existující
  vstupní osobu a používá stabilní chybu `person_unsaved`,
- vrací archivované, neveřejné, historické a budoucí Residence i neaktivní
  a uživatelské typy, ale vylučuje měkce odstraněné Residence,
- schváleno deterministické řazení podle obou technických mezí data,
  pořadí a názvu typu a PK bez zvláštního NULL pravidla,
- `select_related()` pro osobu, typ, místo a autora zajišťuje po validačním
  `exists()` jeden lazy SELECT bez N+1,
- M2.6d nemění modely, služby ani migrace; autorizovaný selector bydlišť
  zůstává pro navazující M2.6e.

## Verze 0.26 – 22. 7. 2026

- přidán frozen slotted úplný snapshot `places.services.ResidenceInput` a
  keyword-only služby `create_residence()` a `update_residence()`,
- služby načítají čerstvý databázový stav všech FK, normalizují okrajové
  mezery textů a atomicky volají `full_clean()` před `save()`,
- update používá `select_for_update()`, může změnit osobu, typ i místo, ale
  zachovává `created_by`, vytvoření a lifecycle metadata,
- nový záznam ani přechod nesmí použít neaktivní typ; existující neaktivní
  typ lze podle PK zachovat, archivovaný Residence lze upravit a měkce
  odstraněný nikoli,
- služba nededuplikuje ani nemapuje obecný `IntegrityError`; doplněny testy
  validace, stale instancí, rollbacků a absence vedlejších zápisů,
- M2.6c nemění modely ani migrace; selectory a oprávněné čtení bydlišť
  zůstávají pro navazující krok.

## Verze 0.25 – 22. 7. 2026

- implementován `places.Residence` pro jeden souvislý pobyt povinné osoby
  a povinného typu s volitelným strukturovaným místem,
- schválen `address_text` délky 500, poznámka a modelová podmínka alespoň
  jednoho z `Place` nebo neprázdného lokalizačního textu; obojí lze
  kombinovat a text se při uložení automaticky nenormalizuje,
- zapojen úplný `PartialDateModel` a společná access, verification, author,
  lifecycle a timestamp metadata; všechny doménové FK používají `PROTECT`,
- potvrzena tolerance uživatelských i neaktivních typů, povolené překryvy a
  absence vlastní unikátnosti, lokalizačního check constraintu a dalších
  explicitních indexů,
- přidána lokální administrace, strukturální migrace
  `places.0005_residence` a testy struktury, validace i databázového chování;
  služby a selectory zůstávají pro navazující M2.6c.

## Verze 0.24 – 22. 7. 2026

- zahájen blok M2.6 číselníkem `places.ResidenceType`, který přímo dědí z
  `LookupModel`, nepřidává vlastní pole a umožňuje uživatelské typy,
- schválen katalog hlavního, dočasného, úředního, institucionálního a jiného
  bydliště včetně stabilních kódů, popisů a pořadí,
- odděleno faktické hlavní bydliště od administrativně evidované úřední
  adresy a odmítnuty nejednoznačné kódy odkazující na trvalý pobyt,
- přidány strukturální `places.0003_residence_type` a datová
  `places.0004_initial_residence_types`,
- datová migrace před zápisem odmítá kolizi s uživatelským kódem, je
  idempotentní a reverse maže pouze schválené stále systémové hodnoty,
- doplněna lokální admin konfigurace a testy; konkrétní model `Residence`
  zatím nebyl implementován.

## Verze 0.23 – 22. 7. 2026

- přidán autorizovaný selector
  `get_visible_relationship_overview(*, person, actor)` nad nezměněným
  permissionless přehledem M2.5g,
- doplněna kontrola aktuálního actora a vstupní osoby včetně stabilních
  validačních chyb a jednotné `PermissionDenied`,
- zavedeno společné vyhodnocení přístupové úrovně a lifecycle pro vstupní,
  výsledné a rodičovské osoby,
- explicitní důvody nově zachovávají pouze viditelná měkce neodstraněná
  `relationship_ids` ve stávajícím pořadí,
- biologický důvod je autorizován pouze kompletní viditelnou cestou přes
  jednoho stejného společného rodiče a dvě hrany `biological_parent`,
- potvrzeno zachování pořadí a neměnnost frozen permissionless objektů,
  dávkové dotazy bez N+1 a absence zápisů, modelových změn a migrací.

## Verze 0.22 – 22. 7. 2026

- konkretizována obecná policy pro všechny čtyři hodnoty `AccessLevel`,
- doplněna globální obsahová oprávnění pro omezený a administrátorský obsah
  a lifecycle oprávnění archivovaných a měkce odstraněných osob,
- zaveden keyword-only helper `can_view_access_level()` s kontrolou
  aktuálního databázového stavu actora a stabilními chybovými kódy,
- určeno, že `is_staff` není obsahová role, aktivní superuser má úplný
  přístup a neaktivní uživatel se posuzuje jako anonymní,
- založeny systémové skupiny Čtenář, Editor a Správce; pouze Správce dostává
  čtyři nová zvýšená oprávnění,
- migrační základ M2.5h-1 nemění modelová pole a autorizovaný relationship
  selector zůstává vyhrazen pro M2.5h-2.

## Verze 0.21 – 22. 7. 2026

- schválen celkový agregovaný čtecí přehled vztahů osoby
  `get_relationship_overview(*, person)`,
- zavedeny frozen slotted položky `RelationshipOverviewItem` a
  `RelationshipOverviewReason` s důvodově orientovaným kontraktem,
- určeno seskupení podle druhé osoby, deduplikace důvodů a zachování
  provenance explicitních období přes vzestupně seřazená `relationship_ids`,
- doplněny směrové a genderované názvy včetně biologického sourozence a
  zahrnutí uživatelských typů vztahů,
- stanoveno stabilní pořadí kategorií, důvodů a osob, lifecycle a konstantní
  pětidotazový profil bez N+1,
- potvrzena permissionless hranice a povinnost vyšší vrstvy filtrovat osoby,
  explicitní vztahy i biologicky odvozený důvod,
- krok M2.5g nic neukládá a nevytváří modelovou změnu, systémová data,
  migraci ani ACP.

## Verze 0.20 – 21. 7. 2026

- konkretizován agregovaný sourozenecký přehled nad biologicky odvozenými a
  čtyřmi explicitními typy sourozenectví,
- schválen frozen slotted `SiblingOverviewItem` a veřejné API
  `get_sibling_overview(*, person)`,
- určeno seskupení podle osoby, zachování všech důvodů a jejich stabilní
  pořadí,
- doplněno oboustranné vyhodnocení explicitních vazeb, lifecycle a řazení
  výsledku podle příjmení, jména a PK,
- potvrzena konstantní tří-dotazová strategie bez N+1 a povinná aplikační
  kontrola viditelnosti osob i explicitních důvodů,
- krok M2.5f nic neukládá a nevytváří modelovou změnu, migraci ani ACP.

## Verze 0.19 – 21. 7. 2026

- konkretizována definice biologického sourozence alespoň jedním společným
  biologickým rodičem bez rozlišení plného a polovičního sourozenectví,
- určeno použití pouze měkce neodstraněných vztahů `biological_parent` a
  lifecycle pravidla vztahů, vstupní osoby a výsledných osob,
- schválen veřejný lazy selector `get_biological_siblings(*, person)` s
  návratem `QuerySet[Person]`, standardním řazením a chybou
  `person_unsaved`,
- oddělen nízkoúrovňový doménový dotaz od povinné aplikační kontroly
  oprávnění a viditelnosti,
- explicitní sourozenecké vztahy se do odvozeného výsledku neslučují,
- krok M2.5e nic neukládá a nevytváří modelovou změnu, migraci ani ACP.

## Verze 0.18 – 21. 7. 2026

- konkretizován a implementován společný rodičovský graf typů
  `biological_parent`, `adoptive_parent`, `step_parent` a `foster_parent`,
- doplněna transakční kontrola přímých i nepřímých cyklů při create a
  update vztahu,
- určeno zahrnutí archivovaných a historických vztahů a vyloučení měkce
  odstraněných vztahů,
- potvrzeno, že `guardian` ani uživatelské typy nejsou automatickou
  součástí genealogického grafu,
- zdokumentován kód `relationship_parent_cycle` a omezení databázových
  zámků,
- krok M2.5d nevytvořil modelovou změnu, migraci ani nové ACP.

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
