# Uživatelské role a oprávnění

**Dokument:** 04  
**Verze:** 0.29
**Stav:** pracovní návrh  
**Datum revize:** 4. 9. 2026

## 1. Nepřihlášený návštěvník

Může:

- prohlížet veřejné osoby a údaje,
- vyhledávat ve veřejných datech,
- vidět informaci, že některý obsah je zamčený.

Nemůže:

- přidávat,
- upravovat,
- mazat,
- zobrazovat omezený obsah.

## 2. Čtenář

Přihlášený uživatel pouze pro čtení.

Může zobrazovat obsah určený přihlášeným uživatelům, ale nemůže jej měnit.

## 3. Editor

Může:

- vytvářet a upravovat osoby,
- vytvářet vazby a události,
- přidávat bydliště,
- přidávat fotografie a dokumenty,
- doplňovat zdroje,
- upravovat zdravotní záznamy, pokud má oprávnění,
- opravovat chyby.

Nemůže:

- spravovat uživatele,
- měnit systémová nastavení,
- fyzicky mazat data.

## 4. Správce

Může:

- spravovat uživatele,
- měnit všechna data,
- obnovovat archivované záznamy,
- měnit systémová nastavení,
- spravovat číselníky,
- provádět export a zálohu,
- spravovat omezený obsah.

Jde o cílové produktové schopnosti, nikoli automatické zpřístupnění každého
modelu přes výchozí Django admin. V aktuální infrastrukturní etapě admin
zpřístupňuje spravovatelné číselníky míst, ale `Place`, `Residence`,
`GraveSite` a `PersonGraveSite` jsou fail-closed odregistrovány. Bezpečné
produktové rozhraní musí nejprve použít schválenou servisní hranici a
actor-aware čtení; pro obecný `Place` taková úplná hranice zatím neexistuje.
Systémové řádky spravovatelných číselníků mají v adminu neměnný technický kód
a nelze je odstranit. Systémový typ vazby má navíc neměnnou kategorii,
symetrii, podporu rozmezí a odvoditelnost, protože určují orientaci a validaci
vazeb. Uživatelské názvy, popisy, pořadí a aktivitu může oprávněný správce
nadále měnit. Snapshotové defaulty typů událostí a konfigurační počty rolí
spolu s validační konfigurací `supports_date_range` a `allows_place` zůstávají
spravovatelným systémovým nastavením; uživatelské řádky jsou plně spravovatelné.

## 5. Přístupové úrovně záznamů

| Úroveň | Podmínka zobrazení |
|---|---|
| `public` | Každý včetně anonymního a neaktivního uživatele. |
| `authenticated` | Uložený, existující, aktivní a autentizovaný uživatel. |
| `restricted` | Aktivní existující uživatel s `accounts.view_restricted_content` nebo aktivní superuser. |
| `admin_only` | Aktivní existující uživatel s `accounts.view_admin_only_content` nebo aktivní superuser. |

Neaktivní uživatel, včetně neaktivního superusera, se posuzuje jako
anonymní. `is_staff` pouze řídí přístup do Django Adminu a sám obsahová
oprávnění neposkytuje. Aktivní superuser má úplný obsahový přístup.

Přístupová úroveň může být nastavena pro:

- osobu,
- bydliště,
- událost,
- vazbu,
- fotografii,
- dokument,
- zdravotní záznam,
- poznámku,
- zdroj,
- konkrétní údaj.

Obecnou policy implementuje
`common.permissions.can_view_access_level(*, actor, access_level)`. Helper
nezná konkrétní doménové objekty ani lifecycle.

Zdravotní záznam má v M2 nejširší povolenou úroveň `restricted`; může být
`admin_only`, ale nikdy `public` ani `authenticated`. Samostatná zdravotní
permission se nezavádí. Doménová actor-aware hranice
`health.permissions.can_view_health_record_access(*, actor, access_level)`
dnes deleguje na obecný helper. Současné i budoucí aplikační čtení ji musí
použít, aby pozdější samostatná zdravotní autorizace nevyžadovala změnu modelu.

Konkrétní health read hranice skládá toto rozhodnutí v
`get_health_record_visibility_filter(*, actor)`. Filtr vyžaduje access osoby i
záznamu a aktivní lifecycle osoby, zdravotního záznamu a jeho typu. Kolekční i
detailní selector používají tentýž filtr; znalost ID skrytého záznamu nepřidává
žádný přístup a detail se chová stejně jako neexistující cíl. Nevzniká nové
health oprávnění ani paralelní permission mechanismus.

Actor-aware čtení zdravotních příloh nejprve vyžaduje celý centrální health
řetězec osoby, záznamu a aktivního typu. Výsledné SQL dále vyžaduje viditelnou,
nearchivovanou a neodstraněnou vazbu i přílohu a stav souboru `available`.
Znalost ID přílohy či vazby health policy neobchází. Nevzniká nové zdravotní
oprávnění ani obecná cesta vydání souboru.

Actor-aware zdroje zdravotního záznamu používají tentýž centrální health
řetězec. Výsledek navíc vyžaduje viditelnou, nearchivovanou a neodstraněnou
zdrojovou vazbu i `Source`. Sdílený zdroj, znalost jeho ID ani ID vazby
neposkytují přístup k chráněnému zdravotnímu kontextu. Nové oprávnění nevzniká.

Transportně neutrální `list_health_records()` a `get_health_record_detail()`
pouze předávají konkrétního actora existujícím health selectorům. Nemají vlastní
permission, ORM visibility podmínky ani obsluhu výjimek, takže autorizační
význam kolekce a detailu zůstává soustředěný v centralizované health policy.
Zdroje a přílohy tento první aplikační kontrakt nečte ani nepřipojuje.

## 5.1 Systémové skupiny a zvýšená oprávnění

Databázové skupiny jsou `Čtenář`, `Editor` a `Správce`.

- Čtenář automaticky nezískává zvýšená obsahová, lifecycle ani editační
  oprávnění.
- Editor získává pro RC průchod konkrétní `people.change_person`, ale
  automaticky nezískává přístup k omezenému nebo administrátorskému obsahu.
- Správce získává `accounts.view_restricted_content`,
  `accounts.view_admin_only_content`, `people.view_archived_person` a
  `people.view_deleted_person` a pro tentýž průchod také
  `people.change_person`.

Správce tím nezískává všechna standardní add/change/delete/view oprávnění,
`is_staff` ani `is_superuser`. Konkrétní permission lze uživateli nebo jiné
schválené skupině přidělit samostatně.

Přihlášení ani samotné členství ve skupině nemění význam přístupových
úrovní. Čtenář a Editor vidí `authenticated`, nikoli automaticky
`restricted` nebo `admin_only`; Správce získává zvýšený obsah jen přes výše
vyjmenovaná permission. Odhlášení vrací actora do anonymního režimu.

Lifecycle osoby se posuzuje odděleně od její přístupové úrovně. Zobrazení
archivované osoby vyžaduje `people.view_archived_person`; zobrazení měkce
odstraněné osoby vyžaduje `people.view_deleted_person`. Aplikační použití
těchto oprávnění zajišťuje autorizovaný přehled vztahů M2.5h-2.

## 5.2 Autorizovaný přehled vztahů

`get_visible_relationship_overview(*, person, actor)` je bezpečná veřejná
čtecí vrstva nad permissionless `get_relationship_overview(*, person)`.
Neviditelnou vstupní osobu odmítne jednotnou zprávou bez prozrazení, zda
důvodem byla přístupová úroveň, archivace nebo měkké odstranění.

Výsledné osoby i explicitní vztahy musí být viditelné podle své vlastní
přístupové úrovně. Archivovaná výsledná osoba vyžaduje
`people.view_archived_person`; měkce odstraněná výsledná osoba se nevrací
ani superuserovi. Explicitní důvod zachová pouze ID viditelných,
měkce neodstraněných vztahů.

Biologické sourozenectví se zveřejní pouze přes jednoho stejného
viditelného společného rodiče a dvě viditelné hrany
`biological_parent`. Archivovaný rodič vyžaduje oprávnění, měkce odstraněný
rodič se jako autorizační cesta nepoužije. Neaktivní actor se i při členství
ve Správci nebo s příznakem superusera posuzuje jako anonymní; `is_staff`
sám žádné z uvedených oprávnění neposkytuje.

## 5.3 Autorizovaný přehled bydlišť

`get_visible_person_residences(*, person, actor)` je veřejná čtecí vrstva
nad permissionless `get_person_residences(*, person)`. Actor i vstupní
osoba se posuzují podle aktuálního databázového stavu. Vstupní osoba musí
mít viditelný `access_level`; archivovaná navíc vyžaduje
`people.view_archived_person`, měkce odstraněná
`people.view_deleted_person` a osoba v obou stavech obě oprávnění.
Neviditelný vstup se vždy odmítne stejnou obecnou zprávou.

Po autorizaci osoby se jednotlivá bydliště tiše filtrují podle svého
`access_level`. Archivované Residence se vracejí bez zvláštní lifecycle
permission, protože takové oprávnění projekt nezavádí; měkce odstraněné se
nevracejí ani superuserovi. Aktivita nebo systémovost typu, místo, stav
ověření a časová platnost přístup nemění. Neaktivní actor vidí pouze
veřejná bydliště veřejně viditelné běžné osoby, `is_staff` samo přístup
nerozšiřuje a aktivní superuser má plný obsahový i lifecycle přístup ke
vstupní osobě.

## 5.4 Autorizovaný katalog hrobových míst

`get_visible_grave_sites(*, actor)` je veřejně bezpečnější čtecí vrstva
nad permissionless `get_grave_sites()`. Každou známou přístupovou úroveň
vyhodnotí nejvýše jednou přes `can_view_access_level()` a výsledný lazy
`QuerySet[GraveSite]` databázově filtruje přes `access_level__in`.

AnonymousUser vidí pouze `public`. Aktivní běžný uživatel vidí navíc
`authenticated`; `restricted` a `admin_only` vyžadují svá oddělená
oprávnění. Samotné `is_staff` přístup nerozšiřuje, aktivní superuser vidí
všechny úrovně a neaktivní uživatel se i s oprávněními, skupinami,
`is_staff` nebo `is_superuser` posuzuje jako anonymní. Uložený actor se
vždy rozhoduje podle aktuálního databázového stavu. Neplatný actor používá
`actor_invalid`, neuložený nebo chybějící autentizovaný actor
`actor_unsaved`.

Archivovaná hrobová místa se vracejí bez zvláštní lifecycle permission,
měkce odstraněná se nevracejí ani superuserovi. Fyzický status, stav
ověření a aktivita či systémovost typu viditelnost nemění. Připojené
`Place` se v tomto kroku samostatně neautorizuje. Neviditelné záznamy se
tiše odfiltrují; autorizace vazeb osob na místa následuje samostatně.

## 5.5 Autorizované vazby osob a hrobových míst

`get_visible_person_grave_site_links(*, person, actor)` a
`get_visible_grave_site_person_links(*, grave_site, actor)` považují
konkrétní vstup za chráněný cíl. Existující neviditelný vstup proto
odmítnou obecnou `PermissionDenied`; prázdný QuerySet nevracejí. Chybějící
PK nebo fyzicky neexistující řádek používá stabilní `person_unsaved`,
respektive `grave_site_unsaved`.

Vstupní osoba vyžaduje viditelný `access_level`; archivovaná navíc
`people.view_archived_person`, měkce odstraněná
`people.view_deleted_person` a osoba v obou stavech obě oprávnění.
Vstupní hrobové místo vyžaduje viditelný `access_level`, může být
archivované i zaniklé, ale nesmí být měkce odstraněné. Pro `GraveSite`
nevzniká lifecycle permission.

Po ověření vstupu se každý řádek tiše odfiltruje, pokud není viditelná
vazba, související osoba nebo hrobové místo. Výsledná archivovaná či
měkce odstraněná osoba používá stejná nezávislá person lifecycle
oprávnění. Archivované vazby a místa se vracejí, soft-deleted vazby a
místa nikoli. Aktivní superuser vidí všechny access úrovně a oba person
lifecycle stavy, ne však soft-deleted hrobové místo; neaktivní
privilegovaný uživatel se posuzuje jako anonymní.

Status a ověření, aktivita či systémovost typu a role a připojené `Place`
se samostatně neautorizují. Oba selectory zachovávají lazy vyhodnocení,
ordering a `select_related()` permissionless vrstvy.

## 5.6 Autorizovaný seznam a detail osoby pro RC 0.1

`get_visible_people(*, actor)` vrací lazy `QuerySet[Person]` pro hlavní
obrazovku. Každou pevnou přístupovou úroveň posuzuje centrálním
`can_view_access_level()` a výsledek databázově filtruje. Výchozí průchod
vždy vylučuje archivované a měkce odstraněné osoby; oprávněné zobrazení
archivu bude dostupné jen přes budoucí explicitní režim popsaný v UI/UX
návrhu.

`get_visible_person(*, person_id, actor)` používá stejnou výchozí hranici
jako seznam. HTTP vrstva proto vrací pro fyzicky neexistující i neviditelnou
osobu stejnou 404 odpověď bez prozrazení chráněných údajů. Platí to pro
plnou stránku, HTMX fragment i ručně zadanou přímou URL.

Django Admin používá pro `Person` stejný autorizovaný selector. Admin
přehledy `PersonName` a `Relationship` navíc vyžadují viditelnost vlastního
záznamu i všech propojených osob. Všechny tři plochy jsou v této etapě pouze
pro čtení. Běžné `is_staff` ani standardní modelové permission nesmějí
obejít obsahová nebo lifecycle pravidla; zápis osoby je veden přes
doménovou službu v aplikačním editačním průchodu.

## 5.7 Editace základních údajů osoby pro RC 0.1

Odkaz i formulář vidí pouze actor s `people.change_person`, ale UI není
bezpečnostní hranicí. Editační view nejprve použije stejný autorizovaný
selector jako detail, takže neviditelná, archivovaná nebo měkce odstraněná
osoba zůstane skrytá jednotnou 404. Teprve pro viditelný cíl ověří čerstvý
aktivní účet a `people.change_person`; bez permission vrací 403.

Čtenář editaci nemá. Editor může upravit veřejnou a `authenticated` osobu,
nikoli automaticky `restricted` nebo `admin_only`. Správce může díky svým
výslovným obsahovým permissions upravit i zvýšené úrovně. `is_staff` bez
obsahové permission neodhalí skrytý cíl a superuser zachovává centrální
policy. POST vyžaduje CSRF a klient nemůže formulářem měnit přístup, ověření
ani lifecycle.

## 5.8 Odvozené údaje a viditelnost zdrojů

Podle ACP-007 se věk, stav žijící/zemřelý, životní data, římské pořadí a
další prezentační odvozené údaje počítají pouze z osob, událostí a jiných
zdrojů, které jsou aktuálnímu actorovi samy viditelné. Běžný RC průchod
vylučuje archivované i měkce odstraněné zdroje. Skrytá událost úmrtí proto
nesmí změnit veřejně zobrazený stav a skrytý jmenovec nesmí vytvořit mezeru
v římském pořadí.

Římská číslice je actor-specific prezentační údaj a může se mezi rolemi
lišit. Věk se zobrazí pouze tehdy, když jej lze z viditelného narození a
případného viditelného úmrtí určit jednoznačně i při neúplném datu.
Nejednoznačné duplicitní zdroje se nesmějí vyřešit náhodným výběrem jednoho
záznamu.

## 5.9 Detail úmrtí dědí policy události

`DeathDetail` nemá samostatnou access ani lifecycle policy. Konkrétnímu
actorovi smí být zpřístupněn pouze tehdy a ve stejném rozsahu jako jeho
nadřazená událost úmrtí; samotná existence detailu nesmí prozradit skrytou
událost. Doménové služby záměrně neřeší HTTP oprávnění, proto je budoucí
aplikační rozhraní smí zavolat až po serverové autorizaci rodičovské události.
V aktuální etapě není detail vystaven v produktovém UI, API ani Django adminu.

## 5.10 Fyzický stav a budoucí doručení přílohy

`FileStatus` není přístupová úroveň. Pouze příloha ve stavu `available` smí
být v budoucnu přímo doručena. `pending`, `missing` a `quarantined` doručení
zakazují i actorovi, který by jinak splnil access policy. Stav souboru je
nezávislý na archivaci a měkkém odstranění.

Samotné `available` přístup nezakládá. Budoucí doručovací hranice musí současně
vyhodnotit nejpřísnější kombinaci access a lifecycle pravidel přílohy,
explicitní vazby a cílového objektu. Přímý storage odkaz nesmí tuto kontrolu
obejít. V aktuální etapě neexistuje doručovací view, URL, selector ani UI.

## 5.11 Kontextová autorizace explicitní vazby přílohy

Neexistuje obecná doručovací URL založená pouze na `Attachment.id` nebo
`storage_key`. Budoucí doručení musí být adresováno přes konkrétní explicitní
vazbu a současně autorizovat cílový objekt, vazbu, přílohu a
`FileStatus.AVAILABLE`. Neviditelný kontext se nesmí prozradit jinou slabší
cestou.

Při vytvoření vazby nesmí být příloha ani cíl archivovaný či měkce odstraněný.
Při změně lze zachovat stejný mezitím archivovaný endpoint, nelze však přejít
na jiný archivovaný endpoint; měkce odstraněný endpoint je zakázaný vždy.
Archivovanou vazbu lze změnit, měkce odstraněnou nikoli. Doménová služba
rozhoduje podle čerstvého databázového stavu. Případné aplikační rozhraní musí
před voláním služby serverově ověřit při create cíl, přílohu i oprávnění
vytvořit daný kontext. Při update musí nejprve autorizovat existující vazbu v
jejím dosavadním kontextu cíle a přílohy a poté každý měněný endpoint i
oprávnění k mutaci. Teprve po těchto kontrolách smí vrátit konkrétní validační
nebo konfliktní detail.

## 5.12 Kontextová autorizace zdroje

`Source` je znovupoužitelný informační pramen, ale jeho opakované použití
nevytváří globální zkratku k chráněným objektům. Každá explicitní vazba se
autorizuje v kontextu vlastního cílového doménového objektu. To, že actor vidí
tentýž zdroj přes jinou přístupnou vazbu, nesmí potvrdit existenci, identitu ani
obsah chráněného cíle.

Access policy cíle je pro vazbu vždy povinná. Případná vlastní access úroveň
vazby nebo zdroje ji smí pouze zpřísnit a lifecycle se vyhodnocuje na všech
objektech konkrétní cesty. Chybějící nebo neviditelný článek cesty selže
uzavřeně. Obecná URL nebo selector pouze podle `Source.id` nesmí sloužit jako
autorizační hranice pro doménový kontext.

### 5.12.1 Implementovaný kontext jména osoby

`get_visible_person_name_source_links(*, person_name, actor)` nejprve ověří
rodičovskou osobu a konkrétní `PersonName`. Osoba používá centrální access
policy a explicitní permissions pro archivovaný či měkce odstraněný stav.
Archivované nebo odstraněné jméno se v běžném průchodu nevydá ani superuserovi.
Výsledný dotaz znovu databázově filtruje access celé cesty a vždy vylučuje
archivovanou či odstraněnou vazbu a zdroj.

Permissionless protějšek je pouze interní historie nesmazaných vazeb a není
autorizační hranicí. Neexistuje selector podle samotného `Source.id`. Viditelná
vazba jiného jména ke stejnému zdroji proto nemůže potvrdit existenci ani obsah
chráněného `PersonName`.

### 5.12.2 Implementovaný kontext události

`get_visible_event_source_links(*, event, actor)` vyžaduje viditelnou,
nearchivovanou a měkce neodstraněnou událost. Výsledný lazy dotaz znovu
kontroluje access a lifecycle události, konkrétní vazby a zdroje. Permissionless
protějšek je pouze interní historie nesmazaných eventových vazeb.

Viditelnost stejného `Source` přes jinou událost nezakládá žádné oprávnění k
chráněné události ani její vazbě. Neexistuje obecná cesta od zdroje zpět ke
všem cílům.

### 5.12.3 Implementovaný kontext vztahu

`get_visible_relationship_source_links(*, relationship, actor)` kontroluje
vlastní access vztahu a access obou propojených osob. Archivovaný vztah je
historický záznam a smí být čten, měkce odstraněný vztah nikoli. Archivovaná
osoba vyžaduje `people.view_archived_person`; měkce odstraněná osoba uzavře
cestu i superuserovi.

Výsledný lazy dotaz opakuje podmínky vztahu a obou osob a navíc vyžaduje
viditelnou, nearchivovanou a neodstraněnou zdrojovou vazbu i `Source`.
Permissionless protějšek je pouze interní historie nesmazaných vazeb.

### 5.12.4 Implementované přílohy vztahu

`get_visible_relationship_attachment_links(*, relationship, actor)` používá
stejnou ochranu vztahu a obou propojených osob jako zdrojový selector.
Výsledný lazy dotaz navíc vyžaduje viditelnou, nearchivovanou a neodstraněnou
vazbu přílohy i přílohu a stav souboru `available`.

Permissionless protějšek je pouze interní historie nesmazaných vazeb a
nezakládá oprávnění k doručení souboru. Sdílená příloha nevytváří cestu zpět
k jinému chráněnému vztahu.

### 5.12.5 Implementované přílohy bydliště

`get_visible_residence_attachment_links(*, residence, actor)` vyžaduje
viditelné, měkce neodstraněné bydliště a viditelnou rodičovskou osobu.
Archivované bydliště zůstává historickým záznamem; archivace a soft-delete osoby
respektují `people.view_archived_person` a `people.view_deleted_person`.

Výsledný lazy dotaz znovu kontroluje bydliště a osobu a vydává pouze viditelnou,
nearchivovanou a neodstraněnou vazbu i přílohu ve stavu `available`. Připojené
`Place` není podle stávající residence policy samostatnou autorizační vrstvou.
Selector nevydává storage URL a sdílená příloha neodhalí jiné bydliště.

### 5.12.6 Implementované zdroje bydliště

`get_visible_residence_source_links(*, residence, actor)` používá stejnou
ochranu bydliště a jeho osoby jako přílohový selector. Výsledný lazy dotaz
znovu kontroluje obě vrstvy a vydává pouze viditelnou, nearchivovanou a
neodstraněnou zdrojovou vazbu i `Source`.

Připojené `Place` není samostatnou autorizační vrstvou a viditelnost stejného
zdroje přes jiný kontext nezakládá přístup k chráněnému bydlišti.

### 5.12.7 Implementované přílohy hrobového místa

`get_visible_grave_site_attachment_links(*, grave_site, actor)` vyžaduje
viditelné a měkce neodstraněné hrobové místo; archivované místo zůstává
historicky čitelné. Výsledný lazy dotaz navíc vydává pouze viditelnou,
nearchivovanou a neodstraněnou vazbu i přílohu ve stavu `available`.

Status, verification, typ a připojené `Place` nejsou samostatnou autorizační
vrstvou. Selector nevydává storage URL a sdílená příloha neodhalí jiné
chráněné hrobové místo.

### 5.12.8 Implementované zdroje hrobového místa

`get_visible_grave_site_source_links(*, grave_site, actor)` používá stejnou
ochranu hrobového místa jako přílohový selector. Výsledný lazy dotaz znovu
kontroluje místo a vydává pouze viditelnou, nearchivovanou a neodstraněnou
zdrojovou vazbu i `Source`.

Status, verification, typ a připojené `Place` nejsou samostatnou autorizační
vrstvou. Viditelnost stejného zdroje přes jiný kontext nezakládá přístup k
chráněnému hrobovému místu.

## 6. Zamčený obsah

Uživatel bez oprávnění má být informován, že chráněný obsah existuje.
Jde o obecné upozornění na skrytou sekci nebo položky; nesmí potvrdit existenci,
identitu ani vazbu konkrétního chráněného objektu dosaženého direct-object URL
nebo přes jiný přístupný kontext.

Možné zprávy:

- Tato sekce obsahuje chráněné záznamy. Pro zobrazení se přihlaste.
- Nemáte oprávnění zobrazit tento obsah.
- Některé položky v této sekci jsou skryté.

Obsah samotný se nezobrazí.

## 7. Výchozí ochrana

- zdravotní informace jsou ve výchozím stavu omezené,
- údaje žijících osob mají přísnější ochranu než historické údaje,
- přesné kontaktní a jiné citlivé údaje se nezveřejňují bez výslovného nastavení.

## 8. Historie změn

Změny vazeb, zdravotních údajů, oprávnění a důležitých osobních údajů se vždy zapisují do historie.
