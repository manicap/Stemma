# Funkční specifikace

**Dokument:** 02  
**Verze:** 0.17
**Stav:** pracovní návrh  
**Datum revize:** 22. 7. 2026

## 1. Hlavní obrazovka

Desktopové rozhraní používá dvousloupcový model:

- vlevo je trvale viditelný seznam osob,
- vpravo je detail právě vybrané osoby,
- kliknutí na osobu změní pouze detail vpravo,
- vybraná osoba je v seznamu zřetelně zvýrazněna,
- změny se po uložení bez obnovení stránky promítnou do všech souvisejících částí rozhraní.

Na tabletu zůstává dvousloupcové rozhraní, ale seznam lze sbalit. Na telefonu se seznam otevírá jako panel vysunutý zleva a po výběru osoby se automaticky zavře.

Horní lišta obsahuje piktogram rozvětveného stromu, název Stemma, přepínač světlého a tmavého režimu a přihlášení nebo profilové menu.

## 2. Seznam osob

Každý záznam osoby obsahuje:

- malou fotografii nebo výchozí bustu vlevo přes dva textové řádky,
- jméno a příjmení,
- automatickou římskou číslici u shodných jmen,
- datum nebo rok narození a úmrtí,
- kategorii osoby.

Nad seznamem jsou:

- vyhledávání s našeptávačem,
- filtr kategorie,
- rozbalovací nabídka řazení,
- pro oprávněného uživatele tlačítko + Přidat osobu.

Výchozí řazení je Od nejmladších. Další možnosti:

- Od nejstarších,
- Příjmení A–Z,
- Příjmení Z–A,
- Jméno A–Z,
- Jméno Z–A.

Osoby bez známého data narození se při řazení podle věku zobrazují až za osobami se známým datem.

Vyhledávání pracuje minimálně s:

- jménem,
- příjmením,
- rodným příjmením,
- dalšími jmény,
- přezdívkou,
- rokem narození.

Vyhledávání nerozlišuje velikost písmen a je tolerantní k diakritice.

Archivované osoby se ve výchozím seznamu nezobrazují. Oprávněný uživatel je může zobrazit zvláštní volbou filtru.

## 3. Detail osoby

Záhlaví detailu zůstává viditelné při přepínání karet a obsahuje:

- hlavní fotografii nebo výchozí bustu,
- celé jméno,
- rodné příjmení,
- římskou číslici,
- kategorii osoby,
- pohlaví,
- datum narození,
- datum úmrtí,
- automaticky vypočítaný věk,
- navigaci Zpět a Vpřed v historii zobrazených osob,
- tlačítko Upravit osobu podle oprávnění,
- tlačítko pro vytvoření souhrnného PDF A4.

Pod záhlavím jsou záložky:

- Přehled,
- Vztahy,
- Události,
- Bydliště,
- Zdraví,
- Materiály.

Výchozí záložkou je Přehled. Aktivní záložka je zřetelně označena textem, pozadím a barevnou spodní linkou.

Podrobný vzhled a chování rozhraní definuje `10_UI_UX_NAVRH.md`.

## 4. Osoba

Základní údaje osoby:

- jméno,
- příjmení,
- rodné příjmení,
- další používaná jména,
- přezdívka,
- pohlaví,
- tituly,
- stručná poznámka,
- hlavní fotografie.

Narození a úmrtí nejsou uloženy jako běžná pole osoby, ale jako speciální typy událostí.

## 5. Automatický stav a věk

- Osoba je považována za zemřelou, pokud existuje událost typu Úmrtí.
- Pokud událost Úmrtí neexistuje, osoba je považována za žijící.
- Věk žijící osoby se počítá k aktuálnímu datu.
- Věk zemřelé osoby se počítá k datu úmrtí.
- Při neúplném datu se zobrazí pouze údaj, který lze spolehlivě odvodit.

## 6. Římské číslování

Pokud existuje více osob se stejným jménem a příjmením:

- aplikace je chronologicky seřadí podle narození,
- přidělí jim římské číslice I., II., III. atd.,
- číslice se neukládá ručně,
- zobrazuje se v seznamu i v detailu,
- při doplnění starší osoby se pořadí automaticky přepočítá.

Osoby bez známého data narození se zařadí za osoby s datem narození.

## 7. Události

Událost může být spojena s jednou nebo více osobami.

Podporované typy zahrnují:

- narození,
- křest,
- sňatek,
- rozvod,
- stěhování,
- studium,
- maturitu,
- vojenskou službu,
- zaměstnání,
- úmrtí,
- pohřeb,
- jinou vlastní událost.

Úraz, operace, očkování a další zdravotní skutečnosti se ukládají jako
zdravotní záznamy, nikoli současně jako obecné události.

Událost může obsahovat:

- přesné, neúplné nebo přibližné datum,
- období od–do,
- název,
- typ,
- místo,
- popis,
- účastníky a jejich role,
- přílohy,
- zdroje,
- přístupovou úroveň.

Příčina a okolnosti úmrtí se ukládají ve specializovaném detailu
`DeathDetail` propojeném s událostí úmrtí.

## 8. Vazby mezi osobami

Vazby jsou univerzální a ukládají se pouze jednou.

Příklady:

- biologický rodič,
- adoptivní rodič,
- nevlastní rodič,
- pěstoun,
- dítě,
- partner,
- manžel,
- sourozenec,
- kmotr,
- poručník,
- vlastní typ vazby.

Aplikace automaticky odvodí opačný směr vazby.

Příklad:

- Jan je otcem Petra,
- Petr je synem Jana.

Název opačné vazby se přizpůsobí pohlaví osoby, pokud je známé.

Typy vazeb jsou uživatelsky rozšiřitelným číselníkem. Každý typ určuje
zobrazené názvy obou směrů ve variantě pro muže, ženu a neznámý gender,
pevnou kategorii, symetrii, podporu časového rozmezí a možnost odvození
z jiných strukturovaných údajů.

Základní systémový katalog obsahuje biologického, adoptivního, nevlastního
a pěstounského rodiče, poručníka, manželství, partnerství, biologické,
adoptivní, nevlastní a sociální sourozenectví, kmotrovství, rodinné
přátelství a jinou vazbu. Samostatné typy dítě, syn a dcera nevznikají;
jejich označení poskytuje opačný směr rodičovské vazby.

Uložený směr A → B je významový: osoba A je výchozí a osoba B cílová.
Název směru A → B popisuje osobu B a vybírá se podle jejího genderu;
název opačného směru popisuje osobu A a vybírá se podle genderu osoby A.
Při neznámém nebo chybějícím genderu se použije neutrální varianta.
U symetrické vazby pořadí osob význam nemění a názvy obou směrů jsou pro
každou genderovou variantu shodné.

Jeden záznam vazby představuje jedno souvislé období vztahu. Stejné osoby
mohou mít více záznamů stejného typu s odlišným časovým vymezením, například
dvě samostatná manželství. Překrývající se, ale neidentická období se v této
etapě nezakazují.

Čas vztahu používá společný model neúplného data:

- `UNKNOWN` znamená neznámý čas vztahu,
- `EXACT` přesné datum vzniku vztahu,
- `MONTH` měsíc vzniku vztahu,
- `YEAR` rok vzniku vztahu,
- `RANGE` známé období platnosti se začátkem a koncem.

Technická horní mez u přesného data, měsíce nebo roku neznamená konec
vztahu; slouží pouze k řazení a porovnání. Rozmezí je možné jen u typu
vztahu, který je podporuje.

Biologické sourozenectví se odvozuje čtecím doménovým selectorem
`get_biological_siblings(*, person)` v `people/selectors.py`. Dvě různé
osoby jsou biologickými sourozenci, sdílejí-li alespoň jednoho biologického
rodiče prostřednictvím měkce neodstraněných vztahů typu
`biological_parent`. Plní a poloviční biologičtí sourozenci se zatím
nerozlišují a počet společných rodičů se nevrací.

Archivace, neaktivita typu ani časové vymezení rodičovského vztahu odvození
neovlivňují; měkce odstraněný vztah se nezapočítává. Výsledek může obsahovat
archivovanou, nikoli však měkce odstraněnou osobu. Vstupní osoba může být
archivovaná i měkce odstraněná, pokud její databázový řádek existuje.
Explicitně uložené sourozenecké vztahy se s výsledkem neslučují.

Selector vrací lazy `QuerySet[Person]` ve standardním pořadí osoby a nic
neukládá. Jde o nízkoúrovňový doménový dotaz bez uživatelského kontextu;
před zveřejněním ve view, API, šabloně nebo exportu musí vyšší aplikační
vrstva uplatnit přístupovou úroveň a pravidla viditelnosti.

Agregovaný přehled `get_sibling_overview(*, person)` spojuje biologicky
odvozené sourozence s explicitními vztahy `sibling`, `adoptive_sibling`,
`step_sibling` a `social_sibling`. Každou osobu vrací jednou a zachovává
všechny zjištěné důvody ve stabilním pořadí: `biological`, `sibling`,
`adoptive_sibling`, `step_sibling`, `social_sibling`. Odvozený kód
`biological` není typem uloženého vztahu.

Výsledkem je tuple neměnných položek `SiblingOverviewItem`, které obsahují
osobu a tuple kódů důvodů. Explicitní vztah se vyhodnocuje na obou stranách,
musí být měkce neodstraněný a může být archivovaný, neaktivního typu nebo
historicky ukončený. Výsledná osoba může být archivovaná, ale nesmí být
měkce odstraněná. Položky se řadí podle příjmení, jména a PK.

Agregovaný selector nic neukládá a pracuje bez uživatelského kontextu.
Vyšší aplikační vrstva musí před zveřejněním ověřit viditelnost osoby i
jednotlivých explicitních důvodů; permissionless výsledek nesmí přímo
obcházet oprávnění ve view, API ani exportu.

Celkový čtecí přehled `get_relationship_overview(*, person)` sjednocuje
všechny explicitní vazby osoby s biologicky odvozenými sourozenci. Každou
druhou osobu vrací jednou a její vztahy popisuje tuple neměnných položek
`RelationshipOverviewReason`. Jeden důvod obsahuje kategorii, technický kód,
směrový genderovaný název, ID všech odpovídajících explicitních vazeb a
příznak odvození.

Explicitní vztahy používají aktuální kategorii, pořadí a názvy svého
`RelationshipType`, včetně uživatelsky vytvořených typů. Název se vybírá
podle skutečné strany vztahu a genderu druhé osoby. Biologicky odvozený
sourozenec používá kategorii `sibling`, kód `biological`, nemá přímé ID
`Relationship` a zobrazuje se jako „Biologický bratr“, „Biologická sestra“
nebo „Biologický sourozenec“ podle genderu druhé osoby.

Více historických řádků stejného typu a stejného směrového názvu se sloučí
do jednoho důvodu; všechna jejich ID zůstanou zachována ve vzestupném
pořadí. Důvody se stabilně řadí podle kategorie, odvozený biologický důvod
před ostatními sourozeneckými důvody a dále podle pořadí typu, kódu a
názvu. Osoby se řadí podle příjmení, jména a PK.

Přehled zahrnuje archivované, neaktivní a historické explicitní vztahy,
nikoli měkce odstraněné. Archivovaná výsledná osoba se zahrne, měkce
odstraněná nikoli. Archivovaný nebo měkce odstraněný vstup lze zpracovat,
pokud jeho databázový řádek existuje. Selector má konstantní dotazový
profil bez N+1, nic neukládá a nevytváří migraci.

`relationship_ids` zachovávají provenance pro následnou aplikační kontrolu
přístupu, ověření a historických údajů. Selector sám nemá uživatelský
kontext a nefiltruje oprávnění. Vyšší vrstva musí před zveřejněním ověřit
výslednou osobu, všechny explicitní vztahy i viditelnost biologicky
odvozeného důvodu a odstranit položky bez viditelného důvodu.

Autorizovaný přehled poskytuje
`get_visible_relationship_overview(*, person, actor)`. Nejprve ověří
actora a aktuální databázový stav vstupní osoby. Neviditelný vstup odmítne
obecnou `PermissionDenied`, zatímco neuložená nebo fyzicky chybějící osoba
zachová `person_unsaved`. Viditelnost osoby vždy kombinuje její
`access_level` s lifecycle pravidly; archivovaná osoba vyžaduje
`people.view_archived_person` a měkce odstraněný vstup
`people.view_deleted_person`.

Selector filtruje permissionless výsledek bez jeho změny. Neviditelné nebo
měkce odstraněné výsledné osoby odstraní; archivované výsledné osoby
zobrazí jen s oprávněním. U explicitního důvodu ponechá pouze viditelná,
měkce neodstraněná `relationship_ids`; prázdný důvod a následně i položku
bez důvodu odstraní. Archivace vztahu, časová platnost ani aktivita typu
viditelnost nemění.

Biologický důvod vyžaduje alespoň jednoho stejného společného rodiče,
který je actorovi viditelný a má k oběma osobám viditelnou, měkce
neodstraněnou hranu `biological_parent`. Hrany od různých rodičů nelze
kombinovat. Měkce odstraněný rodič cestu nikdy neautorizuje; archivovaný
rodič vyžaduje lifecycle oprávnění. Pořadí osob, důvodů i ID zůstává podle
permissionless přehledu. Dávkové dotazy zajišťují konstantní profil bez
N+1 a selector nic nezapisuje ani nevytváří migraci.

## 9. Bydliště

Osoba může mít libovolný počet záznamů bydliště.

Typ bydliště je uživatelsky rozšiřitelný číselník `ResidenceType`.
Systémový katalog rozlišuje hlavní, dočasné, úřední, institucionální a jiné
bydliště. `primary_residence` označuje faktické hlavní nebo obvyklé
bydliště, zatímco `official_residence` administrativně evidovanou adresu;
tyto významy nejsou zaměnitelné. Kódy `permanent` a
`permanent_residence` se nepoužívají, aby se katalog nezaměňoval s českým
právním pojmem trvalého pobytu.

M2.6b zavádí konkrétní model `Residence` pro jeden souvislý pobyt jedné
osoby. Povinně odkazuje na `Person` a `ResidenceType`; volitelně na
strukturované `Place`. Adresní nebo historický lokalizační detail ukládá do
`address_text` o délce nejvýše 500 znaků a poznámku do `note`. Musí být
vyplněno alespoň `Place` nebo neprázdný `address_text`, přičemž obě hodnoty
mohou být použity současně.

Období používá společný `PartialDateModel` a podporuje neznámý, přesný,
částečný i rozsahový údaj podle aktuálních projektových voleb. Residence
rovněž přebírá přístupovou úroveň, stav ověření, autora, lifecycle a časová
razítka. Vazby na osobu, typ i místo používají `PROTECT`. Překryvy i více
samostatných nebo zdánlivě duplicitních pobytů jsou povoleny; model nemá
vlastní unikátní constraint ani dodatečný explicitní index.

Neaktivní existující typ je na modelové vrstvě přípustný. Samotný krok
M2.6b ještě neimplementoval pravidla zápisu, služby, selectory, oprávněné
čtení, zdroje, přílohy ani uživatelské rozhraní.

M2.6c zavádí v `places.services` transakční zápisové API
`create_residence()` a `update_residence()` nad frozen slotted
`ResidenceInput`. Vstup je úplný snapshot editovatelných údajů, nikoli
částečný patch. Při aktualizaci lze opravit osobu, typ, místo, texty,
přístup, ověření i historické datum; `place=None` strukturované místo
odstraní. Autor vytvoření a lifecycle metadata se nemění.

Služby načítají aktuální databázový stav osoby, typu, volitelného místa,
autora a při update samotného Residence. Nový záznam ani přechod nesmí
použít neaktivní typ, ale existující neaktivní typ lze zachovat. Archivované
i měkce odstraněné stále existující osoby a místa jsou na této zápisové
vrstvě přípustné; oprávnění se zde neposuzují. Archivovaný Residence lze
upravit, měkce odstraněný nikoli.

Okrajové mezery se odstraňují z `address_text`, `note`,
`original_date_text` a `date_note`. Každý zápis probíhá v
`transaction.atomic()`, používá `full_clean()` před `save()` a update zamyká
aktuální Residence pomocí `select_for_update()`. Služba nededuplikuje a
obecný `IntegrityError` nepřevádí.

M2.6d přidává permissionless selector
`get_person_residences(*, person)` vracející lazy `QuerySet[Residence]` s
úplnou historií jedné osoby. Zahrnuje neznámé, historické, budoucí a
přibližné údaje, archivované Residence, neaktivní i uživatelské typy a
všechny přístupové úrovně. Vylučuje pouze měkce odstraněné Residence.
Archivovanou i měkce odstraněnou vstupní osobu lze zpracovat, pokud její
řádek stále existuje.

Výsledek se řadí podle `sort_date`, `sort_date_end`, pořadí a názvu typu a
PK. Selector používá `select_related()` pro osobu, typ, místo a autora;
provedení tvoří jeden validační `exists()` dotaz a jeden SELECT při
vyhodnocení QuerySet bez N+1. Nevyhodnocuje dnešní datum, aktuální nebo
hlavní bydliště, přístup ani oprávnění. Výsledek proto nesmí být přímo
zveřejněn ve view, API nebo exportu. Autorizovaný selector vznikne v M2.6e.

M2.6e přidává veřejný autorizovaný selector
`get_visible_person_residences(*, person, actor)`. Vrací lazy
`QuerySet[Residence]` odvozený z permissionless selectoru. Actor se ověřuje
podle společné `AccessLevel` policy a vstupní osoba podle svého aktuálního
databázového stavu. Archivovaná osoba vyžaduje
`people.view_archived_person`, měkce odstraněná
`people.view_deleted_person` a osoba v obou stavech obě oprávnění.
Neviditelný vstup vyvolá obecnou `PermissionDenied`; neuložená nebo fyzicky
chybějící osoba zachovává `person_unsaved`.

Po autorizaci osoby se Residence databázově filtrují pouze přes
`access_level__in`. Archivované Residence zůstávají zahrnuté bez
samostatného lifecycle oprávnění, měkce odstraněné zůstávají vyloučené.
Typ, místo, stav ověření ani historická či budoucí platnost viditelnost
nemění. Pořadí a `select_related()` z M2.6d se zachovávají; SELECT Residence
zůstává lazy a počet validačních, permission i výsledných dotazů je
konstantní vzhledem k počtu pobytů. M2.6e nevytváří migraci, UI, API ani
export.

## 10. Fotografie

Každá osoba může mít:

- jednu hlavní fotografii,
- libovolný počet dalších fotografií.

Pokud hlavní fotografie neexistuje, zobrazí se silueta busty.

Každá fotografie může obsahovat:

- název,
- popis,
- datum nebo přibližný rok,
- autora,
- původ,
- osoby na fotografii,
- místo,
- zdroj,
- přístupovou úroveň.

## 11. Dokumenty a přílohy

Příloha je univerzální objekt pro:

- obrázky,
- PDF,
- textové dokumenty,
- tabulky,
- audio,
- video,
- ZIP a další soubory.

Stejná příloha může být propojena s více osobami, událostmi, zdroji nebo hrobovými místy.

## 12. Zdravotní informace

Zdravotní informace tvoří samostatnou záložku.

Každý záznam může obsahovat:

- datum,
- název,
- typ,
- popis,
- lékaře nebo zařízení,
- přílohy,
- poznámku,
- přístupovou úroveň.

Typy zahrnují:

- očkování,
- diagnózu,
- vyšetření,
- operaci,
- úraz,
- alergii,
- léky,
- jiný zdravotní záznam.

## 13. Hrobová místa

Hrobové místo je samostatný objekt, nikoli událost.

Může obsahovat:

- název,
- hřbitov,
- obec,
- oddíl,
- řadu,
- číslo hrobu,
- GPS souřadnice,
- fotografie,
- přepis nápisu,
- popis,
- stav existující/zaniklý,
- odkazy na externí databáze.

Jedno hrobové místo může být propojeno s více osobami.

M2.7a potvrzuje budoucí hlavní model `GraveSite` a samostatné propojení
`PersonGraveSite`, ale zatím je neimplementuje. Zavádí pouze rozšiřitelné
číselníky `GraveSiteType`, `PersonGraveSiteRole` a pevný výčet
`GraveSiteStatus`.

Systémové typy hrobového místa jsou `grave`, `tomb`, `urn_site`, `ossuary`,
`scattering_place`, `memorial`, `cenotaph` a `other`. Rodinné nebo společné
užití se vyjádří propojením více osob; celé kolumbárium může být později
samostatné `Place`, zatímco konkrétní schránka je `urn_site`.

Pevný fyzický stav místa má právě hodnoty `existing`, `destroyed` a
`unknown`. Přemístění ostatků není stav místa a důvěryhodnost záznamu řeší
společný `VerificationStatus`. Stav `destroyed` automaticky nearchivuje,
měkce neodstraňuje ani nemění ověření záznamu.

Systémové role propojení osoby jsou `buried`, `urn_placed`,
`ashes_scattered`, `commemorated`, `remains_relocated_from`,
`remains_relocated_to` a `other`. Typ `cenotaph` označuje povahu objektu,
zatímco role `commemorated` vztah konkrétní osoby k němu. Směrové role
přemístění rozlišují původní a cílové místo; samotné propojení konkrétního
přesunu v M2.7a nevzniká.

M2.7b implementuje `GraveSite` jako jeden konkrétní fyzický nebo pamětní
objekt. Není obecným `Place`, pohřební událostí ani vazbou osoby. Povinně
odkazuje na `GraveSiteType` a používá fyzický `GraveSiteStatus`; volitelný
`Place` představuje širší strukturovanou lokalitu.

Objekt může současně obsahovat textovou lokalitu, název hřbitova, oddíl,
řadu, číslo hrobu, přepis nápisu, přesné souřadnice a poznámku. Alespoň
jedna lokalizace musí být určena pomocí `Place`, neprázdného
`location_text`, neprázdného `cemetery_name` nebo úplné dvojice souřadnic.
Textové hodnoty tvořené jen whitespace se nepovažují za lokalizaci.
Zeměpisná šířka a délka musí být zadány společně a respektovat rozsahy
-90 až 90 a -180 až 180.

`GraveSite` používá přístup, ověření, autora, timestamp a lifecycle, ale
nemá vlastní `PartialDateModel`. Datum pohřbu, vzniku památníku nebo přesunu
není vlastností tohoto objektu. Fyzický status se nemění automaticky s
archivací nebo měkkým odstraněním. Model nepoužívá unikátnost lokalizačních
údajů ani deduplikaci; typ a `Place` jsou chráněny přes `PROTECT`.
`PersonGraveSite`, služby a selectory vzniknou až v dalších krocích.

## 14. Viditelnost a zamčený obsah

Navržené úrovně viditelnosti:

- veřejné,
- pouze přihlášení,
- omezené,
- pouze správce.

Pokud uživatel nemá oprávnění:

- aplikace může zobrazit, že sekce nebo záznam existuje,
- nezobrazí jeho obsah,
- zobrazí vysvětlení a případně výzvu k přihlášení.

Přesný obecný význam přístupových úrovní je:

- `public` vidí každý včetně anonymního a neaktivního uživatele,
- `authenticated` vidí pouze uložený, existující a aktivní přihlášený
  uživatel,
- `restricted` vidí aktivní uživatel s oprávněním
  `accounts.view_restricted_content` nebo aktivní superuser,
- `admin_only` vidí aktivní uživatel s oprávněním
  `accounts.view_admin_only_content` nebo aktivní superuser.

Příznak `is_staff` sám obsahový přístup nerozšiřuje. Neaktivní uživatel,
včetně neaktivního superusera, se pro přístupovou úroveň posuzuje jako
anonymní návštěvník. Obecné vyhodnocení poskytuje keyword-only helper
`can_view_access_level(*, actor, access_level)` v `common/permissions.py`.

Zobrazení archivované osoby vyžaduje oprávnění
`people.view_archived_person` a zobrazení měkce odstraněné osoby oprávnění
`people.view_deleted_person`. Tato lifecycle oprávnění nenahrazují kontrolu
`access_level`. Autorizovaný přehled vztahů je používá pro vstupní osobu,
výsledné osoby a společné biologické rodiče; měkce odstraněné výsledné
osoby ani rodiče nezveřejňuje.

## 15. Historie změn

U důležitých záznamů se eviduje:

- kdo změnu provedl,
- kdy,
- který objekt a pole změnil,
- původní a nová hodnota,
- případný komentář.

## 16. Mazání

Důležité záznamy se fyzicky nemažou okamžitě.

Použije se:

- archivace,
- měkké odstranění,
- možnost obnovy,
- varování při existujících vazbách.
