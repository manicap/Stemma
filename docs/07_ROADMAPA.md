# Roadmapa projektu

**Dokument:** 07  
**Verze:** 0.20
**Stav:** M2 dokončeno; infrastruktura `materials` zahájena
**Datum revize:** 30. 8. 2026

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

#### M2 – jádro Osoba, Místo, Událost a Vazba ✅

1. založit doménové aplikace potřebné pro jádro,
2. implementovat základní číselníky a model Osoba,
3. implementovat Místo,
4. implementovat Událost a účastníky události,
5. implementovat Vazbu mezi osobami,
6. vytvářet malé strukturální a datové migrace,
7. doplňovat testy databázové integrity a doménových pravidel.

Audit skutečné implementace z 30. 8. 2026 potvrzuje dokončení M2:

- `Person`, `Place`, `Event`, `EventParticipant`, `DeathDetail` a
  `Relationship` včetně souvisejících číselníků mají konkrétní modely,
  strukturální a datové migrace a cílené integritní testy,
- navazující `Residence`, `GraveSite` a `PersonGraveSite` mají rovněž
  servisní a selectorové hranice; nejde jen o historický roadmapový status,
- existující aplikační zápisy M2 entit procházejí transakčními doménovými
  službami a business admin cesty, které by hranici obcházely, jsou read-only
  nebo fail-closed,
- aplikační čtení osob a odvozených údajů používá centrální actor-aware
  access/lifecycle policy; autorizované selectory existují také pro vazby,
  bydliště a hrobová místa,
- obecný `Place` zatím nemá produktový zápisový ani čtecí use-case a není
  vystaven neomezeným adminem; případné budoucí rozhraní musí nejprve doplnit
  odpovídající servisní a actor-aware hranici,
- závěrečná brána po doplnění `DeathDetail` prošla 1 083 testy,
  `manage.py check`, kontrolou migrací a nezávislým QA, security a
  dokumentačním review.

#### Nejbližší další infrastrukturní milník

Podle skutečných závislostí je dalším krokem doména materiálů: jednou uložené
přílohy a zdroje a jejich explicitní propojení se stabilním M2 jádrem.
Registrovaná aplikace `materials` a prázdné katalogy `AttachmentCategory` a
`AttachmentRole` ve strukturální migraci `materials.0001_attachment_lookups`
tvoří první samostatný řez. Nevznikají systémové hodnoty, přílohy, zdroje,
vazby, souborové úložiště ani aplikační rozhraní.

Druhý řez přidává pevný `FileStatus`, metadata model `Attachment` a migraci
`materials.0002_attachments`. Model je backendově neutrální a pouze připravuje
integritní základ; upload, doručení, explicitní vazby, služby, selectory,
admin a UI zůstávají pro samostatné navazující řezy.

Třetí řez přidává šest explicitních vazeb ke stávajícím doménám, migraci
`materials.0003_attachment_links` a transakční create/update služby. Vazby na
zdravotní záznam a zdroj zůstávají záměrně odložené do příslušných domén.
Nevzniká generická vazba, selector, admin, doručovací URL ani produktové UI.

#### Následující implementační kroky

1. doplnit zdroje, jejich explicitní propojení a actor-aware čtení příloh,
2. doplnit zdravotní záznamy,
3. doplnit audit navazujících zápisových operací,
4. průběžně rozšiřovat testy databázové integrity a bezpečnostních hranic.

## Experimentální cílový průřez – RC 0.1 ✅ připraven na `agent/rc-0.1`

RC 0.1 je pracovní označení prvního skutečně použitelného kandidáta aplikace. Neznamená dokončení celé roadmapy ani schválení produkčního nasazení. Jeho účelem je co nejdříve ověřit jeden úplný uživatelský průchod od databáze přes oprávnění až po skutečné UI.

Na experimentální větvi `agent/rc-0.1` smí hlavní agent podle ACP-006 volit nejmenší bezpečné vertikální řezy přes více níže uvedených fází, pokud zachová schválené závislosti, datový model, oprávnění a UI/UX principy. Stav původních milníků se tím nemění, dokud nejsou jejich vlastní podmínky skutečně splněny.

### RC 0.1 – povinná acceptance kritéria

RC 0.1 lze označit za dokončené pouze tehdy, když jsou splněny **všechny** následující oblasti a stav je ověřen automatickými testy i skutečným uživatelským průchodem v prohlížeči.

#### A. Reprodukovatelné spuštění

- čistý checkout lze zprovoznit podle aktuální dokumentace bez znalosti historie chatu,
- instalace závislostí, migrace a běžné spuštění vývojového serveru mají jednoznačný postup,
- projekt nevyžaduje commitnutá tajemství ani lokální databázi,
- existuje jednoduchý dokumentovaný způsob vytvoření nebo načtení bezpečných ukázkových dat pro ověření UI.

#### B. Skutečný seznam osob

- pracovní sekce Osoby čte skutečné osoby z databáze, nikoli mocky nebo pevně zapsaná demonstrační data v šabloně,
- seznam vrací pouze osoby viditelné pro aktuálního actora podle existujících pravidel přístupové úrovně a lifecycle,
- výběr osoby otevře její skutečný detail,
- prázdný seznam a neexistující výsledek mají použitelné uživatelské sdělení.

#### C. Skutečný detail osoby

- detail pracuje se skutečným modelem `Person` a schválenými odvozenými údaji,
- minimálně zobrazuje dostupné základní identifikační údaje osoby a respektuje schválený návrh záhlaví a rozvržení,
- neexistující a neviditelná osoba jsou bezpečně zpracovány bez úniku chráněných údajů,
- přímé zadání URL nesmí obejít autorizaci, kterou uplatňuje seznam nebo UI.

#### D. Přihlášení a role v uživatelském průchodu

- funguje přihlášení a odhlášení,
- lze prakticky ověřit alespoň anonymního návštěvníka, přihlášeného čtenáře a editora,
- UI zobrazuje akce podle oprávnění, ale skutečné vynucení práv probíhá vždy na serveru,
- neaktivní uživatel, `is_staff`, superuser a zvýšená obsahová oprávnění zachovávají již zdokumentovanou centrální policy.

#### E. Jednoduchá editace osoby

- oprávněný editor může z detailu otevřít formulář pro základní údaje entity `Person`,
- formulář vychází z existujícího modelu a schválených pravidel; nevytváří pole narození, úmrtí ani jiné údaje, které patří do samostatných událostí nebo entit,
- změna probíhá přes servisní/doménovou hranici odpovídající architektuře projektu, nikoli přímým nekontrolovaným zápisem ve view,
- validace je serverová a chybové stavy se zobrazí uživateli,
- po úspěšném uložení se změna skutečně zapíše do databáze a projeví v aktuálním UI bez nutnosti ručního obnovení celé stránky tam, kde je podle schváleného návrhu vhodné HTMX.

#### F. Bezpečnostní a autorizační brána

Musí existovat cílené automatické testy a nezávislý security review alespoň pro relevantní kombinace:

- anonymní návštěvník,
- aktivní běžný autentizovaný uživatel,
- editor,
- neaktivní uživatel,
- `is_staff` bez obsahových oprávnění,
- aktivní superuser,
- objekt s `public`, `authenticated`, `restricted` a `admin_only` přístupem,
- archivovaná a měkce odstraněná osoba tam, kde se jejich lifecycle vztahuje k danému průchodu,
- pokus o přímé otevření nebo změnu chráněného objektu přes URL nebo ručně sestavený HTTP požadavek.

RC nesmí oslabit existující selector, service ani permission kontrakty jen proto, aby UI prošlo testy.

#### G. Použitelné skutečné UI

- globální shell obsahuje Přehled a stabilní navigaci oddělenou od sekce Osoby,
- sekce Osoby odpovídá uvnitř shellu dvousloupcovému konceptu seznam/detail na desktopu,
- mobilní zobrazení je funkčně použitelné bez nutnosti zoomu a bez funkcí dostupných pouze hoverem,
- základní vizuální systém vychází ze schváleného UI/UX návrhu,
- světlý i tmavý motiv jsou alespoň funkčně použitelné; RC nevyžaduje finální kosmetické vyladění,
- běžné loading, empty, validation a permission stavy nejsou nahrazeny debug výstupem nebo Django Adminem,
- výsledný průchod musí být ověřen v reálném browseru, nikoli pouze testovacím klientem.

#### H. Kontrolní brána projektu

Před označením RC 0.1 za hotové musí projít minimálně:

```text
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
```

Dále musí být ověřeno:

- cílené testy nového uživatelského průchodu,
- nezávislý QA review,
- nezávislý security/access-control review,
- UI/UX review v prohlížeči pro desktop a mobilní šířku,
- konzistence implementace s aktuální dokumentací,
- čistý diff bez tajemství, lokální databáze, cache a nesouvisejících změn.

### RC 0.1 – co do cíle záměrně nepatří

Pokud následující funkce nejsou nutné jako závislost výše uvedeného průchodu, jejich dokončení **není podmínkou RC 0.1**:

- kompletní UI všech událostí,
- kompletní editace vztahů,
- kompletní UI bydlišť a hrobových míst,
- materiály, fotografie a zdroje v plném rozsahu,
- zdravotní UI,
- PDF export osoby,
- samostatný rodokmen,
- kompletní časová osa,
- pokročilé vyhledávání a všechny filtry,
- finální auditní UI,
- kompletní archivace a obnova přes UI,
- finální vizuální polish a všechny budoucí možnosti personalizace.

Existující backendové funkce z těchto oblastí se nesmějí odstranit, obejít nebo účelově oslabit. Agent má používat a zachovávat již implementované části a regresní testy.

### Aktuální ověřený stav RC 0.1

Oblast A má implementovaný reprodukovatelný lokální postup:

- dokumentace vede čistý checkout od Python 3.14 přes izolovaný `venv`,
  instalaci jediného deklarovaného balíčku, lokální tajný klíč a migrace až
  ke spuštění serveru,
- lokální konfigurace, databáze a launcher artefakty zůstávají mimo Git,
- lokálně omezený `seed_demo_data` vytvoří syntetické osoby pro tři
  přístupové úrovně, při zachování markerů je idempotentní, podporuje
  `--dry-run`, nic nemaže ani nepřepisuje a neobsahuje demo hesla nebo jiná
  tajemství; při `DEBUG=False` selže bez zápisu.
- dvě další veřejné demo osoby a tři označené životní události umožňují ručně
  ověřit narození, úmrtí, věk, stav a viditelné římské pořadí,
- interaktivní `bootstrap_demo_accounts` vytvoří nebo resetuje lokálního
  Čtenáře, Editora a Správce s přesnými skupinami; heslo zadává tester skrytě,
  příkaz je nevypisuje ani neukládá v otevřené podobě a mimo `DEBUG=True`
  selže bez zápisu,
- izolovaný Windows clean-snapshot smoke test prošel vytvořením nového
  Python 3.14 `venv`, instalací z `requirements.txt`, všemi migracemi,
  dry-runem, prvním i opakovaným seedem, `manage.py check` a HTTP 200 ze
  skutečně spuštěného vývojového serveru; POSIX varianta byla zkontrolována
  staticky proti stejným projektovým vstupům.

Oblast A je tím pro RC 0.1 splněna. Její regresní brána zůstává součástí
závěrečného ověření celého kandidáta.

Oblast D má implementovaný autentizační a rolový základ:

- funguje standardní session login, bezpečný lokální návrat a CSRF chráněný
  POST logout; neaktivní účet se nepřihlásí,
- topbar rozlišuje anonymní a přihlášený stav a po změně session se seznam
  přepočítá podle aktuální centrální access policy,
- Čtenář zůstává bez editace, Editor a Správce dostávají konkrétní
  `people.change_person`; `is_staff`, superuser a zvýšená obsahová permission
  zachovávají samostatný dokumentovaný význam,
- cílené testy pokrývají anonymního uživatele, neplatný i neaktivní login,
  bezpečný `next`, logout/CSRF a praktický obsahový rozdíl rolí.
- lokální tester může všechny tři role reprodukovatelně vytvořit nebo jim
  resetovat přihlašovací údaje bez commitnutého či vypsaného hesla.

Oblast D je pro RC 0.1 splněna. Skutečný browser průchod ověřil
přihlášení Editora i Čtenáře, změnu viditelné kohorty podle role, POST
odhlášení a návrat do anonymního stavu.

Oblast E má implementovanou jednoduchou editaci základních údajů osoby:

- oprávněný actor otevře formulář přímo z detailu, zatímco UI i server
  respektují `people.change_person` a viditelnost konkrétní osoby,
- jméno, příjmení, pohlaví, kategorie a poznámka se ukládají přes
  transakční `update_person_basic()` s validací a zámkem aktuálního řádku;
  služba mění jen rozsah formuláře a ostatní údaje zachová z čerstvého řádku,
- přístup, ověření, lifecycle, autorství, narození a úmrtí formulář nemění;
  klientsky podstrčená pole jsou ignorována,
- HTMX po úspěchu obnoví detail i položku seznamu bez reloadu, zobrazí
  potvrzení a nastaví detailovou URL; validační chyby a zadané hodnoty
  zůstávají ve formuláři,
- cílené testy pokrývají service rollback, permission matice, neaktivního
  actora, skrytý cíl, CSRF, metody, tampering, validaci a OOB fragment.

Oblast E je pro RC 0.1 splněna. Browser ověřil otevření formuláře z
detailu, serverovou validační chybu, platný HTMX zápis bez reloadu, potvrzení
v UI i následnou obnovu demo záznamu. Čtenář editační akci nevidí a
přímá editační URL mu vrací 403.

Vertikální řez B+C+G a navazující UI foundation jsou implementovány:

- kořenová URL zobrazuje Přehled pouze ze skutečných actor-visible dat a
  globální navigace odděluje Přehled, Osoby a jasně plánované budoucí oblasti,
- sekce Osoby čte skutečné, pro actora viditelné osoby z databáze,
- výchozí seznam i detail bezpečně vylučují archivované a měkce odstraněné
  osoby a jednotně skrývají existenci neviditelného přímého cíle,
- detail se načítá jako plná stránka i HTMX fragment a používá lokálně
  verzovaný HTMX asset,
- existuje dvousloupcový desktopový základ, mobilní vysouvací seznam,
  světlý a tmavý motiv a použitelné empty, loading a 404 stavy; výchozí je
  tmavý motiv a lokální preference se zachovává mezi návštěvami,
- desktopový i mobilní list/detail průchod včetně opakované HTMX výměny,
  výběru osoby, motivu a mobilního zavření panelu prošel reálným browserem,
- Person a navazující jména a vztahy v Django Adminu respektují stejnou
  čtecí policy a zůstávají pouze pro čtení; zápis osoby vede aplikační
  editační průchod přes doménovou službu,
- seznam a detail podle ACP-007 zobrazují pouze z viditelných zdrojů odvozené
  narození, úmrtí, životní stav, spolehlivě určitelný věk a římské pořadí ve
  viditelné kohortě; neúplná ani duplicitní data nezískávají falešnou přesnost,
- cílené automatické testy pokrývají access matice, čerstvý stav actora,
  lifecycle, přímou URL, HTMX, admin bypass a neprozrazující odvození.

Závěrečný browser průchod na desktopu 1280×720 a mobilu 390×844
ověřil list/detail, výběr osoby, actor-specific odvozené údaje, mobilní
panel bez horizontálního overflow a světlý i tmavý motiv. Sekvenční UI/UX
review hlavního agenta nenašel blocker; samostatné subagent browser review
nebylo v jeho izolovaném prostředí technicky dostupné.

Navazující browser průchod UI foundation ověřil na desktopu 1440×900 globální
navigaci, Přehled i zachovaný HTMX list/detail v sekci Osoby, na tabletu
768×900 globální drawer vedle použitelného dvousloupcového pohledu Osob a na
mobilu 390×844 samostatné globální a person-list drawery bez horizontálního
overflow. Světlý i tmavý motiv zůstaly použitelné a explicitní volba přežila
reload; zavřené drawery jsou vyřazeny z focus a accessibility toku a Escape
vrací focus na jejich ovládací prvek.

Oblasti B, C a G jsou tím pro RC 0.1 splněny. Bezpečnostní oblast F je
doložena cílenými testy a nezávislým security review bez blockeru. Závěrečná
brána H prošla `manage.py check`, `makemigrations --check --dry-run`, 1020
automatickými testy, cílenými testy průchodu, nezávislým QA a security review,
kontrolou dokumentace, diffu, tajemství a lokálních artefaktů.

Všechna povinná acceptance kritéria A–H jsou splněna. RC 0.1 je připraven
na větvi `agent/rc-0.1`; nejde o schválení produkčního nasazení, merge do
`feature/mvp` nebo `main` ani o dokončení pozdějších fází roadmapy.

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
