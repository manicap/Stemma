# Návrh datového modelu

**Dokument:** 03  
**Verze:** 0.22
**Stav:** koncept  
**Datum revize:** 22. 7. 2026

## 1. Základní pilíře

Datový model stojí na třech hlavních entitách:

- Osoba – kdo,
- Událost – co a kdy se stalo,
- Vazba – kdo je s kým propojen.

Další hlavní entity:

- Místo,
- Bydliště,
- Hrobové místo,
- Příloha,
- Zdroj,
- Zdravotní záznam,
- Uživatel,
- Změna.

## 2. Osoba

Navržená pole:

- ID,
- jméno,
- příjmení,
- rodné příjmení,
- další jména,
- přezdívka,
- pohlaví,
- kategorie osoby,
- titul před jménem,
- titul za jménem,
- stručná poznámka,
- ID hlavní fotografie,
- datum vytvoření,
- datum poslední změny,
- stav archivace.

Neukládá se přímo:

- datum narození,
- místo narození,
- datum úmrtí,
- místo úmrtí,
- příznak žije/zemřel,
- věk,
- římská číslice.

Tyto údaje se odvozují z událostí a pravidel aplikace.

### 2.1 Kategorie osoby

Každá osoba může být zařazena do jedné hlavní kategorie podle svého vztahu k rodině a významu v rodinném příběhu.

Základní kategorie:

1. **Přímá rodina** – přímí předci a potomci.
2. **Ostatní rodina** – sourozenci předků, jejich potomci, příbuzní sňatkem a další vzdálenější příbuzenstvo.
3. **Blízcí rodině** – rodinní přátelé, kmotři a další dlouhodobě blízké osoby, pokud již nepatří do některé rodinné kategorie.
4. **Duchovní** – farář nebo jiný duchovní významně spojený s rodinou.
5. **Další související osoby** – svědci, sousedé, zaměstnavatelé, hospodářští správci a jiné osoby důležité pro rodinný příběh.

Pravidla:

- kategorie je obecné zařazení osoby a nenahrazuje konkrétní vazby mezi osobami,
- kmotrovství, příbuzenství, partnerství a další konkrétní vztahy se nadále evidují jako vazby,
- pokud osoba splňuje více možností, přednost má rodinná kategorie,
- seznam kategorií má být spravován jako číselník, aby jej bylo možné později rozšířit bez změny struktury entity Osoba,
- kategorie může být dočasně nevyplněná, pokud zatím nelze osobu spolehlivě zařadit.

## 3. Událost

### 3.1 Typ události

Typ události je uživatelsky rozšiřitelný číselník. Vedle kódu, názvu,
popisu, pořadí, aktivity a systémového příznaku určuje:

- zda typ podporuje časové rozmezí,
- zda událost může mít místo,
- zda se nová událost tohoto typu ve výchozím stavu zobrazuje v přehledu,
- výchozí přístupovou úroveň nové události.

Systémové typy jsou narození, křest, sňatek, rozvod, stěhování, studium,
maturita, vojenská služba, zaměstnání, úmrtí, pohřeb a jiná událost.
Zdravotní skutečnosti se evidují jako zdravotní záznamy.

### 3.2 Záznam události

`Event` používá společná pole časových razítek, přístupu, ověření, autora,
životního cyklu a úplnou strukturu `PartialDateModel`. Vlastní pole jsou:

- povinný typ události,
- volitelné strukturované místo,
- `location_detail` pro dobový adresní nebo lokalizační detail,
- volitelný vlastní zobrazovaný název `title`,
- popis,
- uložený příznak `show_in_overview`.

Neznámé datum je platný stav. Rozmezí lze použít pouze u typu, který je
podporuje. Typ bez povoleného místa zakazuje strukturované místo i
neprázdný lokalizační detail.

Výchozí přístup a zobrazení v přehledu jsou snapshotové návrhy typu pro
novou událost. Budoucí doménová služba je při založení zkopíruje, pokud
uživatel nezadá vlastní hodnotu. Pozdější změna typu nebo jeho defaultů
existující událost nepřepisuje.

Pravidla:

- každá osoba může mít nejvýše jednu aktivní událost Narození,
- každá osoba může mít nejvýše jednu aktivní událost Úmrtí,
- sňatek je jedna společná událost propojená s více osobami,
- neznámé datum se nenahrazuje vymyšleným přesným datem.

Příčina a okolnosti úmrtí patří do samostatného specializovaného detailu
`DeathDetail` ve vztahu jedna ku jedné k události úmrtí.

## 4. Účast osoby na události

`EventParticipant` je samostatná spojovací entita a není součástí
základního modelu `Event`. Obsahuje povinné vazby na:

- existující osobu,
- událost,
- roli osoby v události,
- volitelnou poznámku ke konkrétní účasti.

Stejná osoba může mít v jedné události více různých rolí a stejnou roli
může mít více osob. Trojice událost, osoba a role je jedinečná; rozdílná
poznámka nepovoluje duplicitní účast.

Databázový constraint hlídá pouze přesnou duplicitu. Povolenost a aktivita
role, minimální a maximální počty a úplnost celé události budou ověřovány
budoucí transakční doménovou službou. Změna konfigurace nemá zpětně
zneplatňovat uložené historické účasti.

Role osoby je spravovatelný číselník. Systémové role jsou hlavní osoba,
narozená osoba, křtěná osoba, zemřelá osoba, manželský partner, rodič,
dítě, kmotr nebo kmotra, svědek, účastník a jiná role.

Manželský partner používá jedinou genderově neutrální technickou roli
`spouse`. Genderované označení je pouze odvozená zobrazovací logika.

Konfigurační model `AllowedEventRole` spojuje typ události s povolenou rolí
a určuje její minimální a maximální počet, pořadí a aktivitu. Nulové
minimum znamená nepovinnou roli, kladné minimum povinný počet a prázdné
maximum počet bez horního omezení. Každá dvojice typu a role má nejvýše
jedno konfigurační pravidlo.

## 5. Vazba mezi osobami

Pole:

- ID,
- osoba A,
- osoba B,
- typ vazby,
- datum od,
- datum do,
- textová podoba období,
- stav ověření,
- poznámka,
- přístupová úroveň,
- datum vytvoření,
- datum poslední změny,
- stav archivace.

Každý typ vazby definuje:

- označení směru A → B,
- označení směru B → A,
- varianty podle pohlaví,
- kategorii,
- zda je vazba symetrická,
- zda může být časově omezená.

`RelationshipType` je uživatelsky rozšiřitelný číselník odvozený pouze
z `LookupModel`. Vedle společných polí číselníku obsahuje:

- `forward_label_male`, `forward_label_female` a
  `forward_label_unknown` — povinné názvy osoby B z pohledu osoby A,
- `reverse_label_male`, `reverse_label_female` a
  `reverse_label_unknown` — povinné názvy osoby A z pohledu osoby B,
- `category` — pevnou kategorii vztahu,
- `is_symmetric` — zda pořadí osob nemění význam vztahu,
- `supports_date_range` — zda budoucí konkrétní vazba smí používat
  `DatePrecision.RANGE`,
- `is_derivable` — zda lze vztah odvodit z jiných strukturovaných údajů.

Pevné kategorie jsou rodič a dítě (`parent_child`), partnerství
(`partner`), sourozenectví (`sibling`), kmotrovství (`godparent`), péče
a poručenství (`care`), sociální vazba (`social`) a jiná vazba (`other`).

Osoba A je výchozí osoba uloženého vztahu a osoba B cílová osoba.
Genderová varianta názvu A → B se vybírá podle osoby B a varianta názvu
B → A podle osoby A. Varianta `unknown` se použije při neznámém nebo
chybějícím genderu. U symetrického typu musí být všechny tři dvojice
názvů obou směrů shodné.

Systémový katalog obsahuje kódy `biological_parent`, `adoptive_parent`,
`step_parent`, `foster_parent`, `guardian`, `spouse`, `partner`, `sibling`,
`adoptive_sibling`, `step_sibling`, `social_sibling`, `godparent`,
`family_friend` a `other`. Pouze biologické sourozenectví `sibling` je
v této etapě označeno jako odvoditelné. Samotný algoritmus odvození ani
konkrétní model `Relationship` nejsou součástí M2.5a.

### 5.1 Konkrétní vazba

`Relationship` je samostatná historická doménová entita. Dědí
`TimestampedModel`, `AccessControlledModel`, `VerifiableModel`,
`AuthoredModel`, `LifecycleModel`, `PartialDateModel` a `models.Model`.

Vlastní pole jsou:

- `relationship_type` — povinný `ForeignKey` na `RelationshipType`,
  `on_delete=PROTECT`, `related_name="relationships"`,
- `person_a` — povinný `ForeignKey` na `Person`, `on_delete=PROTECT`,
  `related_name="relationships_as_a"`,
- `person_b` — povinný `ForeignKey` na `Person`, `on_delete=PROTECT`,
  `related_name="relationships_as_b"`,
- `note` — `TextField(blank=True)` pro běžnou doménovou poznámku.

`person_a` je výchozí osoba a `person_b` cílová osoba. Opačný zobrazovaný
směr se odvozuje z typu a nevytváří druhý databázový řádek. U symetrického
typu je kanonické pořadí `person_a_id < person_b_id`; model pořadí pouze
validuje a doménová služba je před zápisem normalizuje.

Jeden řádek představuje jedno souvislé období. `UNKNOWN` znamená neznámý
čas, `EXACT`, `MONTH` a `YEAR` známý vznik vztahu a `RANGE` období platnosti
se začátkem a koncem. Technické `sort_date_end` u jednoduché přesnosti není
koncem vztahu. Rozmezí je povoleno pouze typem s
`supports_date_range=True`.

Stejná orientovaná trojice může mít více odlišných známých období, ale jen
jeden měkce neodstraněný záznam s neznámým časem. Archivované záznamy se do
unikátnosti nadále započítávají; měkce odstraněné nikoli. Rozdílná poznámka,
přístupová úroveň, stav ověření ani původní text data nemění identitu
období.

Model zakazuje vztah osoby k sobě. Pro známý čas a neznámý čas používá dva
samostatné podmíněné unikátní constrainty. Obrácená nesymetrická vazba je
jiné tvrzení. Odvoditelný typ lze explicitně uložit; M2.5b nic automaticky
neodvozuje a neřeší rodičovské cykly ani překryvy období.

Metadata jsou `verbose_name = "Vazba"`, `verbose_name_plural = "Vazby"`
a řazení podle typu, technických časových mezí, obou osob a primárního
klíče. Textová reprezentace používá formát
`"{person_a} – {relationship_type} – {person_b}"` s bezpečnými fallbacky.

### 5.2 Doménová služba vazeb

Veřejné zápisové rozhraní je v `people/services.py`. Používá frozen
dataclass se slots `RelationshipInput` a keyword-only funkce
`create_relationship(*, data, created_by=None)` a
`update_relationship(*, relationship, data)`. Vstup obsahuje typ, obě
osoby, poznámku, přístup, stav ověření a historické části
`PartialDateModel`; technické `sort_date` a `sort_date_end` se nepředávají.

Create nastavuje také volitelné `created_by`. Update může měnit typ, osoby,
poznámku, přístup, ověření a časový údaj, ale nemění autora, čas vytvoření
ani lifecycle pole. `updated_at` a technické meze zachovávají standardní
modelové chování.

Služba pracuje v `transaction.atomic()` s aktuálním databázovým stavem.
Update načítá vztah přes `select_for_update()`. Symetrické dvojice před
`full_clean()` normalizuje podle PK; nesymetrickou orientaci zachovává.
Archivované i měkce odstraněné osoby jsou povoleny, pokud jejich řádky
existují. Neaktivní typ nelze použít při create ani na něj přejít při
update; existující vztah může svůj neaktivní typ zachovat. Archivovaný
vztah lze upravit, měkce odstraněný nikoli.

Přesné duplicity běžně zachytí `full_clean()`. Souběžný `IntegrityError`
se po rollbacku převede na `duplicate_relationship` pouze tehdy, pokud
databázový dotaz potvrdí konflikt stejné schválené časové identity. Jiná
integritní chyba se nemaskuje. M2.5c nevytváří migraci a neřeší rodičovské
cykly, věk, překryvy období ani automaticky odvozené nebo opačné vztahy.

### 5.3 Rodičovský graf

Genealogický rodičovský graf tvoří pouze typy `biological_parent`,
`adoptive_parent`, `step_parent` a `foster_parent`. `person_a` je
rodičovská osoba, `person_b` dítě a orientovaná hrana proto vede
`person_a → person_b`. Všechny čtyři typy se vyhodnocují společně a cyklus
může být smíšený. `guardian` ani jiné systémové či uživatelské typy do
grafu automaticky nevstupují.

Do grafu se započítávají všechny měkce neodstraněné vztahy uvedených typů.
Archivace, neaktivita typu ani přesnost, stáří nebo ukončení časového údaje
rodičovský fakt nevyřazují. Měkce odstraněný vztah se nezapočítává.

Nová hrana `A → B` je odmítnuta, právě když v existujícím grafu vede cesta
`B → … → A`. Create validuje nový vztah; update vyloučí vlastní současný
řádek a ověří navrhovaný výsledný stav. Změna na nerodičovský typ může
starší cyklus odstranit. Nesouvisející starší nekonzistence jinde v grafu
změnu neblokuje. Stabilní chyba má klíč `person_b` a kód
`relationship_parent_cycle`.

Kontrola probíhá transakčně v doménové službě a načítá graf jedním
querysetem. Obecný grafový cyklus nelze vyjádřit běžným databázovým
constraintem. SQLite neposkytuje skutečné řádkové zámky a ani databáze se
zámky bez silnější izolace nemusí pokrýt všechny souběžné phantom scénáře.
M2.5d nemění model ani migrace a neřeší věk nebo překryvy období.

### 5.4 Odvození biologických sourozenců

Nízkoúrovňový doménový selector v `people/selectors.py` poskytuje veřejné
API:

```python
def get_biological_siblings(
    *,
    person: Person,
) -> QuerySet[Person]:
    ...
```

Osoba Y je biologickým sourozencem osoby X, pokud jsou různé a existuje
alespoň jedna osoba P, která je prostřednictvím měkce neodstraněného
`Relationship` typu `biological_parent` rodičem X i Y. Jeden společný rodič
stačí; plní a poloviční sourozenci se nerozlišují. Jiné rodičovské typy ani
explicitní `sibling`, `adoptive_sibling`, `step_sibling` nebo
`social_sibling` se do výsledku neslučují.

Rodičovský fakt přebírá lifecycle význam z M2.5d: započítává se při
`Relationship.deleted_at IS NULL` bez ohledu na archivaci, aktivitu typu,
přesnost nebo historické ukončení data. Výsledná `Person` musí mít
`deleted_at IS NULL`, ale může být archivovaná. Vstupní osoba musí mít PK a
existující databázový řádek; archivace ani měkké odstranění vstupu dotaz
neblokují. Neuložená nebo fyzicky chybějící osoba vyvolá `ValidationError`
s klíčem `person` a kódem `person_unsaved`.

Selector vrací lazy, databázově deduplikovaný `QuerySet[Person]` se
standardním `Person.Meta.ordering = ("last_name", "first_name")`. Nic
neukládá a nevytváří explicitní vztah. Nemá uživatelský kontext ani
nefiltruje `access_level`; vyšší aplikační vrstva musí před zveřejněním
výsledku uplatnit oprávnění a viditelnost. Toto oddělení není povolením
obejít serverovou kontrolu ve view nebo API. M2.5e nemění model ani migrace.

### 5.5 Agregovaný přehled sourozeneckých vazeb

`people/selectors.py` dále vystavuje neměnný dataclass a keyword-only
funkci:

```python
@dataclass(frozen=True, slots=True)
class SiblingOverviewItem:
    person: Person
    relationship_codes: tuple[str, ...]


def get_sibling_overview(
    *,
    person: Person,
) -> tuple[SiblingOverviewItem, ...]:
    ...
```

Přehled znovu používá `get_biological_siblings()` pro odvozený důvod
`biological` a přidává pouze explicitní typy `sibling`,
`adoptive_sibling`, `step_sibling` a `social_sibling`. Každou osobu seskupí
podle PK a zachová všechny důvody bez duplicit v uvedeném stabilním pořadí.
Kód `biological` není `RelationshipType.code` a nepředstavuje uložený
objekt.

Explicitní vztahy se hledají s osobou na straně A i B a nespoléhají na
kanonické pořadí ani na aktuální `is_symmetric`. Započítávají se při
`deleted_at IS NULL`; archivace, aktivita typu ani časové vymezení se
neposuzují. Výsledná osoba musí mít `deleted_at IS NULL`, ale může být
archivovaná. Vstupní lifecycle a chyba `person_unsaved` zůstávají shodné s
M2.5e.

Výsledný tuple se řadí podle `last_name`, `first_name` a PK jako
deterministického fallbacku. Implementace používá jeden existence dotaz,
jeden SELECT biologických sourozenců a jeden SELECT explicitních vztahů se
`select_related()`, tedy konstantní tři dotazy bez N+1.

Selector nic neukládá a nemá uživatelský kontext. Vyšší aplikační vrstva
musí před zveřejněním filtrovat viditelnost výsledných osob i jednotlivých
explicitních důvodů. M2.5f nemění model ani migrace.

### 5.6 Celkový agregovaný přehled vztahů

Celkový nízkoúrovňový read model v `people/selectors.py` vystavuje:

```python
@dataclass(frozen=True, slots=True)
class RelationshipOverviewReason:
    category: str
    relationship_code: str
    label: str
    relationship_ids: tuple[int, ...]
    is_derived: bool


@dataclass(frozen=True, slots=True)
class RelationshipOverviewItem:
    person: Person
    reasons: tuple[RelationshipOverviewReason, ...]


def get_relationship_overview(
    *,
    person: Person,
) -> tuple[RelationshipOverviewItem, ...]:
    ...
```

Jedna položka představuje jednu druhou osobu a jeden důvod je deduplikován
podle trojice kategorie, kód a zobrazený název. Explicitní důvod zachovává
všechna odpovídající `Relationship.pk` bez duplicit ve vzestupném pořadí a
má `is_derived=False`. Biologicky odvozený důvod má kategorii `sibling`,
kód `biological`, prázdné `relationship_ids` a `is_derived=True`.

Přehled znovu používá `get_sibling_overview()` a jeho veřejný kontrakt
nemění. Provenance čtyř explicitních sourozeneckých typů načítá samostatným
optimalizovaným dotazem. Ostatní explicitní typy, včetně uživatelských,
načítá druhým dotazem přes obě strany vztahu. Oba dotazy používají
`select_related()` a nevytvářejí N+1.

Směrový název popisuje druhou osobu: při vstupu na straně A se použije
`forward_label_*` podle genderu osoby B, při vstupu na straně B
`reverse_label_*` podle genderu osoby A. Neznámý nebo nerozpoznaný gender
používá variantu `unknown`. Odvozené biologické názvy jsou „Biologický
bratr“, „Biologická sestra“ a „Biologický sourozenec“.

Kategorie se řadí v pořadí `parent_child`, `partner`, `sibling`,
`godparent`, `care`, `social`, `other`; neznámá hodnota následuje až za
známými kategoriemi. Uvnitř kategorie je biologický důvod před explicitními
sourozeneckými důvody, poté rozhoduje `RelationshipType.sort_order`, kód a
název. Osoby se řadí podle příjmení, jména a PK.

Započítávají se explicitní vztahy s `deleted_at IS NULL` bez ohledu na
archivaci, aktivitu typu nebo časovou platnost. Výsledná osoba nesmí být
měkce odstraněná, ale může být archivovaná. Existující vstup lze zpracovat
bez ohledu na jeho lifecycle; neuložený nebo fyzicky chybějící vstup
zachovává chybu `person_unsaved`.

Selector nic neukládá, nemá parametr `actor` a nefiltruje přístupová práva.
Vyšší vrstva používá `relationship_ids` pro kontrolu konkrétních
explicitních záznamů a samostatně posuzuje viditelnost biologického důvodu.
M2.5g nemění modely, systémová data ani migrace.

### 5.7 Autorizovaný celkový přehled vztahů

Vyšší čtecí selector vystavuje keyword-only API:

```python
def get_visible_relationship_overview(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> tuple[RelationshipOverviewItem, ...]:
    ...
```

Používá stejné frozen dataclassy jako M2.5g. Vstupní osobu znovu načte z
databáze a před spuštěním permissionless přehledu ověří její přístupovou
úroveň i lifecycle. Neviditelný vstup vyvolá obecnou `PermissionDenied`;
neuložená nebo fyzicky chybějící osoba používá `person_unsaved`. Actor
zachovává chyby `actor_invalid` a `actor_unsaved` z obecné permission
policy.

Výsledná osoba musí mít viditelný `access_level`, nesmí být měkce
odstraněná a při archivaci vyžaduje `people.view_archived_person`.
Explicitní důvody se filtrují podle aktuálních měkce neodstraněných
`Relationship` a jejich `access_level`; z agregované provenance zůstanou
jen viditelná ID ve stávajícím vzestupném pořadí. Archivace vztahu,
neaktivita typu a historický čas se neposuzují.

Biologický důvod zůstane jen při kompletní viditelné cestě přes jednoho
společného rodiče: rodič i obě osoby jsou viditelné a obě orientované hrany
`biological_parent` rodič → dítě jsou měkce neodstraněné a přístupné.
Měkce odstraněný rodič cestu nikdy nevytváří a archivovaný vyžaduje
`people.view_archived_person`. Viditelné hrany různých rodičů se neslučují.

Čtyři hodnoty `AccessLevel` se vyhodnotí přes
`can_view_access_level()` nejvýše jednou za volání. Explicitní provenance i
biologické cesty se načítají dávkově a počet dotazů neroste s počtem osob,
důvodů, ID nebo rodičů. Nové položky zachovávají pořadí M2.5g a původní
permissionless frozen objekty se nemění. M2.5h-2 nic nezapisuje a nevytváří
modelovou změnu ani migraci.

## 6. Bydliště

`ResidenceType` je konkrétní uživatelsky rozšiřitelný číselník v aplikaci
`places`, který přímo dědí pouze z `LookupModel`. Nepřidává vlastní pole a
používá `code`, `name`, `description`, `sort_order`, `is_active` a
`is_system` s pořadím `sort_order`, `name`, `code`.

Systémové hodnoty jsou:

| Kód | Název | Pořadí | Význam |
|---|---|---:|---|
| `primary_residence` | Hlavní bydliště | 10 | Obvyklé nebo hlavní bydliště osoby v daném období. |
| `temporary_residence` | Dočasné bydliště | 20 | Časově omezené bydliště nebo pobyt mimo hlavní bydliště. |
| `official_residence` | Úřední bydliště | 30 | Administrativně nebo úředně evidovaná adresa, která nemusí odpovídat skutečnému pobytu. |
| `institutional_residence` | Institucionální pobyt | 40 | Pobyt v instituci, například internátu, kasárnách, nemocnici, ústavu nebo domově. |
| `other` | Jiné bydliště | 90 | Jiný druh bydliště nebo pobytu nezařaditelný do předchozích typů. |

Všechny systémové hodnoty jsou aktivní a systémové; uživatelské typy jsou
povolené. Hlavní bydliště je faktický údaj, kdežto úřední bydliště může být
jen administrativně evidovanou adresou. Kódy `permanent` a
`permanent_residence` se kvůli právnímu významu trvalého pobytu nepoužívají.

Strukturální migrace `places.0003_residence_type` vytváří číselník a datová
`places.0004_initial_residence_types` jeho systémový katalog. Strukturální
`places.0005_residence` přidává konkrétní `Residence` pro jeden souvislý
pobyt jedné osoby.

Model v přesném pořadí dědí `TimestampedModel`, `AccessControlledModel`,
`VerifiableModel`, `AuthoredModel`, `LifecycleModel` a `PartialDateModel`.
Jeho vlastní pole jsou:

- povinné `person` → `Person` s `PROTECT` a `related_name="residences"`,
- povinné `residence_type` → `ResidenceType` s `PROTECT` a
  `related_name="residences"`,
- volitelné `place` → `Place` s `PROTECT`, `null=True`, `blank=True` a
  `related_name="residences"`,
- `address_text` jako nepovinný `CharField(max_length=500)`,
- `note` jako nepovinný `TextField`.

Musí být uvedeno místo nebo lokalizační text obsahující po `strip()` alespoň
jeden znak; strukturované místo a textový detail lze kombinovat. Text se při
uložení automaticky nenormalizuje. Model toleruje uživatelský i neaktivní
existující typ. Nemá vlastní unikátní constraint ani dodatečný explicitní
index, takže dovoluje více období i zdánlivě duplicitní tvrzení. Řazení je
`person_id`, `sort_date`, `sort_date_end`, `residence_type__sort_order`,
`pk`.

Samotný krok M2.6b ještě neimplementoval služby ani selectory bydlišť.
Budoucí propojení se zdroji a přílohami zůstává součástí navazujících
milníků.

M2.6c přidává `places.services.ResidenceInput` jako úplný frozen slotted
snapshot polí `person`, `residence_type`, `place`, `address_text`, `note`,
`access_level`, `verification_status`, všech zdrojových polí
`PartialDateModel`, `original_date_text` a `date_note`. Technická, autorská
a lifecycle pole ve vstupu nejsou.

`create_residence(*, data, created_by=None)` a
`update_residence(*, residence, data)` jsou keyword-only transakční služby.
Obě používají čerstvé databázové FK, normalizují okrajové mezery čtyř
textových polí a před uložením volají `full_clean()`. Update je úplná náhrada
editovatelných hodnot, smí změnit osobu i typ a `place=None` odstraní místo,
ale zachovává `created_by`, vytvoření a lifecycle. Aktuální Residence se při
update načítá přes `select_for_update()`.

Nový Residence vyžaduje aktivní typ. Stejný neaktivní typ lze při update
zachovat, přechod na jiný neaktivní typ je zakázán a přechod na aktivní typ
je povolen; porovnává se PK aktuálního databázového typu. Měkce odstraněný
Residence nelze upravit, archivovaný ano. Lifecycle osoby a místa tato
služba nefiltruje. Služba nemá deduplikační pravidlo ani mapování obecného
`IntegrityError`. Samotný krok M2.6c nezměnil model ani migrace a selector
bydlišť v něm ještě nebyl implementovaný.

M2.6d zavádí `get_person_residences(*, person)` v `places/selectors.py`.
Vrací lazy `QuerySet[Residence]` omezený na zadanou osobu a
`deleted_at IS NULL`. Archivace Residence, lifecycle vstupní osoby,
`access_level`, `verification_status`, aktivita či systémovost typu,
lifecycle místa a časová platnost se nefiltrují. Jde o úplnou interní
historii, nikoli výběr současného nebo hlavního bydliště.

Řazení je `sort_date`, `sort_date_end`, `residence_type__sort_order`,
`residence_type__name`, `pk`. Hodnoty `UNKNOWN` zůstávají na přirozeném
databázovém NULL pořadí bez Python řazení. Selector načítá `person`,
`residence_type`, `place` a `created_by` pomocí `select_related()`. Po
jednom `exists()` dotazu pro ověření vstupní osoby zůstává výsledný SELECT
lazy a jeho počet neroste s počtem Residence. Neuložená nebo fyzicky
chybějící osoba používá `person_unsaved`.

Selector je permissionless a může vracet omezený, administrátorský nebo
archivovaný obsah. Není určen k přímému veřejnému použití; autorizovaná
vrstva bude následovat v M2.6e. M2.6d nemění modely ani migrace.

M2.6e přidává nad tímto interním querysetem
`get_visible_person_residences(*, person, actor)`. Selector používá
`can_view_access_level()` pro každou známou úroveň nejvýše jednou, čerstvý
databázový stav actora a čerstvou vstupní osobu. Viditelnost vstupní osoby
kombinuje její `access_level` s `people.view_archived_person` a
`people.view_deleted_person`; aktivní superuser má plný přístup, samotné
`is_staff` nikoli a neaktivní uživatel se posuzuje jako anonymní.

Po úspěšné autorizaci selector volá
`get_person_residences(person=fresh_person)` a přidává pouze databázový
filtr `access_level__in`. Tím zachovává vyloučení měkce odstraněných
Residence, zahrnutí archivovaných Residence bez nové lifecycle permission,
úplnou historii, neaktivní a uživatelské typy, původní řazení i
`select_related()`. Výsledek je stále lazy `QuerySet[Residence]` a počet
dotazů neroste s počtem řádků. Neplatný actor používá `actor_invalid`,
neuložený nebo chybějící autentizovaný actor `actor_unsaved`, neplatná osoba
`person_unsaved` a neviditelná osoba obecnou `PermissionDenied`. M2.6e
nemění modely ani migrace.

## 7. Hrobové místo

Pole:

- ID,
- název,
- hřbitov,
- obec,
- oddíl,
- řada,
- číslo hrobu,
- GPS souřadnice,
- přepis nápisu,
- popis,
- stav místa,
- externí odkaz,
- datum vytvoření,
- datum poslední změny.

Spojení osoba–hrobové místo je samostatná vazba, aby jedno místo mohlo patřit více osobám.

Budoucí hlavní model se jmenuje `GraveSite` a budoucí spojovací model
`PersonGraveSite`. M2.7a ani jeden ještě nevytváří.

`GraveSiteType` přímo dědí z `LookupModel`, nepřidává vlastní pole a
umožňuje uživatelské hodnoty. Systémový katalog v pořadí tvoří:

| Kód | Název | Pořadí |
|---|---|---:|
| `grave` | Hrob | 10 |
| `tomb` | Hrobka | 20 |
| `urn_site` | Urnové místo | 30 |
| `ossuary` | Kostnice | 40 |
| `scattering_place` | Místo rozptylu | 50 |
| `memorial` | Pamětní místo | 60 |
| `cenotaph` | Symbolický hrob | 70 |
| `other` | Jiné místo | 90 |

`PersonGraveSiteRole` je druhý přímý `LookupModel` bez vlastních polí.
Jeho systémové hodnoty jsou:

| Kód | Název | Pořadí |
|---|---|---:|
| `buried` | Pohřbena | 10 |
| `urn_placed` | Uložena urna | 20 |
| `ashes_scattered` | Rozptýlena | 30 |
| `commemorated` | Připomenuta | 40 |
| `remains_relocated_from` | Ostatky přemístěny z místa | 50 |
| `remains_relocated_to` | Ostatky přemístěny na místo | 60 |
| `other` | Jiné propojení | 90 |

`GraveSiteStatus` je pevný `TextChoices` v `places/choices.py` s hodnotami
`existing`, `destroyed` a `unknown`. Popisuje fyzický stav, nikoli
důvěryhodnost nebo lifecycle záznamu. `VerificationStatus` zůstává
samostatnou dimenzí; například doložené zaniklé místo kombinuje
`destroyed` s `verified`, pravděpodobně existující místo `existing` s
`probable` a spolehlivě doložené historické místo neznámého současného
stavu `unknown` s `verified`.

Kenotaf je typ objektu `cenotaph`; osoba k němu typicky používá roli
`commemorated`. Přemístění ostatků není status a dvojice rolí rozlišuje
výchozí a cílové místo bez automatického párování. Strukturální migrace
`places.0006_grave_site_lookups` vytváří oba číselníky a datová
`places.0007_initial_grave_site_lookups` plní systémové hodnoty po společné
kontrole kolizí.

M2.7b vytváří konkrétní model `GraveSite` v tomto pořadí dědičnosti:
`TimestampedModel`, `AccessControlledModel`, `VerifiableModel`,
`AuthoredModel`, `LifecycleModel`, `models.Model`. `PartialDateModel`
záměrně nepoužívá, protože datum pohřbu, přesunu nebo vzniku památníku
patří do budoucí vazby či události.

Vlastní pole modelu jsou:

- povinné `grave_site_type` → `GraveSiteType` s `PROTECT` a
  `related_name="grave_sites"`,
- `status` jako `GraveSiteStatus` s výchozí hodnotou `unknown`,
- volitelné `place` → `Place` s `PROTECT`,
  `related_name="grave_sites"`, `null=True` a `blank=True`,
- `location_text` délky 500,
- `cemetery_name` délky 255,
- `section`, `row` a `grave_number` délky 100,
- `inscription` a `note` jako nepovinné texty,
- volitelné `latitude` a `longitude` jako desetinná čísla se šesti
  desetinnými místy.

Validní záznam vyžaduje alespoň `place`, neprázdný `location_text`,
neprázdný `cemetery_name` nebo úplnou dvojici souřadnic. Neúplná dvojice
souřadnic je neplatná; šířka musí být mezi -90 a 90 a délka mezi -180 a
180. Strukturované a textové lokalizační údaje se mohou kombinovat a
model při uložení text automaticky nestripuje.

Model nemá vlastní `UniqueConstraint`, explicitní index ani deduplikaci.
Řadí se podle `cemetery_name`, `section`, `row`, `grave_number`, `pk`.
Fyzický `status`, důvěryhodnost a lifecycle zůstávají nezávislé.
Strukturální migrace je `places.0008_gravesite`; `PersonGraveSite`,
služby, selectory a oprávnění M2.7b nevytváří.

## 8. Příloha

Pole:

- ID,
- typ souboru,
- MIME typ,
- původní název,
- interní název,
- název pro uživatele,
- popis,
- cesta nebo objektové úložiště,
- velikost,
- kontrolní součet,
- datum vzniku,
- datum nahrání,
- nahrál uživatel,
- autor,
- původ,
- vlastník originálu,
- přístupová úroveň,
- technická metadata,
- stav archivace.

Příloha může být propojena s více objekty.

## 9. Zdroj

Pole:

- ID,
- typ zdroje,
- název,
- citace,
- archiv nebo instituce,
- signatura,
- odkaz,
- poznámka,
- míra důvěryhodnosti,
- přístupová úroveň.

Zdroj se má vázat na konkrétní tvrzení nebo záznam, nikoli pouze na celou osobu.

## 10. Zdravotní záznam

Pole:

- ID,
- osoba,
- datum,
- název,
- typ,
- popis,
- lékař nebo zařízení,
- poznámka,
- přístupová úroveň,
- datum vytvoření,
- datum poslední změny,
- stav archivace.

Výchozí přístupová úroveň zdravotního záznamu je omezená.

## 11. Místo

Pole:

- ID,
- název,
- typ místa,
- nadřazené místo,
- země,
- souřadnice,
- historické názvy,
- popis.

## 12. Uživatel

Pole:

- ID,
- jméno,
- e-mail,
- role,
- stav účtu,
- datum posledního přihlášení,
- datum vytvoření.

Vlastní `accounts.User` používá standardní Django Groups a Permissions.
Globální obsahová oprávnění jsou `accounts.view_restricted_content` a
`accounts.view_admin_only_content`. Model `Person` přidává lifecycle
oprávnění `people.view_archived_person` a `people.view_deleted_person`.
Jde o modelová metadata bez nových polí.

Datová migrace udržuje systémové skupiny Čtenář, Editor a Správce. Čtenář
ani Editor automaticky nezískávají žádné ze čtyř zvýšených oprávnění.
Správce získává právě tato čtyři oprávnění, nikoli automaticky všechna
modelová práva ani příznaky `is_staff` nebo `is_superuser`.

`common.permissions.can_view_access_level()` ověřuje aktuální databázový
stav autentizovaného uživatele. Anonymní a neaktivní actor vidí pouze
`public`; aktivní superuser vidí všechny úrovně. Neznámá úroveň a neplatný
nebo neexistující autentizovaný actor používají stabilní validační chyby.
Lifecycle a autorizovaný přehled vztahů nejsou součástí obecného helperu.

## 13. Změna

Pole:

- ID,
- uživatel,
- typ objektu,
- ID objektu,
- změněné pole,
- původní hodnota,
- nová hodnota,
- datum změny,
- komentář.

## 14. Odvozené hodnoty

Aplikace dopočítává:

- stav žijící/zemřelý,
- věk,
- věk při úmrtí,
- římskou číslici,
- opačný směr vazby,
- chronologické řazení,
- počet fotografií, dokumentů a událostí.

## 15. Zásady

- stejná informace se nemá ukládat dvakrát,
- přílohy a zdroje mají být znovu použitelné,
- důležitá fakta se ukládají strukturovaně,
- neúplná data nesmí být maskována falešnou přesností,
- fyzické mazání se nepoužívá jako výchozí operace.
