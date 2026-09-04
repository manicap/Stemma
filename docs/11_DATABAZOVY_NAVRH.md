# Databázový návrh

**Dokument:** 11  
**Verze:** 0.70
**Stav:** infrastrukturní milník M2 dokončen; implementace `health` zahájena
**Datum revize:** 4. 9. 2026

## 1. Účel

Dokument definuje implementovatelný databázový návrh aplikace **Stemma** pro Django a SQLite. Navazuje zejména na dokumenty `02_FUNKCNI_SPECIFIKACE.md`, `03_DATOVY_MODEL.md`, `04_UZIVATELSKE_ROLE_A_PRAVA.md`, `08_ARCHITEKTONICKE_PRINCIPY.md`, `09_CODING_STANDARD.md` a `10_UI_UX_NAVRH.md`.

Návrh prošel logickou i architektonickou revizí. Milníky M0, M1 a M2 jsou na
větvi `agent/rc-0.1` implementovány a ověřeny. M2 obsahuje konkrétní modely,
migrace, služby a selectory pro osobu, místo, událost, vztah, bydliště a
hrobová místa; RC 0.1 je nad tímto základem rovněž připravené.

### 1.1 Stav implementace

- M0: projekt `config`, aplikace `accounts`, vlastní `accounts.User` a první migrace jsou dokončeny.
- M1: aplikace `common`, pět aktuálně potřebných pevných výčtů, sedm abstraktních modelů a validace neúplných dat jsou dokončeny.
- `common` nevytváří vlastní tabulku; při dokončení M1 nevznikla nová migrace.
- M2 je dokončené: obsahuje jádro Osoba, Místo, Událost a Vazba včetně
  `EventParticipant`, `DeathDetail`, navazujících bydlišť, hrobových míst,
  doménových služeb a autorizovaných selectorů. Audit ověřil také migrace,
  constrainty, modelovou validaci, rollbacky, pořadí zámků a regresní testy.
- Existující aplikační zápisy M2 entit vedou přes servisní hranice a čtení
  používané aplikační vrstvou přes centrální actor-aware access/lifecycle
  policy. Obecný `Place` nemá produktovou cestu a zůstává v adminu fail-closed,
  dokud nevznikne jeho úplná servisní a autorizační hranice.
- RC 0.1 používá autorizovaný výchozí seznam a detail osoby nad skutečnými
  daty včetně actor-specific odvozených životních údajů a římského pořadí;
  automatická i browser brána jsou dokončené.
- Aplikace `materials` je založena a registrována jako samostatný doménový
  balíček. `AttachmentCategory` a `AttachmentRole` přímo dědí z
  `LookupModel`; migrace `materials.0001_attachment_lookups` nevkládá
  systémová data. `Attachment` a šest explicitních vazeb ke stávajícím
  doménám vznikají v migracích `materials.0002` a `materials.0003`. `Source`,
  jeho lookupy a explicitní source vazby jsou implementované v migracích
  `materials.0004` až `materials.0006`; zdravotní přílohy a zdroje doplňují
  migrace `materials.0007` a `materials.0008`.
- Základní zápis osoby pro RC používá frozen slotted `PersonInput` a
  transakční `create_person()`, které znovu načítají FK a autora, normalizují
  okraje textů a před uložením volají `full_clean()`. Stejnou hranici používá
  při zachování markerů opakovatelný lokální příkaz `seed_demo_data`; model
  nyní podle schváleného návrhu ukládá také titul před jménem, titul za jménem
  a životopisný text. Strukturální migrace
  `people.0010_person_titles_biography` nastaví existujícím řádkům prázdné
  řetězce bez zpětného doplňování historických dat.
- `update_person(*, person, data, actor)` uvnitř jedné transakce znovu načte
  aktuálního actora, ověří `people.change_person` a zamkne aktuální osobu přes
  `select_for_update()`. Odmítne neuloženou, fyzicky chybějící, neviditelnou,
  archivovanou nebo měkce odstraněnou osobu. Z čerstvého řádku zachová
  `access_level`, `verification_status`, technická, autorská i lifecycle
  metadata a před uložením volá `full_clean()`. Tituly a životopis jsou součástí
  úplného servisního snapshotu. Užší současný RC formulář používá scoped
  `BasicPersonInput` a `update_person_basic()`, které po stejném autorizačním
  ověření a zámku mění jen jméno, příjmení, pohlaví, kategorii a poznámku.
  Tituly a životopis proto zachovává přímo z čerstvého databázového řádku a
  zatím je uživatelsky nezpřístupňuje.
- Business modely `Place`, `Residence`, `GraveSite` a `PersonGraveSite`
  nejsou registrovány v Django adminu. Jejich dřívější výchozí admin obcházel
  existující hranice u bydlišť a hrobových míst a zároveň zveřejňoval
  neautorizované interní querysety. Obecný `Place` úplnou schválenou servisní
  a actor-aware hranici zatím nemá, proto je rovněž fail-closed. Bezpečné
  produktové rozhraní musí tyto hranice použít nebo nejprve doplnit.
  Uživatelsky spravovatelné číselníky zůstávají v adminu dostupné.
- Společná admin hranice číselníků chrání u systémových řádků technický `code`
  a odstranění; systémový `AllowedEventRole` má stejně chráněnou identitu
  dvojice typu a role. U systémového `RelationshipType` jsou neměnné také
  kategorie, symetrie, podpora rozmezí a odvoditelnost. Prezentační pole,
  aktivita, snapshotové defaulty a validační konfigurace typů událostí
  (`supports_date_range`, `allows_place`), konfigurační počty rolí a všechny
  uživatelské řádky zůstávají spravovatelné. Guard kontroluje i podstrčený POST
  a hromadné mazání, takže technickou identitu řídící doménové invarianty nelze
  změnit výchozím adminem.

## 2. Závazné principy

- Narození a úmrtí jsou události.
- Stav žijící nebo zemřelý, věk, věk při úmrtí a římská číslice se odvozují.
- Opačný směr vazby mezi osobami se neukládá.
- Sňatek je jedna sdílená událost s více účastníky.
- Stejný fakt, soubor ani zdroj se nemá ukládat duplicitně.
- Neúplné datum se nesmí nahrazovat falešným přesným datem.
- Zdravotní skutečnosti se ukládají jako zdravotní záznamy, nikoli současně jako obecné události.
- Důležité záznamy se archivují nebo odstraňují měkce.
- Zdravotní údaje mají výchozí přístupovou úroveň `omezené`.
- Databázový návrh musí fungovat v SQLite a nesmí bezdůvodně blokovat PostgreSQL.

## 3. Rozdělení Django aplikací

```text
stemma/
├── accounts/      uživatelé, skupiny a oprávnění
├── common/        výčty, abstraktní modely, normalizace a validace
├── people/        osoby, jména, kategorie a vazby
├── places/        místa, bydliště a hrobová místa
├── events/        události a účastníci
├── materials/     přílohy, zdroje a jejich propojení
├── health/        zdravotní záznamy
└── audit/         auditní historie
```

Obchodní aplikace zůstávají součástí jednoho Django projektu. Hlavní objekty nemají přímé cizí klíče zpět do `materials`; přílohy a zdroje se připojují explicitními spojovacími modely.

## 4. Společné technické vzory

### 4.1 Pevné výčty

Pevnými Django `TextChoices` budou zejména:

- pohlaví: muž, žena, neznámé,
- přístupová úroveň: veřejné, pouze přihlášení, omezené, pouze správce,
- stav ověření: ověřeno, pravděpodobné, nejisté, sporné, nepotvrzené,
- přesnost a kvalifikátor data,
- auditní operace,
- stav fyzického souboru.

Tyto hodnoty nebudou uživatelsky spravovanými číselníky, protože jsou součástí validační nebo bezpečnostní logiky. V M1 byly implementovány výčty pro pohlaví, přístupovou úroveň, stav ověření, přesnost data a kvalifikátor data. Auditní operace a stav fyzického souboru budou doplněny s příslušnými doménami.

### 4.2 Abstraktní modely

Společná pole se budou sdílet pomocí abstraktních Django modelů:

- `TimestampedModel` — vytvořeno a změněno,
- `AuthoredModel` — autor záznamu,
- `AccessControlledModel` — přístupová úroveň,
- `VerifiableModel` — stav ověření,
- `LifecycleModel` — archivace a měkké odstranění,
- `PartialDateModel` — neúplný a nejistý časový údaj,
- `LookupModel` — společný základ číselníků.

Abstraktní model nevytváří vlastní tabulku. Jeho pole se vloží do konkrétních modelů. Všechny uvedené abstraktní modely byly implementovány a otestovány v M1.

### 4.3 Archivace a měkké odstranění

Archivace a měkké odstranění mají rozdílný význam.

- Archivovaný záznam zůstává platným historickým záznamem, ale běžně se nezobrazuje.
- Měkce odstraněný záznam je považován za odstraněný a nepoužívá se pro odvozené hodnoty.

Hlavní entity budou používat pole:

- `archived_at`, `archived_by`,
- `deleted_at`, `deleted_by`,
- důvod zásahu.

Číselníky budou používat `is_active` a `is_system` místo archivace.

## 5. Jednotný model neúplného data

Stejná struktura data se použije u událostí, vazeb, bydlišť, zdravotních záznamů, dalších jmen, názvů míst, příloh, zdrojů a propojení osob s hroby.

Podporované významy:

- přesné datum,
- měsíc a rok,
- pouze rok,
- rozmezí,
- přibližně,
- před,
- po,
- zcela neznámé datum.

Logická pole:

- přesnost data,
- kvalifikátor,
- rok, měsíc a den začátku,
- rok, měsíc a den konce,
- původní text data,
- poznámka k datu,
- technické `sort_date` a `sort_date_end`.

Technická řadicí data se automaticky odvozují a nesmějí se zobrazovat jako historický fakt. Uživatel je neupravuje.

Validace hlídá správný rozsah roku a měsíce, existenci dne v konkrétním měsíci, návaznost částí data, povolené kvalifikátory, zákaz konce mimo rozmezí a zákaz konce před začátkem. Implementace v `common/partial_dates.py` používá čisté pomocné funkce a stabilní chybové kódy. Modelová metoda `clean()` validuje a nastavuje technické meze; `save()` nevolá `full_clean()` a pouze zajišťuje jejich přepočet před uložením.

## 6. Osoba a jména

### 6.1 Osoba

Osoba obsahuje pouze stabilní identitu:

- hlavní jméno,
- hlavní příjmení,
- pohlaví,
- kategorii osoby,
- tituly,
- stručnou poznámku,
- životopisný text,
- přístupovou úroveň,
- technická a auditní pole.

Musí být vyplněno alespoň jméno nebo příjmení. Jméno ani jeho kombinace nejsou unikátní.

Osoba neobsahuje přímá pole narození, úmrtí, věku, stavu žijící/zemřelý ani římské číslice.

Technická pole `title_before_name` a `title_after_name` jsou nepovinné
`CharField(max_length=100, blank=True)`. Stručná poznámka `notes` a samostatný
životopisný text `biography` jsou nepovinné `TextField(blank=True)`; životopis
nenahrazuje krátkou kontextovou poznámku.

### 6.2 Kategorie osoby

Spravovatelný číselník s výchozími hodnotami:

- Přímá rodina,
- Ostatní rodina,
- Blízcí rodině,
- Duchovní,
- Další související osoby.

Kategorie je nepovinná a nenahrazuje konkrétní vztahy.

### 6.3 Další jméno osoby

Samostatný model uchovává například:

- rodné příjmení,
- další křestní jméno,
- dřívější příjmení,
- alternativní zápis,
- přezdívku,
- jméno uvedené ve zdroji.

Každý záznam má typ, hodnotu, normalizovanou vyhledávací hodnotu, stav ověření, případnou časovou platnost a zdroje.

## 7. Místo

Místo je opakovaně použitelný geografický nebo fyzický objekt.

Model `Place` dědí společné abstraktní modely `TimestampedModel`,
`AccessControlledModel`, `VerifiableModel`, `AuthoredModel` a `LifecycleModel`.
Nedědí `PartialDateModel`.

Vlastní pole modelu jsou:

- `place_type` — volitelný `ForeignKey` na `PlaceType`, `null=True`,
  `blank=True`, `on_delete=models.PROTECT`, `related_name="places"`,
- `name` — povinný `CharField(max_length=255)`,
- `normalized_name` — povinný `CharField(max_length=255, db_index=True)`;
  zatím se zadává explicitně a automatický normalizační algoritmus není
  součástí tohoto kroku,
- `parent` — volitelný `ForeignKey` na `self`, `null=True`, `blank=True`,
  `on_delete=models.SET_NULL`, `related_name="children"`,
- `country` — `CharField(max_length=100, blank=True)` pro zobrazovanou textovou
  hodnotu země nebo historického státního útvaru; samostatný model ani
  číselník zemí se zatím nevytváří,
- `description` — `TextField(blank=True)`,
- `latitude` — `DecimalField(max_digits=8, decimal_places=6, null=True,
  blank=True)`,
- `longitude` — `DecimalField(max_digits=9, decimal_places=6, null=True,
  blank=True)`,
- `coordinate_precision_m` — volitelný `PositiveIntegerField(null=True,
  blank=True)` vyjadřující odhadovanou přesnost souřadnic v metrech.

Model uplatňuje tato validační pravidla:

- zeměpisná šířka a délka musí být zadány buď obě, nebo ani jedna,
- zeměpisná šířka musí být v rozsahu −90 až 90,
- zeměpisná délka musí být v rozsahu −180 až 180,
- přesnost souřadnic lze vyplnit pouze při zadaných obou souřadnicích,
- místo nesmí být samo sobě rodičem,
- hierarchie `parent` nesmí obsahovat přímý ani nepřímý cyklus.

Metadata modelu jsou `verbose_name = "Místo"`,
`verbose_name_plural = "Místa"` a `ordering = ("name",)`. Textová
reprezentace vrací `name`.

Hierarchie míst nesmí obsahovat cyklus. Detailní adresní údaje se primárně ukládají u bydliště nebo události. Samostatné místo pro dům nebo budovu vznikne pouze tehdy, pokud se opakovaně používá nebo má vlastní historii a materiály.

Historické, jazykové a alternativní názvy mohou být vedeny v samostatném modelu `PlaceName`.

## 8. Události

### 8.1 Typ události

Číselník `EventType` je přímým potomkem `LookupModel`. Vedle zděděných
polí obsahuje tato povinná pole s `null=False` a `blank=False`:

- `supports_date_range` — `BooleanField(default=False)`; určuje, zda typ
  podporuje `DatePrecision.RANGE`,
- `allows_place` — `BooleanField(default=True)`; určuje, zda událost může
  mít přiřazené místo,
- `default_show_in_overview` — `BooleanField(default=False)`; určuje výchozí
  hodnotu příznaku zobrazení nové události v přehledu osoby,
- `default_access_level` — `CharField(max_length=20,
  choices=AccessLevel.choices, default=AccessLevel.PUBLIC)`; určuje výchozí
  přístupovou úroveň nové události.

Změna výchozích hodnot typu nemění již existující události. Metadata
modelu jsou `verbose_name = "Typ události"`,
`verbose_name_plural = "Typy událostí"` a zděděné
`ordering = ("sort_order", "name", "code")`. Textová reprezentace vrací
`name`.

Systémové hodnoty mají `is_active=True`, `is_system=True` a následující
konfiguraci:

| Kód | Název | Popis | Pořadí | Rozmezí | Místo | Přehled | Výchozí přístup |
|---|---|---|---:|:---:|:---:|:---:|---|
| `birth` | Narození | Narození osoby. | 10 | ne | ano | ano | `AccessLevel.PUBLIC` |
| `baptism` | Křest | Křest osoby. | 20 | ne | ano | ne | `AccessLevel.PUBLIC` |
| `marriage` | Sňatek | Uzavření manželství. | 30 | ne | ano | ano | `AccessLevel.PUBLIC` |
| `divorce` | Rozvod | Ukončení manželství rozvodem. | 40 | ne | ano | ne | `AccessLevel.PUBLIC` |
| `relocation` | Stěhování | Přestěhování osoby nebo domácnosti. | 50 | ne | ano | ne | `AccessLevel.PUBLIC` |
| `education` | Studium | Studium na škole nebo v jiném vzdělávacím programu. | 60 | ano | ano | ne | `AccessLevel.PUBLIC` |
| `graduation` | Maturita | Složení maturity nebo obdobné závěrečné zkoušky. | 70 | ne | ano | ne | `AccessLevel.PUBLIC` |
| `military_service` | Vojenská služba | Výkon vojenské služby. | 80 | ano | ano | ne | `AccessLevel.PUBLIC` |
| `employment` | Zaměstnání | Pracovní nebo profesní působení. | 90 | ano | ano | ne | `AccessLevel.PUBLIC` |
| `death` | Úmrtí | Úmrtí osoby. | 100 | ne | ano | ano | `AccessLevel.PUBLIC` |
| `funeral` | Pohřeb | Pohřeb nebo jiné rozloučení se zemřelým. | 110 | ne | ano | ne | `AccessLevel.PUBLIC` |
| `other` | Jiná událost | Jiná životní událost. | 120 | ano | ano | ne | `AccessLevel.PUBLIC` |

Úraz, operace, očkování a další zdravotní skutečnosti se ukládají jako zdravotní záznamy.

### 8.2 Role účastníka a povolené role

Účast osoby na události je samostatný spojovací model.

`ParticipantRole` je spravovatelný číselník, který dědí pouze
`LookupModel` a nepřidává vlastní databázová pole. Metadata jsou
`verbose_name = "Role účastníka"`,
`verbose_name_plural = "Role účastníků"` a zděděné
`ordering = ("sort_order", "name", "code")`. Textová reprezentace vrací
`name`.

Systémové role mají `is_active=True`, `is_system=True`:

| Kód | Název | Popis | Pořadí |
|---|---|---|---:|
| `subject` | Hlavní osoba | Osoba, které se událost primárně týká. | 10 |
| `born_person` | Narozená osoba | Osoba, jejíž narození událost eviduje. | 20 |
| `baptized_person` | Křtěná osoba | Osoba, jejíž křest událost eviduje. | 30 |
| `deceased_person` | Zemřelá osoba | Osoba, jejíž úmrtí nebo pohřeb událost eviduje. | 40 |
| `spouse` | Manželský partner | Partner při sňatku nebo rozvodu. | 50 |
| `parent` | Rodič | Rodič hlavní osoby nebo jiného účastníka. | 60 |
| `child` | Dítě | Dítě hlavní osoby nebo jiného účastníka. | 70 |
| `godparent` | Kmotr nebo kmotra | Kmotr nebo kmotra při křtu. | 80 |
| `witness` | Svědek | Svědek události. | 90 |
| `participant` | Účastník | Další osoba přímo účastná události. | 100 |
| `other` | Jiná role | Jiná role osoby v události. | 110 |

Používá se jediná genderově neutrální role `spouse`. Označení
ženich, nevěsta, manžel nebo manželka je pouze budoucí zobrazovací logika
odvozená z osoby a kontextu.

`AllowedEventRole` je konfigurační spojovací model bez common mixinů.
Obsahuje:

- `event_type` — `ForeignKey` na `EventType`, `on_delete=models.PROTECT`,
  `related_name="allowed_roles"`,
- `participant_role` — `ForeignKey` na `ParticipantRole`,
  `on_delete=models.PROTECT`, `related_name="event_type_rules"`,
- `min_count` — `PositiveSmallIntegerField(default=0)`,
- `max_count` — `PositiveSmallIntegerField(null=True, blank=True)`,
- `sort_order` — `PositiveIntegerField(default=0)`,
- `is_active` — `BooleanField(default=True)`,
- `is_system` — `BooleanField(default=False, editable=False)`.

Hodnota `min_count=0` znamená nepovinnou roli a vyšší hodnota minimální
povinný počet. `max_count=None` znamená počet bez horního omezení.
Maximum nesmí být nižší než minimum. `sort_order` určuje pořadí
v rozhraní, `is_active=False` pravidlo deaktivuje a `is_system` rozlišuje
systémovou konfiguraci.

Metadata modelu jsou `verbose_name = "Povolená role události"`,
`verbose_name_plural = "Povolené role událostí"` a:

```python
ordering = (
    "event_type__sort_order",
    "sort_order",
    "participant_role__sort_order",
    "participant_role__code",
)
```

Dvojice `event_type` a `participant_role` je jedinečná pomocí constraintu
`events_unique_allowed_role`. Constraint
`events_valid_allowed_role_counts` vyžaduje, aby `max_count` bylo `NULL`
nebo větší či rovné `min_count`. Textová reprezentace vrací
`"{event_type} – {participant_role}"`.

Systémová matice používá `is_active=True`, `is_system=True`. Zápis
`minimum..maximum / pořadí` používá `∞` pro neomezené maximum:

| Typ události | Povolené role |
|---|---|
| `birth` | `born_person` 1..1 / 10; `parent` 0..2 / 20; `witness` 0..∞ / 30; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `baptism` | `baptized_person` 1..1 / 10; `parent` 0..2 / 20; `godparent` 0..∞ / 30; `witness` 0..∞ / 40; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `marriage` | `spouse` 2..2 / 10; `parent` 0..∞ / 20; `witness` 0..∞ / 30; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `divorce` | `spouse` 1..2 / 10; `witness` 0..∞ / 30; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `relocation` | `subject` 1..∞ / 10; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `education` | `subject` 1..1 / 10; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `graduation` | `subject` 1..1 / 10; `witness` 0..∞ / 30; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `military_service` | `subject` 1..1 / 10; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `employment` | `subject` 1..1 / 10; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `death` | `deceased_person` 1..1 / 10; `witness` 0..∞ / 30; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `funeral` | `deceased_person` 1..1 / 10; `witness` 0..∞ / 30; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `other` | `subject` 1..∞ / 10; `parent` 0..∞ / 20; `child` 0..∞ / 30; `spouse` 0..∞ / 40; `godparent` 0..∞ / 50; `witness` 0..∞ / 60; `participant` 0..∞ / 80; `other` 0..∞ / 90 |

Systémová pravidla jsou současně chráněna aplikační validací:

- narození má právě jednu narozenou osobu,
- úmrtí má právě jednu zemřelou osobu,
- sňatek má dva hlavní partnery.

### 8.3 Událost

`Event` je hlavní historická entita a dědí abstraktní modely
`TimestampedModel`, `AccessControlledModel`, `VerifiableModel`,
`AuthoredModel`, `LifecycleModel` a `PartialDateModel`.

Vlastní pole modelu jsou:

- `event_type` — povinný `ForeignKey` na `EventType`, `null=False`,
  `blank=False`, `on_delete=models.PROTECT`, `related_name="events"`,
- `place` — volitelný `ForeignKey` na `places.Place`, `null=True`,
  `blank=True`, `on_delete=models.PROTECT`, `related_name="events"`,
- `location_detail` — `CharField(max_length=255, blank=True)` pro dobový
  adresní nebo lokalizační detail, který nenahrazuje strukturované místo,
- `title` — `CharField(max_length=255, blank=True)` pro volitelný vlastní
  zobrazovaný název bez automatického odvozování z typu,
- `description` — `TextField(blank=True)`,
- `show_in_overview` — `BooleanField(default=False)` jako uložené rozhodnutí
  konkrétní události.

Časový údaj používá úplnou strukturu `PartialDateModel`.
`DatePrecision.UNKNOWN` je platný stav. Pokud typ nepodporuje rozmezí,
`DatePrecision.RANGE` je odmítnuto na poli `date_precision` s kódem
`date_range_not_supported`. Typ s `allows_place=False` odmítne
strukturované místo s kódem `place_not_allowed` a neprázdný oříznutý
`location_detail` s kódem `location_detail_not_allowed`. Kalendářní
validace a odvození technických mezí zůstávají v `PartialDateModel`.

Hodnoty `EventType.default_access_level` a
`EventType.default_show_in_overview` jsou návrhy pro novou událost.
Doménová služba je při založení zkopíruje pouze tehdy, pokud volající
neuvede vlastní hodnotu. Změna typu ani jeho defaultů existující události
zpětně nemění; při aktualizaci se uložený snapshot zachová, není-li výslovně
nahrazen.

Metadata modelu jsou `verbose_name = "Událost"`,
`verbose_name_plural = "Události"` a
`ordering = ("sort_date", "sort_date_end", "pk")`. Textová reprezentace
vrací neprázdný oříznutý `title`, jinak dostupný název typu a bez
dostupného typu text `"Událost"`.

Účastníci nejsou přímými poli `Event`; `EventParticipant` je samostatný
spojovací model. Přílohy a zdroje budou používat samostatné
explicitní spojovací modely.

Příčina a okolnosti úmrtí se ukládají v samostatném modelu `DeathDetail`,
který dědí pouze z `models.Model`. Obsahuje `event` jako povinný
`OneToOneField` na `Event` s `on_delete=CASCADE` a
`related_name="death_detail"` a volitelné texty `cause` a `circumstances`.
Alespoň jeden text musí být po oříznutí neprázdný a rodičem smí být pouze
systémový typ `death`.

Detail nemá vlastní access, lifecycle, verification ani author metadata;
všechny tyto významy a případná aplikační autorizace se odvozují výhradně z
rodičovské události. Veřejnou zápisovou hranici tvoří keyword-only
`create_death_detail()`, `update_death_detail()` a `delete_death_detail()`
nad frozen slotted `DeathDetailInput`. Služby používají `transaction.atomic()`,
zamykají nejprve rodičovský `Event` a pak detail, dovolují archivovanou, ale
nikoli měkce odstraněnou událost a mapují souběžnou 1:1 kolizi na stabilní
`death_detail_exists`, pokud databáze potvrdí duplicitní řádek. Zámek rodiče
serializuje zápisy na databázích s účinnými řádkovými zámky; SQLite má
`select_for_update()` jako no-op, takže testy dokazují pořadí zámků a mapování
kolize, nikoli skutečnou souběžnou serializaci. `update_event()` odmítne změnu
události s detailem na jiný než systémový typ `death`; při změně typu se detail
nikdy automaticky neodstraňuje. Samostatné odstranění je pouze explicitní
službou a zachovává rodičovský `Event`. Při fyzickém odstranění rodiče detail
zaniká přes `CASCADE` jako součást zděděného lifecycle.
`DeathDetail` není v této etapě registrován v adminu ani vystaven v UI či API.

Jedna osoba smí mít nejvýše jednu aktivní účast jako narozená osoba a jednu jako zemřelá osoba.

### 8.4 Účastník události

`EventParticipant` představuje účast konkrétní existující osoby v jedné
události v jedné konkrétní roli. Jde o spojovací model dědící pouze z
`models.Model`; přístup, ověření a lifecycle se odvozují z nadřazeného
`Event`.

Model obsahuje:

- `event` — povinný `ForeignKey` na `Event`, `null=False`, `blank=False`,
  `on_delete=models.CASCADE`, `related_name="participants"`,
- `person` — povinný `ForeignKey` na `people.Person`, `null=False`,
  `blank=False`, `on_delete=models.PROTECT`,
  `related_name="event_participations"`,
- `role` — povinný `ForeignKey` na `ParticipantRole`, `null=False`,
  `blank=False`, `on_delete=models.PROTECT`,
  `related_name="event_participations"`,
- `note` — `TextField(blank=True)` pro volitelnou poznámku ke konkrétní
  účasti; poznámka nemění identitu účasti.

Osoba musí být založeným záznamem `Person`. Prázdná osoba ani samostatný
textový účastník nejsou součástí současného návrhu. Stejná osoba může mít
v jedné události více různých rolí, stejnou roli může mít více osob a
jedna osoba může být účastníkem více událostí.

Trojice `event`, `person` a `role` je jedinečná pomocí constraintu
`events_unique_participation`. Odlišná poznámka nepovoluje duplicitní
trojici.

Metadata modelu jsou `verbose_name = "Účastník události"`,
`verbose_name_plural = "Účastníci událostí"` a:

```python
ordering = (
    "role__sort_order",
    "person__last_name",
    "person__first_name",
    "person_id",
)
```

Textová reprezentace vrací `"{person} – {role} – {event}"`. Pro
nedostupnou vazbu používá bezpečné texty `"Neznámá osoba"`,
`"Neznámá role"` a `"Událost"`.

Model dynamicky nekontroluje aktuální `AllowedEventRole`. Transakční
doménová služba při vytvoření nebo změně účasti ověří aktivní
konfiguraci, aktivitu role a počty účastníků. Změna konfigurace sama
nezneplatňuje již uložené historické účasti.

### 8.5 Doménové služby události a účastníků

`EventInput`, `create_event()` a `update_event()` tvoří zápisovou hranici
celého agregátu. Vstup je frozen slotted command DTO editovatelných polí;
`None` u výchozího přístupu a zobrazení znamená při create převzetí defaultu
typu a při update zachování uloženého snapshotu.
Create načte čerstvý aktivní typ, volitelné místo a autora, zkopíruje
neuvedené výchozí hodnoty typu, zavolá `full_clean()` a v jedné transakci
uloží událost i úplnou sadu účastníků. Update zamkne a znovu načte aktuální
událost, autora ani lifecycle metadata nemění, dovoluje zachovat její
stávající neaktivní typ a atomicky nahradí pole i účastníky. Archivovaný
záznam lze opravit, měkce odstraněný nikoli. Chyba kterékoliv části vrátí
celý agregát do původního stavu.

Změnu účastníků jedné události zajišťuje služba v `events/services.py`:

```python
@dataclass(frozen=True, slots=True)
class EventParticipantInput:
    person: Person
    role: ParticipantRole
    note: str = ""


def replace_event_participants(
    *,
    event: Event,
    participants: Iterable[EventParticipantInput],
    require_complete: bool = False,
) -> list[EventParticipant]:
    ...
```

Služba materializuje vstupní iterable právě jednou a v
`transaction.atomic()` atomicky nahradí celou sadu účastníků. Událost,
aktuální účasti, použité osoby, role a relevantní konfiguraci načítá z
databáze a podle možností databáze zamyká pomocí `select_for_update()`.
Celý požadovaný výsledný stav ověří před prvním zápisem. Zachované
trojici událost, osoba a role ponechá primární klíč, případně aktualizuje
její poznámku; odstraní jen vynechané a vytvoří jen nové účasti. Výsledkem
je seznam uložených účastí v modelovém pořadí.

Při každé náhradě se ověřuje, že osoby a role jsou uložené, role jsou
aktivní, pro typ události existuje aktivní `AllowedEventRole`, vstup
neobsahuje duplicitní dvojici osoby a role a počet nepřekračuje
`max_count`. Při `require_complete=False` se `min_count` nekontroluje a
událost může zůstat rozpracovaná. Při `require_complete=True` musí být
splněna minima všech aktivních pravidel; neaktivní pravidla se do minima
nezapočítávají. Aktivní povinné pravidlo odkazující na neaktivní roli je
neplatnou konfigurací.

Samotná změna konfigurace historické účasti automaticky nemění. Při
pozdějším volání služby však každý záznam zahrnutý do nové výsledné sady
musí projít aktuální konfigurací. Dnes nepovolenou historickou účast lze
odstranit jejím vynecháním, ale nelze ji ponechat ani pouze změnit její
poznámku. Grandfathering se nepoužívá.

Validační chyby používají `django.core.exceptions.ValidationError`, klíče
`event` a `participants` a stabilní kódy `event_unsaved`,
`participant_person_unsaved`, `participant_role_unsaved`,
`participant_role_inactive`, `role_not_allowed_for_event_type`,
`duplicate_event_person_role`, `participant_count_above_maximum` a
`participant_count_below_minimum`. Pro přesnou dvojici `birth` /
`born_person` a `death` / `deceased_person` služba navíc pod zámkem osoby
odmítá jinou účast stejné osoby v neodstraněné události kódem
`duplicate_person_life_event`. Archivovaná událost se nadále počítá jako
platná historická skutečnost, měkce odstraněná nikoli; jiný typ, například
`funeral`, se nezapočítává. Dostupný kontext je předáván v `params`.
Implementace nemění modely a nevytváří migraci.

`Event` a `EventParticipant` nejsou do vzniku servisně napojeného rozhraní
registrovány v Django adminu. Přímý admin zápis by obcházel atomickou hranici,
aktuální konfiguraci rolí, lifecycle zákaz i životní jedinečnost.

## 9. Vazby mezi osobami

### 9.1 Kategorie a typ vazby

`RelationshipCategory` je pevný `TextChoices` výčet:

| Technická hodnota | Český název |
|---|---|
| `parent_child` | Rodič a dítě |
| `partner` | Partnerství |
| `sibling` | Sourozenectví |
| `godparent` | Kmotrovství |
| `care` | Péče a poručenství |
| `social` | Sociální vazba |
| `other` | Jiná vazba |

`RelationshipType` je konkrétní uživatelsky rozšiřitelný číselník, který
dědí pouze z `LookupModel`. Vedle zděděných polí obsahuje:

| Pole | Typ a pravidla |
|---|---|
| `forward_label_male` | `CharField(max_length=100)`, povinné |
| `forward_label_female` | `CharField(max_length=100)`, povinné |
| `forward_label_unknown` | `CharField(max_length=100)`, povinné |
| `reverse_label_male` | `CharField(max_length=100)`, povinné |
| `reverse_label_female` | `CharField(max_length=100)`, povinné |
| `reverse_label_unknown` | `CharField(max_length=100)`, povinné |
| `category` | `CharField(max_length=20)`, `RelationshipCategory.choices`, výchozí `other` |
| `is_symmetric` | `BooleanField`, výchozí `False` |
| `supports_date_range` | `BooleanField`, výchozí `False` |
| `is_derivable` | `BooleanField`, výchozí `False` |

Objekt se řadí podle zděděného `("sort_order", "name", "code")`, má
jednotné číslo „Typ vazby“ a množné číslo „Typy vazeb“.

### 9.2 Směr, genderované názvy a symetrie

Vazba se ukládá jednou mezi osobami A a B. Osoba A je výchozí osoba a osoba
B cílová osoba. `forward_label_*` popisuje osobu B z pohledu osoby A
a genderová varianta se vybírá podle genderu osoby B. `reverse_label_*`
popisuje osobu A z pohledu osoby B a varianta se vybírá podle genderu osoby
A. Varianta `unknown` se používá při `Gender.UNKNOWN` nebo chybějícím údaji.

U symetrické vazby pořadí osob význam nemění a budoucí konkrétní
`Relationship` uloží dvojici v normalizovaném pořadí. U směrové vazby je
pořadí významové. Symetrický typ musí mít shodné dopředné a zpětné názvy
pro mužskou, ženskou i neznámou variantu. `RelationshipType.clean()` hlásí
chybu na příslušném zpětném poli s kódem `symmetric_labels_mismatch`.
Stejné pravidlo vynucuje databázový constraint
`people_symmetric_relationship_labels_match`.

`supports_date_range=False` znamená, že budoucí konkrétní `Relationship`
nesmí používat `DatePrecision.RANGE`; hodnota `True` rozmezí povoluje.
Příznak nevyžaduje vyplnění data a neomezuje ostatní podporované přesnosti.
`RelationshipType` samo datum neobsahuje.

`is_derivable=True` označuje vztah, který lze odvodit z jiných
strukturovaných údajů a běžně se nemá ukládat duplicitně, jsou-li zdrojová
data dostupná. Příznak v M2.5a nic automaticky neodvozuje, nezakazuje
explicitní záznam a neimplementuje algoritmus odvození.

### 9.3 Systémové typy

Všechny systémové typy mají `is_active=True` a `is_system=True`.

| Kód | Název a popis | Kategorie | Pořadí | Symetrický | Rozmezí | Odvoditelný |
|---|---|---|---:|---:|---:|---:|
| `biological_parent` | Biologický rodič — Vztah biologického rodiče a dítěte. | `parent_child` | 10 | ne | ne | ne |
| `adoptive_parent` | Adoptivní rodič — Vztah adoptivního rodiče a adoptovaného dítěte. | `parent_child` | 20 | ne | ne | ne |
| `step_parent` | Nevlastní rodič — Vztah nevlastního rodiče a nevlastního dítěte. | `parent_child` | 30 | ne | ano | ne |
| `foster_parent` | Pěstoun — Vztah pěstouna a dítěte v pěstounské péči. | `parent_child` | 40 | ne | ano | ne |
| `guardian` | Poručník — Vztah poručníka a osoby v poručenství. | `care` | 50 | ne | ano | ne |
| `spouse` | Manželství — Manželský vztah mezi dvěma osobami. | `partner` | 60 | ano | ano | ne |
| `partner` | Partnerství — Partnerský vztah mezi dvěma osobami. | `partner` | 70 | ano | ano | ne |
| `sibling` | Biologické sourozenectví — Biologické sourozenectví. | `sibling` | 80 | ano | ne | ano |
| `adoptive_sibling` | Adoptivní sourozenectví — Sourozenectví vzniklé adopcí. | `sibling` | 90 | ano | ne | ne |
| `step_sibling` | Nevlastní sourozenectví — Nevlastní sourozenectví. | `sibling` | 100 | ano | ano | ne |
| `social_sibling` | Sourozenecká sociální vazba — Sourozenecká sociální vazba bez biologického nebo právního základu. | `sibling` | 110 | ano | ano | ne |
| `godparent` | Kmotrovství — Vztah kmotra nebo kmotry a kmotřence. | `godparent` | 120 | ne | ne | ne |
| `family_friend` | Rodinné přátelství — Blízká přátelská vazba osoby k rodině. | `social` | 130 | ano | ano | ne |
| `other` | Jiná vazba — Jiná rodinná nebo sociální vazba. | `other` | 140 | ano | ano | ne |

Genderované názvy obou směrů jsou:

| Kód | A → B: muž / žena / neznámé | B → A: muž / žena / neznámé |
|---|---|---|
| `biological_parent` | syn / dcera / dítě | otec / matka / rodič |
| `adoptive_parent` | adoptovaný syn / adoptovaná dcera / adoptované dítě | adoptivní otec / adoptivní matka / adoptivní rodič |
| `step_parent` | nevlastní syn / nevlastní dcera / nevlastní dítě | nevlastní otec / nevlastní matka / nevlastní rodič |
| `foster_parent` | pěstounský syn / pěstounská dcera / dítě v pěstounské péči | pěstoun / pěstounka / pěstoun nebo pěstounka |
| `guardian` | svěřenec / svěřenkyně / osoba v poručenství | poručník / poručnice / poručník nebo poručnice |
| `spouse` | manžel / manželka / manžel nebo manželka | shodné s A → B |
| `partner` | partner / partnerka / partner nebo partnerka | shodné s A → B |
| `sibling` | bratr / sestra / sourozenec | shodné s A → B |
| `adoptive_sibling` | adoptivní bratr / adoptivní sestra / adoptivní sourozenec | shodné s A → B |
| `step_sibling` | nevlastní bratr / nevlastní sestra / nevlastní sourozenec | shodné s A → B |
| `social_sibling` | blízký jako bratr / blízká jako sestra / blízký jako sourozenec | shodné s A → B |
| `godparent` | kmotřenec / kmotřenka / kmotřenec nebo kmotřenka | kmotr / kmotra / kmotr nebo kmotra |
| `family_friend` | rodinný přítel / rodinná přítelkyně / rodinný přítel nebo přítelkyně | shodné s A → B |
| `other` | související osoba / související osoba / související osoba | shodné s A → B |

`family_friend` je v první verzi symetrická vazba mezi dvěma osobami;
nevyjadřuje vztah osoby k rodině jako samostatnému objektu. Pouze biologické
sourozenectví `sibling` má `is_derivable=True`.

### 9.4 Budoucí konkrétní vazba

`Relationship` je samostatná historická doménová entita a dědí v tomto
pořadí:

```python
TimestampedModel,
AccessControlledModel,
VerifiableModel,
AuthoredModel,
LifecycleModel,
PartialDateModel,
models.Model,
```

Vlastní pole jsou:

| Pole | Typ a pravidla |
|---|---|
| `relationship_type` | povinný `ForeignKey` na `RelationshipType`, `on_delete=PROTECT`, `related_name="relationships"` |
| `person_a` | povinný `ForeignKey` na `Person`, `on_delete=PROTECT`, `related_name="relationships_as_a"` |
| `person_b` | povinný `ForeignKey` na `Person`, `on_delete=PROTECT`, `related_name="relationships_as_b"` |
| `note` | `TextField(blank=True)`, běžná doménová poznámka |

Poznámka se řídí přístupovou úrovní celé vazby. Zděděné `date_note` je
vyhrazené poznámce k časovému údaji. Model nepřidává vlastní `save()`;
technické meze nadále přepočítává zděděný `PartialDateModel`.

### 9.5 Časový význam a opakovaná období

Jeden `Relationship` představuje jedno souvislé období vztahu:

- `UNKNOWN` znamená neznámý čas vztahu,
- `EXACT` přesné datum vzniku vztahu,
- `MONTH` měsíc vzniku vztahu,
- `YEAR` rok vzniku vztahu,
- `RANGE` známé období platnosti se začátkem a koncem.

U `EXACT`, `MONTH` a `YEAR` technické `sort_date_end` neznamená konec
vztahu. Je pouze horní technickou mezí přesnosti pro řazení a porovnání.
`RANGE` je povoleno pouze při
`relationship_type.supports_date_range=True`; `UNKNOWN` je vždy platné.

Stejné osoby mohou mít více záznamů stejného typu s odlišným časovým
vymezením. Překrývající se, ale neidentická období se v M2.5b nezakazují.
Poznámka, přístupová úroveň, stav ověření ani původní text data nemění
identitu období.

### 9.6 Modelová validace

`Relationship.clean()` zachová a agreguje chyby `PartialDateModel` a dále
kontroluje:

- `person_a == person_b` — chyba na `person_b` s kódem
  `relationship_to_self`,
- nepodporované `DatePrecision.RANGE` — chyba na `date_precision` s kódem
  `date_range_not_supported`,
- symetrický typ s `person_a_id > person_b_id` — chyba na `person_b`
  s kódem `symmetric_relationship_not_normalized`.

U symetrického typu je kanonické pořadí `person_a_id < person_b_id`.
Model osoby nepřehazuje. Budoucí veřejný zápis bude před vytvořením
normalizovat doménová služba podle PK. Kontrola pořadí proběhne jen při
bezpečně dostupném typu a uložených různých osobách.

Databáze nemůže podmínit constraint hodnotou `is_symmetric` z jiné tabulky.
Přímý ORM zápis bez `full_clean()` proto může uložit nenormalizovanou
symetrickou dvojici. Toto omezení je přijatelné pouze do zavedení veřejné
doménové služby; `clean()` ani `save()` data automaticky nemění.

`RelationshipType.is_derivable=True` explicitní uložení nezakazuje a nic
automaticky neodvozuje.

### 9.7 Databázové constrainty

Vztah osoby k sobě zakazuje:

```text
people_relationship_distinct_persons
```

Unikátnost používá dva podmíněné constrainty. Pro jejich účely znamená
„active“ `deleted_at IS NULL`. Archivovaný záznam zůstává historicky
existující a započítává se; měkce odstraněný záznam se nezapočítává.

`people_unique_active_unknown_relationship` povoluje pro orientovanou
trojici `person_a`, `person_b` a `relationship_type` nejvýše jeden měkce
neodstraněný záznam s `DatePrecision.UNKNOWN`.

`people_unique_active_dated_relationship` zajišťuje u známého času
jedinečnost polí:

```text
person_a,
person_b,
relationship_type,
date_precision,
sort_date,
sort_date_end
```

Oba unikátní constrainty používají při modelové validaci kód
`duplicate_relationship`. Odlišné technické časové vymezení nebo jiná
přesnost mohou vytvořit další období. Po měkkém odstranění lze vytvořit
náhradu; obnovení původního záznamu může narazit na novější aktivní záznam.

### 9.8 Metadata a hranice M2.5b

Metadata jsou:

```python
verbose_name = "Vazba"
verbose_name_plural = "Vazby"
ordering = (
    "relationship_type__sort_order",
    "sort_date",
    "sort_date_end",
    "person_a_id",
    "person_b_id",
    "pk",
)
```

Textová reprezentace vrací
`"{person_a} – {relationship_type} – {person_b}"` a používá fallbacky
`"Neznámá osoba A"`, `"Vazba"` a `"Neznámá osoba B"`.

M2.5b neřeší rodičovské cykly, kontrolu věku, genealogickou
pravděpodobnost, překryvy období, automatický opačný řádek, automatické
vazby z událostí ani algoritmus odvození sourozenců. Tato pravidla patří
do budoucí doménové služby.

Tvrdé chyby zahrnují:

- vazbu osoby sama se sebou,
- přesnou aktivní duplicitu,
- obrácenou duplicitu symetrické vazby,
- cyklus přímého rodičovství,
- konec období před začátkem.

Biologické sourozenectví se primárně odvozuje ze společných biologických
rodičů. Explicitní sourozenecká vazba se používá u neznámých rodičů nebo
u adoptivního, nevlastního či sociálního sourozenectví.

### 9.9 Doménová služba vazeb

Veřejné zápisové rozhraní je v `people/services.py`:

```python
@dataclass(frozen=True, slots=True)
class RelationshipInput:
    relationship_type: RelationshipType
    person_a: Person
    person_b: Person
    note: str = ""
    access_level: str = AccessLevel.PUBLIC
    verification_status: str = VerificationStatus.UNCONFIRMED
    date_precision: str = DatePrecision.UNKNOWN
    date_qualifier: str = DateQualifier.NONE
    start_year: int | None = None
    start_month: int | None = None
    start_day: int | None = None
    end_year: int | None = None
    end_month: int | None = None
    end_day: int | None = None
    original_date_text: str = ""
    date_note: str = ""


def create_relationship(
    *,
    data: RelationshipInput,
    created_by: AbstractBaseUser | None = None,
) -> Relationship:
    ...


def update_relationship(
    *,
    relationship: Relationship,
    data: RelationshipInput,
) -> Relationship:
    ...
```

`created_by` není součástí dataclass. Create jej může nastavit po ověření
existence v aktuálním uživatelském modelu. Update mění typ, obě osoby,
poznámku, přístup, ověření a všechny historické části `PartialDateModel`,
ale nemění `created_by`, `created_at` ani lifecycle pole. Technická pole
`sort_date` a `sort_date_end` nejsou vstupem; odvozuje je modelové `save()`.

Create i update běží v `transaction.atomic()` a znovu načítají typ a osoby
z databáze. Každá mutace jako svůj první doménový zámek získá stejný
coarse-grained mutex nad prvním systémovým rodičovským `RelationshipType`.
Poté obě osoby zamyká jedním `select_for_update()` dotazem v rostoucím pořadí
PK bez ohledu na vstupní orientaci. Update mezi těmito kroky načítá aktuální
`Relationship` přes `select_for_update()` a pracuje s touto uzamčenou
instancí. Symetrický typ
normalizuje různé osoby podle PK před `full_clean()`; shodné osoby ponechá
modelové chybě `relationship_to_self`. Nesymetrická orientace se nemění.
Pokud žádný schválený rodičovský kód současně nemá `is_system=True`, služba
selže před dalším doménovým dotazem kódem
`relationship_configuration_invalid` a nezapisuje bez mutexu.

Archivovaná ani měkce odstraněná osoba není v M2.5c zakázána, pokud její
řádek existuje. Neaktivní `RelationshipType` nelze použít při create ani
na něj změnit typ při update. Existující vztah se stejným neaktivním typem
lze aktualizovat a na aktivní typ lze přejít. Archivovaný `Relationship`
lze aktualizovat; měkce odstraněný nikoli. Služba lifecycle pole nemění.

Neuložené nebo fyzicky chybějící instance používají servisní kódy
`relationship_unsaved`, `relationship_type_unsaved`,
`relationship_person_a_unsaved`, `relationship_person_b_unsaved` a
`relationship_created_by_unsaved`. Neaktivní typ používá
`relationship_type_inactive` a měkce odstraněný vztah
`relationship_deleted`. Modelové chyby se zachovávají.

Běžnou přesnou duplicitu zjistí `full_clean()`. Pokud souběžný zápis přesto
vyvolá `IntegrityError`, služba jej zachytí vně vnitřního atomického bloku
a po rollbacku ověří konflikt podle normalizované časové identity. Pouze
potvrzený konflikt převede na `ValidationError` s klíčem `__all__` a kódem
`duplicate_relationship`; jinou integritní chybu znovu vyvolá.

M2.5c nevytváří migraci. Nekontroluje rodičovské cykly, věk,
genealogickou pravděpodobnost ani překryvy období a nevytváří opačné,
odvozené či z událostí plynoucí vztahy. `is_derivable` zápis neomezuje.

### 9.10 Genealogická validace rodičovských cyklů

Společný orientovaný rodičovský graf tvoří přesně kódy:

```python
_PARENT_RELATIONSHIP_TYPE_CODES = frozenset(
    {
        "biological_parent",
        "adoptive_parent",
        "step_parent",
        "foster_parent",
    }
)
```

Uzel je `Person.pk` a hrana vede `Relationship.person_a_id →
Relationship.person_b_id`; osoba A je rodičovská osoba a osoba B dítě.
Všechny čtyři typy tvoří jeden graf. `guardian`, další systémové typy ani
budoucí uživatelské typy kategorie `parent_child` se automaticky
nezahrnují.

Graf obsahuje všechny vztahy s `deleted_at IS NULL` a rodičovským kódem.
Archivace, neaktivita typu, `UNKNOWN`, jednoduché přesnosti i historicky
ukončený `RANGE` hranu nevyřazují. Aktuální kalendářní platnost se
neposuzuje. Měkce odstraněný vztah se nezapočítává.

Neveřejný helper v `people/services.py` má kontrakt:

```python
def _validate_parent_relationship_cycle(
    *,
    relationship_type: RelationshipType,
    person_a: Person,
    person_b: Person,
    exclude_relationship_id: int | None = None,
) -> None:
    ...
```

Pro nerodičovský typ nebo shodné osoby skončí bez grafového dotazu.
V ostatních případech načte relevantní dvojice jedním querysetem přes
`select_for_update()`, při update vyloučí aktuální PK, sestaví v Pythonu
adjacency map `dict[int, set[int]]` a iterativním průchodem s `visited`
hledá cestu z osoby B do osoby A. Nalezená cesta znamená, že navrhovaná
hrana A → B uzavírá cyklus.

Create volá helper po načtení aktuálního typu a osob, kontrole aktivity a
případné normalizaci, ale před `full_clean()` a `save()`. Update postupuje
stejně nad výsledným navrhovaným stavem a vyloučí svůj současný řádek.
Změna z rodičovského na nerodičovský typ grafovou kontrolu neprovádí a může
starší cyklus opravit. Starší nesouvisející cyklus jinde v grafu změnu
neblokuje a `visited` zabraňuje nekonečnému průchodu.

Cyklus vyvolá:

```python
ValidationError(
    {
        "person_b": ValidationError(
            "Tato rodičovská vazba by vytvořila cyklus.",
            code="relationship_parent_cycle",
            params={
                "person_a_id": person_a.pk,
                "person_b_id": person_b.pk,
                "relationship_type_id": relationship_type.pk,
                "relationship_type_code": relationship_type.code,
            },
        )
    }
)
```

Kontrola běží uvnitř existujícího `transaction.atomic()`. SQLite provádí
`select_for_update()` prakticky jako no-op, včetně relationship mutation
mutexu; testy proto dokazují pořadí SQL protokolu, nikoli skutečné čekání
zámků. Obecný grafový cyklus nelze
vynutit běžným `CheckConstraint` a ani řádkové zámky nemusí bez silnější
izolace zachytit všechny phantom scénáře souběžně vkládaných hran. Pro
současný malý provoz je servisní transakční kontrola přiměřená.

M2.5d nemění modely, constrainty, systémová data ani migrace. Neřeší věk,
genealogickou pravděpodobnost, překryvy období, odvozování sourozenců ani
vztahy z událostí.

### 9.11 Čtecí odvození biologických sourozenců

Modul `people/selectors.py` vystavuje přesně:

```python
__all__ = ("get_biological_siblings",)


def get_biological_siblings(
    *,
    person: Person,
) -> QuerySet[Person]:
    ...
```

Pro různé osoby X a Y platí biologické sourozenectví právě tehdy, existuje-li
alespoň jedna osoba P a měkce neodstraněné vztahy `biological_parent` P → X
a P → Y. Jeden společný biologický rodič stačí. Plní a poloviční sourozenci
se v M2.5e nerozlišují a počet společných rodičů se nevrací. Jiné
rodičovské typy a explicitní vztahy `sibling`, `adoptive_sibling`,
`step_sibling` nebo `social_sibling` výsledek nevytvářejí ani nerozšiřují.

Oba rodičovské vztahy musí mít `deleted_at IS NULL`. Archivace, neaktivita
typu, `UNKNOWN`, jednoduchá přesnost i historicky ukončený `RANGE` se
započítávají a aktuální kalendářní platnost se neposuzuje. Výsledná osoba
musí mít `deleted_at IS NULL`, ale archivace ji nevylučuje. Vstupní osoba
musí mít PK a odpovídající databázový řádek; může být archivovaná i měkce
odstraněná. Chybějící řádek nebo PK vyvolá:

```python
ValidationError(
    {
        "person": ValidationError(
            "Osoba musí být před vyhledáním sourozenců uložena.",
            code="person_unsaved",
        )
    }
)
```

Po jednom `exists()` dotazu selector sestaví lazy ORM dotaz: subquery ID
biologických rodičů vstupu, subquery ID ostatních dětí těchto rodičů a
databázově deduplikovaný queryset osob. Vstupní a měkce odstraněné osoby
jsou vyloučeny. Nevzniká dotaz pro každého rodiče ani Pythonový průchod
grafem. Výsledek používá standardní `Person.Meta.ordering` podle příjmení a
jména.

Jde o nízkoúrovňový doménový selector bez parametru `actor`; nefiltruje
`Relationship.access_level` ani `Person.access_level` podle konkrétního
uživatele. Vyšší aplikační vrstva musí před zveřejněním ve view, API,
šabloně nebo exportu uplatnit pravidla viditelnosti. Toto rozdělení není
obecným povolením obcházet serverová oprávnění. Selector nic nemění ani
neukládá, nevytváří `Relationship` typu `sibling` a M2.5e nevytváří
migraci.

### 9.12 Agregovaný čtecí přehled sourozeneckých vazeb

Veřejné API `people/selectors.py` je rozšířeno na:

```python
__all__ = (
    "SiblingOverviewItem",
    "get_biological_siblings",
    "get_sibling_overview",
)


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

Stabilní pořadí důvodů určuje neveřejná konstanta:

```python
_SIBLING_REASON_ORDER = (
    "biological",
    "sibling",
    "adoptive_sibling",
    "step_sibling",
    "social_sibling",
)
```

`biological` označuje výsledek existujícího
`get_biological_siblings()` a není `RelationshipType.code`. Zbývající kódy
jsou jediné explicitní typy zahrnuté do přehledu. Každá osoba se seskupí
podle PK, objeví se jednou a zachová všechny skutečně zjištěné důvody bez
duplicit ve stabilním pořadí. Více historických období stejného typu důvod
neopakuje.

Explicitní vztahy se filtrují přes `Q(person_a=person) |
Q(person_b=person)` a druhá osoba se určí podle skutečné strany vztahu.
Selector nespoléhá na kanonické pořadí ani na aktuální hodnotu
`is_symmetric`. Vztah musí mít `deleted_at IS NULL`; archivace, aktivita typu
a časové vymezení se neposuzují. Výsledná osoba musí mít
`deleted_at IS NULL`, ale archivace ji nevylučuje. Vstupní osoba a chyba
`person_unsaved` zachovávají kontrakt M2.5e.

Agregace nejprve vyhodnotí biologický queryset a poté jedním querysetem se
`select_related("relationship_type", "person_a", "person_b")` načte
explicitní vztahy. Spolu s existence dotazem jde očekávaně o tři konstantní
dotazy bez N+1. Výsledné položky se řadí v Pythonu přesně podle
`(person.last_name, person.first_name, person.pk)`; PK je deterministický
fallback nad `Person.Meta.ordering`.

Selector nic neukládá, nepoužívá zápisové služby a nemá parametr `actor`.
Vyšší aplikační vrstva musí před zveřejněním ověřit viditelnost výsledné
osoby i každého explicitního vztahu a případně odstranit nepovolené důvody.
Permissionless přehled nesmí být přímo zveřejněn ve view, API nebo exportu.
M2.5f nevytváří modelovou změnu ani migraci.

### 9.13 Celkový agregovaný čtecí přehled vztahů

Veřejné API `people/selectors.py` je rozšířeno na:

```python
__all__ = (
    "RelationshipOverviewItem",
    "RelationshipOverviewReason",
    "SiblingOverviewItem",
    "get_biological_siblings",
    "get_relationship_overview",
    "get_sibling_overview",
)


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

Přehled seskupuje podle PK druhé osoby. Důvod identifikuje trojice
`category`, `relationship_code` a `label`. Více historických explicitních
řádků stejné identity vytváří jeden důvod a všechna jejich PK zůstávají
deduplikovaná a vzestupně seřazená v `relationship_ids`. Explicitní důvod
má `is_derived=False`. Biologický důvod nemá přímý řádek, proto používá
`relationship_ids=()` a `is_derived=True`.

Přehled volá `get_sibling_overview()` a nemění jeho veřejný kontrakt.
Pro provenance načte jedním querysetem explicitní typy `sibling`,
`adoptive_sibling`, `step_sibling` a `social_sibling`. Druhým querysetem
načte všechny ostatní explicitní systémové i uživatelské typy. Oba dotazy
hledají vstupní osobu na straně A nebo B a používají
`select_related("relationship_type", "person_a", "person_b")`. Spolu s
existence dotazem a dvěma dotazy M2.5f jde o pět konstantních dotazů bez
N+1.

Při vstupu na straně A popisuje druhou osobu `forward_label_*` zvolený
podle genderu osoby B. Při vstupu na straně B se použije `reverse_label_*`
podle genderu osoby A. `Gender.UNKNOWN` i nerozpoznaná hodnota používají
variantu `unknown`. Biologický důvod používá názvy „Biologický bratr“,
„Biologická sestra“ a „Biologický sourozenec“.

Stabilní pořadí kategorií určuje:

```python
_RELATIONSHIP_CATEGORY_ORDER = (
    "parent_child",
    "partner",
    "sibling",
    "godparent",
    "care",
    "social",
    "other",
)
```

Neznámá kategorie se řadí až za známé podle své hodnoty. V kategorii
`sibling` je biologický důvod před explicitními důvody; dále rozhoduje
`RelationshipType.sort_order`, kód a label. Výsledné osoby se řadí podle
`last_name`, `first_name` a PK.

Explicitní vztah musí mít `deleted_at IS NULL`; archivace, aktivita typu a
časová platnost se neposuzují. Výsledná osoba musí mít
`deleted_at IS NULL`, ale může být archivovaná. Vstupní osoba může být
archivovaná i měkce odstraněná, musí však mít existující databázový řádek.
Neplatný vstup zachovává chybu `person_unsaved`.

Selector nemá parametr `actor`, nefiltruje `access_level`, nic neukládá a
nevytváří odvozené řádky. Vyšší aplikační vrstva musí před zveřejněním
filtrovat výsledné osoby, znovu načíst a posoudit explicitní vztahy podle
`relationship_ids`, samostatně rozhodnout o viditelnosti biologického
důvodu a odstranit položky bez viditelného důvodu. M2.5g nevytváří
modelovou změnu, systémová data, migraci ani ACP.

### 9.14 Autorizovaný agregovaný přehled vztahů

Veřejné keyword-only API
`get_visible_relationship_overview(*, person, actor)` vrací stejné
`RelationshipOverviewItem` a `RelationshipOverviewReason` jako M2.5g.
Nejprve přes `can_view_access_level()` jednou vyhodnotí každou známou
úroveň, načte aktuálního actora pro lifecycle permissions a aktuální
databázový stav vstupní osoby. Neuložená nebo fyzicky chybějící osoba
používá `person_unsaved`; neviditelný vstup jednotnou `PermissionDenied`.

Vstupní osoba kombinuje `access_level`, `view_archived_person` a případně
`view_deleted_person`. Výsledná osoba musí být přístupná, archivovaná
vyžaduje `view_archived_person` a měkce odstraněná se vždy vyloučí.
Explicitní `relationship_ids` se jedním querysetem znovu načtou s
`deleted_at IS NULL` a filtrují podle `access_level`. Archivace vztahu,
aktivita typu a časová platnost nemění viditelnost.

Pro všechny biologické kandidáty se jedním querysetem se
`select_related("relationship_type", "person_a", "person_b")` načtou
orientované hrany `biological_parent` rodič → dítě. Důvod zůstane pouze
tehdy, když průnik viditelných rodičů vstupu a sourozence obsahuje alespoň
jedno stejné PK. Rodič musí být přístupný, při archivaci oprávněný a nesmí
být měkce odstraněný; obě hrany musí být přístupné a měkce neodstraněné.
Archivované hrany jsou platné. Hrany různých rodičů se nekombinují.

Po filtraci se vytvoří nové tuple, položky a změněné explicitní důvody bez
mutace permissionless frozen objektů. Prázdné důvody a položky se odstraní
a původní pořadí se nepřepočítává. Dotazový profil je konstantní vzhledem k
počtu osob, důvodů, ID i rodičů. M2.5h-2 nemění modely, systémová data ani
migrace.

## 10. Bydliště a hrobová místa

### 10.1 Bydliště

Bydliště spojuje právě jednu osobu s volitelným strukturovaným místem a časovým údajem.

M2.6a zavádí jeho typ jako samostatný model `ResidenceType`, který přímo
dědí z `LookupModel`, nepřidává vlastní databázová pole a zůstává
uživatelsky rozšiřitelný. Metadata jsou `verbose_name = "Typ bydliště"`,
`verbose_name_plural = "Typy bydliště"` a zděděné pořadí
`("sort_order", "name", "code")`.

Systémový katalog je:

| Kód | Název | Popis | Pořadí |
|---|---|---|---:|
| `primary_residence` | Hlavní bydliště | Obvyklé nebo hlavní bydliště osoby v daném období. | 10 |
| `temporary_residence` | Dočasné bydliště | Časově omezené bydliště nebo pobyt mimo hlavní bydliště. | 20 |
| `official_residence` | Úřední bydliště | Administrativně nebo úředně evidovaná adresa, která nemusí odpovídat skutečnému pobytu. | 30 |
| `institutional_residence` | Institucionální pobyt | Pobyt v instituci, například internátu, kasárnách, nemocnici, ústavu nebo domově. | 40 |
| `other` | Jiné bydliště | Jiný druh bydliště nebo pobytu nezařaditelný do předchozích typů. | 90 |

Hlavní bydliště je faktické nebo obvyklé bydliště. Úřední bydliště je
administrativně evidovaná adresa a nemusí mu odpovídat. Kódy `permanent` a
`permanent_residence` se nepoužívají, aby nebyly zaměněny s českým právním
pojmem trvalého pobytu.

Datová migrace nejprve prověří všech pět kódů. Uživatelský nesystémový
záznam se schváleným kódem nepřepíše ani nepřevede, ale vyvolá chybu před
první změnou katalogu. Forward je idempotentní a opravuje existující
systémové hodnoty. Reverse odstraní jen schválené kódy s aktuálním
`is_system=True`; uživatelské hodnoty zachová.

M2.6b přidává strukturální migrací `places.0005_residence` konkrétní model
`Residence`. Jeden řádek představuje jeden souvislý pobyt jedné osoby a v
přesném pořadí dědí `TimestampedModel`, `AccessControlledModel`,
`VerifiableModel`, `AuthoredModel`, `LifecycleModel` a `PartialDateModel`.
Lifecycle data archivace a měkkého odstranění nejsou historickým začátkem
ani koncem pobytu.

Vlastní pole modelu jsou:

- povinné `person` s `PROTECT` a reverzní vazbou `residences`,
- povinné `residence_type` s `PROTECT` a reverzní vazbou `residences`,
- volitelné `place` s `PROTECT`, `null=True`, `blank=True` a reverzní
  vazbou `residences`,
- `address_text` jako `CharField(max_length=500, blank=True)`,
- `note` jako `TextField(blank=True)`.

Musí existovat strukturované místo nebo text obsahující po `strip()` alespoň
jeden znak. Obě lokalizace mohou být vyplněny současně; `Place` pak
reprezentuje strukturovanou lokalitu a `address_text` konkrétní nebo
historický detail. Text se při `save()` automaticky nestripuje. Pravidlo je
modelové a nemá databázový `CheckConstraint`.

Překrývající se pobyty, více samostatných období stejného typu i zdánlivě
duplicitní tvrzení jsou povoleny. Model nemá vlastní unikátní constraint ani
dodatečný explicitní index; používá automatické FK indexy a index zděděného
`sort_date`. Uživatelské i neaktivní existující typy jsou na modelové vrstvě
přípustné. Pořadí je `person_id`, `sort_date`, `sort_date_end`,
`residence_type__sort_order`, `pk`. Samotný krok M2.6b ještě
neimplementoval služby, selectory, oprávněné čtení ani propojení s přílohami
a zdroji.

M2.6c zavádí transakční zápisovou vrstvu v `places/services.py`:

```python
create_residence(*, data: ResidenceInput, created_by=None) -> Residence
update_residence(*, residence: Residence, data: ResidenceInput) -> Residence
```

Frozen slotted `ResidenceInput` je úplný snapshot všech editovatelných
doménových polí Residence. Používá skutečná pole částečného data
`start_year`, `start_month`, `start_day`, `end_year`, `end_month` a
`end_day`; neobsahuje PK, timestampy, autora ani lifecycle. Update nahrazuje
celý editovatelný stav a může změnit osobu, typ i místo. Hodnota `place=None`
odstraní strukturované místo, pokud zůstane platná textová lokalizace.

Před zápisem se podle PK načte čerstvá osoba, typ, volitelné místo a při
create také volitelný autor. Update uvnitř `transaction.atomic()` zamkne a
načte čerstvý Residence přes `select_for_update()`, takže zastaralá vstupní
instance nepřepisuje novější typ, lifecycle ani autora. Neuložené nebo
fyzicky chybějící objekty používají stabilní kódy
`residence_unsaved`, `residence_person_unsaved`, `residence_type_unsaved`,
`residence_place_unsaved` a `residence_created_by_unsaved`.

Create odmítá neaktivní typ kódem `residence_type_inactive`. Update dovolí
zachovat aktuální neaktivní typ podle PK nebo přejít na aktivní typ, ale
zakáže přechod na jiný neaktivní typ stejným kódem. Měkce odstraněný
Residence odmítá `residence_deleted`; archivovaný lze upravit. Stále
existující archivované nebo měkce odstraněné osoby a místa jsou povoleny,
protože služba neřeší viditelnost ani oprávnění.

`address_text`, `note`, `original_date_text` a `date_note` se před
přiřazením stripují bez změny vnitřních mezer. Následuje úplný
`full_clean()` a běžný `save()`. Update zachovává `created_by`, `created_at`
a lifecycle metadata. Obecný `IntegrityError` se nemaskuje, protože model
nemá schválenou deduplikaci. M2.6c nevytváří migraci; selectory a oprávněné
čtení bydlišť v tomto kroku ještě nebyly řešeny.

M2.6d přidává nízkoúrovňový interní selector:

```python
get_person_residences(*, person: Person) -> QuerySet[Residence]
```

Vstup musí mít PK a stále existující databázový řádek, jinak selector vrací
`ValidationError` na `person` s kódem `person_unsaved`. Lifecycle ani
přístupovou úroveň vstupní osoby neposuzuje, takže přijímá také archivovaný
nebo měkce odstraněný existující řádek.

QuerySet filtruje `person_id` a `deleted_at__isnull=True`. Vrací úplnou
historii včetně archivovaných Residence, všech `AccessLevel` a stavů
ověření, neaktivních i uživatelských typů, volitelného místa a všech
časových variant. Nevyhodnocuje současné datum, aktuálnost, překryvy,
hlavní bydliště ani starší modelovou validitu lokalizace.

Deterministické databázové pořadí je:

```python
(
    "sort_date",
    "sort_date_end",
    "residence_type__sort_order",
    "residence_type__name",
    "pk",
)
```

`UNKNOWN` používá přirozené NULL pořadí databáze. Selector neprovádí
Python řazení. `select_related("person", "residence_type", "place",
"created_by")` umožňuje běžný přístup ke všem čtyřem vazbám bez N+1.
Volání provede jeden `exists()` dotaz; SELECT Residence zůstává lazy až do
vyhodnocení a jeho počet je konstantní. Selector nemá actor parametr,
nevolá permission policy a může vracet omezený nebo administrátorský
obsah. Autorizovaný selector vznikne v M2.6e. M2.6d nevytváří migraci.

M2.6e přidává vyšší veřejný selector:

```python
get_visible_person_residences(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[Residence]
```

Každý `AccessLevel` vyhodnotí nejvýše jednou přes
`can_view_access_level()`. Actor musí splnit společný kontrakt
`actor_invalid` / `actor_unsaved` a rozhoduje jeho aktuální databázový stav.
Selector načte čerstvou vstupní osobu; neuložená nebo fyzicky chybějící
používá `person_unsaved`. Její `access_level` musí být viditelný a
archivovaný či měkce odstraněný stav navíc vyžaduje odpovídající
`people.view_archived_person` nebo `people.view_deleted_person`. Při obou
stavech jsou nutná obě oprávnění. Neviditelná osoba vyvolá
`PermissionDenied("Nemáte oprávnění zobrazit tuto osobu.")`.

Po autorizaci selector volá permissionless
`get_person_residences(person=fresh_person)` a přidá
`filter(access_level__in=visible_access_levels)`. Residence SELECT proto
zůstává lazy a filtrování probíhá v databázi. Zachová se původní ordering,
`select_related()`, vyloučení `deleted_at IS NOT NULL`, archivované
Residence, historická i budoucí období a neaktivní nebo uživatelské typy.
Residence nemá samostatné lifecycle oprávnění a Place ani ResidenceType se
zvlášť neautorizují. Počet validačních a permission dotazů i výsledných
SELECTů je konstantní vzhledem k počtu Residence, bez N+1. M2.6e nevytváří
migraci.

### 10.2 Hrobové místo

Hrobové místo je samostatný fyzický nebo pamětní objekt. Obsahuje například:

- typ,
- fyzický stav existující/zaniklé/existence neznámá,
- místo nebo textovou lokalitu,
- oddíl, řadu a číslo,
- přepis nápisu,
- souřadnice,
- přílohy a zdroje.

Hlavní model se jmenuje `GraveSite` a explicitní propojení osoby
`PersonGraveSite`. Vznikají samostatně v M2.7b a M2.7c.

Pevný `places.choices.GraveSiteStatus` používá:

```python
class GraveSiteStatus(models.TextChoices):
    EXISTING = "existing", "Existující"
    DESTROYED = "destroyed", "Zaniklé"
    UNKNOWN = "unknown", "Existence neznámá"
```

Status popisuje současný nebo evidovaný fyzický stav místa. `destroyed`
není archivace ani měkké odstranění. `unknown` znamená neznámou současnou
existenci, nikoli neověřený zdroj. Přemístění ostatků není status.
`VerificationStatus` samostatně popisuje důvěryhodnost záznamu; příklady
M2.7a používají `verified`, `probable` a `unconfirmed`. Změna statusu nesmí
automaticky měnit `verification_status`, `archived_at` ani `deleted_at`.

`GraveSiteType` přímo dědí z `LookupModel` a obsahuje tento systémový
katalog:

| Kód | Název | Popis | Pořadí |
|---|---|---|---:|
| `grave` | Hrob | Hrobové místo určené k uložení tělesných ostatků; může být individuální i společné. | 10 |
| `tomb` | Hrobka | Stavebně vymezené hrobové místo nebo podzemní či nadzemní hrobka. | 20 |
| `urn_site` | Urnové místo | Místo určené k uložení urny, včetně urnového hrobu nebo jednotlivé kolumbární schránky. | 30 |
| `ossuary` | Kostnice | Místo společného uložení kosterních ostatků. | 40 |
| `scattering_place` | Místo rozptylu | Vymezené místo, na kterém byl proveden rozptyl popela. | 50 |
| `memorial` | Pamětní místo | Památník, deska nebo jiné místo připomínky bez tvrzení o uložení ostatků. | 60 |
| `cenotaph` | Symbolický hrob | Hrob nebo památník připomínající osobu, jejíž ostatky zde nejsou uloženy. | 70 |
| `other` | Jiné místo | Jiný druh hrobového, pohřebního nebo pamětního místa. | 90 |

Rodinné nebo společné užití není zvláštní typ; vyjádří je více vazeb osob.
Celé kolumbárium může být `Place`, konkrétní schránka používá `urn_site`.

`PersonGraveSiteRole` je druhý přímý `LookupModel`:

| Kód | Název | Popis | Pořadí |
|---|---|---|---:|
| `buried` | Pohřbena | Na místě byly uloženy tělesné ostatky osoby. | 10 |
| `urn_placed` | Uložena urna | Na místě byla uložena urna s popelem osoby. | 20 |
| `ashes_scattered` | Rozptýlena | Na místě byl rozptýlen popel osoby. | 30 |
| `commemorated` | Připomenuta | Osoba je na místě připomenuta nápisem, památníkem nebo symbolicky, bez tvrzení o uložení ostatků. | 40 |
| `remains_relocated_from` | Ostatky přemístěny z místa | Místo je doloženým výchozím místem přemístění ostatků. | 50 |
| `remains_relocated_to` | Ostatky přemístěny na místo | Místo je doloženým cílem přemístění ostatků. | 60 |
| `other` | Jiné propojení | Jiný význam propojení osoby s místem. | 90 |

`cenotaph` popisuje povahu objektu; konkrétní osoba má k němu typicky roli
`commemorated`. Tato role platí také pro památník nebo pamětní desku.
Směrové role přemístění rozlišují původní a cílové místo, ale M2.7a
nevytváří přesunovou událost, datum ani automatické párování.

Oba katalogy umožňují uživatelské hodnoty a vznikají strukturální migrací
`places.0006_grave_site_lookups`. Datová migrace
`places.0007_initial_grave_site_lookups` před prvním zápisem zkontroluje
kolize schválených kódů v obou tabulkách. Po úspěchu idempotentně vytvoří
nebo opraví systémové hodnoty. Reverse odstraní jen schválené kódy, které
jsou stále `is_system=True`.

M2.7b přidává hlavní model:

```python
class GraveSite(
    TimestampedModel,
    AccessControlledModel,
    VerifiableModel,
    AuthoredModel,
    LifecycleModel,
    models.Model,
):
    ...
```

Jeden řádek představuje jeden konkrétní fyzický nebo pamětní objekt.
`GraveSite` není obecné geografické `Place`, událost ani vazba osoby a
nepoužívá `PartialDateModel`. Datum pohřbu, přemístění ostatků nebo vzniku
památníku patří do události.

Povinné `grave_site_type` používá `PROTECT` a
`related_name="grave_sites"`. `status` je `CharField(max_length=20)` s
`GraveSiteStatus.choices` a defaultem `unknown`. Volitelné `place` také
používá `PROTECT`, `related_name="grave_sites"`, `null=True` a
`blank=True`.

Lokalizační a popisná pole jsou:

| Pole | Typ | Význam |
|---|---|---|
| `location_text` | `CharField(500, blank=True)` | Historická nebo neformální textová lokalita. |
| `cemetery_name` | `CharField(255, blank=True)` | Název hřbitova nebo areálu. |
| `section` | `CharField(100, blank=True)` | Oddíl včetně alfanumerického značení. |
| `row` | `CharField(100, blank=True)` | Řada včetně alfanumerického značení. |
| `grave_number` | `CharField(100, blank=True)` | Číslo nebo jiné označení místa. |
| `inscription` | `TextField(blank=True)` | Přepis nápisu. |
| `latitude` | `DecimalField(9, 6, null=True, blank=True)` | Přesná šířka objektu. |
| `longitude` | `DecimalField(9, 6, null=True, blank=True)` | Přesná délka objektu. |
| `note` | `TextField(blank=True)` | Interní nebo doplňující poznámka. |

Alespoň jeden z údajů `place`, neprázdný `location_text`, neprázdný
`cemetery_name` nebo úplná dvojice souřadnic musí být přítomen. Whitespace
se při validaci nepovažuje za lokalizaci, ale `save()` text automaticky
nestripuje. Chybějící lokalizace používá `location_text` a kód
`grave_site_location_required`.

Souřadnice musí být vyplněny společně. Neúplnost používá chybějící pole a
kód `grave_site_coordinates_incomplete`; šířka respektuje -90 až 90 a
délka -180 až 180. Souřadnice GraveSite mohou být přesnější než
souřadnice nadřazeného `Place`.

Model dovoluje neaktivní i uživatelský typ. Nevytváří unikátnost kombinace
hřbitova, oddílu, řady a čísla, žádný jiný `UniqueConstraint`, deduplikaci
ani explicitní index. Řazení je `cemetery_name`, `section`, `row`,
`grave_number`, `pk`. `__str__` používá v pořadí hřbitov, textovou
lokalitu, `Place`, souřadnice a neutrální fallback, doplněné identifikátory
a čitelným typem.

`status` popisuje fyzický stav. `verification_status`, `archived_at` a
`deleted_at` zůstávají samostatné dimenze a navzájem se automaticky
nemění. Model vzniká jedinou strukturální migrací
`places.0008_gravesite`, která kvůli zděděným uživatelským FK používá
swappable dependency na User. M2.7b nevytváří datovou migraci.

M2.7c přidává samostatné explicitní propojení osoby:

```python
class PersonGraveSite(
    TimestampedModel,
    AccessControlledModel,
    VerifiableModel,
    AuthoredModel,
    LifecycleModel,
    models.Model,
):
    ...
```

Jeden řádek je jedno tvrzení o konkrétní osobě, konkrétním hrobovém místě
a významu propojení. Model určuje například:

- pohřbena,
- uložena urna,
- rozptýlena,
- připomenuta nápisem,
- ostatky přemístěny z tohoto místa,
- ostatky přemístěny na toto místo.

Vlastní pole jsou pouze:

| Pole | Typ a integrita | Reverzní relace |
|---|---|---|
| `person` | povinný `ForeignKey(Person, PROTECT)` | `grave_site_links` |
| `grave_site` | povinný `ForeignKey(GraveSite, PROTECT)` | `person_links` |
| `role` | povinný `ForeignKey(PersonGraveSiteRole, PROTECT)` | `person_grave_site_links` |
| `note` | `TextField(blank=True)` | — |

Model používá timestamp, access, verification, author a lifecycle metadata
nezávislá na osobě a místě. Není událostí ani časovým intervalem a
nepoužívá `PartialDateModel`; datum pohřbu, rozptylu nebo přemístění patří
do události.

Jedna osoba může mít více propojení a jedno hrobové místo může být spojeno
s více osobami. U stejné osoby a místa lze uložit více rolí i více
samostatných tvrzení stejné role. Model proto nemá jednoduchou ani
složenou unikátnost, deduplikaci, vlastní constraint nebo explicitní
index. Modelová vrstva dovoluje neaktivní a uživatelskou roli a neověřuje
kompatibilitu role s typem hrobového místa.

Řazení je `person_id`, `grave_site_id`, `role__sort_order`, `role__name`,
`pk`. Obranný textový výstup má podobu osoba – role – hrobové místo.
Strukturální migrace `places.0009_persongravesite` vytváří pouze tento
model a závisí na `places.0008_gravesite`,
`people.0009_alter_person_options` a swappable User. M2.7c nevytváří
služby, selectory, autorizované čtení, události ani automatické párování
přesunových rolí.

M2.7d-1 přidává zápisovou doménovou vrstvu bez změny modelů a migrací:

```python
@dataclass(frozen=True, slots=True)
class GraveSiteInput:
    grave_site_type: GraveSiteType
    status: str = GraveSiteStatus.UNKNOWN
    place: Place | None = None
    location_text: str = ""
    cemetery_name: str = ""
    section: str = ""
    row: str = ""
    grave_number: str = ""
    inscription: str = ""
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    note: str = ""
    access_level: str = AccessLevel.PUBLIC
    verification_status: str = VerificationStatus.UNCONFIRMED
```

`GraveSiteInput` je úplný snapshot všech editovatelných údajů. Veřejné
keyword-only funkce jsou `create_grave_site(*, data, created_by=None)` a
`update_grave_site(*, grave_site, data)`. Snapshot nemůže nastavit PK,
časová pole, autora při update ani lifecycle metadata.

Obě služby používají `transaction.atomic()`, čerstvě načtou
`GraveSiteType` a volitelný `Place`; create navíc validuje čerstvého
volitelného autora. Texty `location_text`, `cemetery_name`, `section`,
`row`, `grave_number`, `inscription` a `note` stripují pouze na okrajích.
Souřadnice přijímají jako `Decimal | None` a jejich dvojici, rozsah i
desetinný kontrakt kontroluje nezměněný model přes `full_clean()` před
každým `save()`.

Create vyžaduje aktivní typ a nový výchozí lifecycle. Update načte
čerstvý `GraveSite` přes `select_for_update()`, odmítne fyzicky chybějící
nebo měkce odstraněný řádek, ale dovolí upravit archivovaný. Může změnit
typ, status, `Place`, souřadnice, texty, access i verification a může
`Place` nebo obě souřadnice odebrat. Stejný neaktivní typ lze zachovat,
přechod na jiný neaktivní typ je zakázán a přechod na aktivní povolen.
Archivovaný nebo měkce odstraněný, ale existující `Place` je přípustný.

Update pracuje s čerstvým řádkem a zachovává `created_by`, `created_at`,
archivní i mazací metadata; mění se běžné `updated_at`. Modelové klíče a
kódy validace se nemapují. Služba nevytváří doménovou unikátnost,
deduplikaci ani `duplicate_grave_site` a obecný `IntegrityError`
nepřevádí. Nevzniká migrace, služba `PersonGraveSite`, selector,
autorizované čtení ani permission policy.

M2.7d-2 doplňuje zápisovou vrstvu explicitní vazby bez změny modelů a
migrací:

```python
@dataclass(frozen=True, slots=True)
class PersonGraveSiteInput:
    person: Person
    grave_site: GraveSite
    role: PersonGraveSiteRole
    note: str = ""
    access_level: str = AccessLevel.PUBLIC
    verification_status: str = VerificationStatus.UNCONFIRMED
```

Jde o úplný snapshot editovatelných údajů. Keyword-only
`create_person_grave_site(*, data, created_by=None)` vytvoří novou vazbu a
`update_person_grave_site(*, link, data)` může opravit osobu, hrobové místo,
roli, poznámku, access i verification. PK, autorství, technické časy a
lifecycle nejsou součástí vstupu.

Obě služby v `transaction.atomic()` načtou čerstvou osobu, `GraveSite` a
`PersonGraveSiteRole`; create navíc čerstvého volitelného autora. Poznámku
stripují pouze na okrajích a před každým `save()` volají `full_clean()`.
Update zamkne aktuální `PersonGraveSite` přes `select_for_update()`,
odmítne fyzicky chybějící nebo měkce odstraněný řádek, ale dovolí změnit
archivovanou vazbu.

Nová vazba vyžaduje aktivní roli. Při update lze zachovat stejnou
neaktivní roli nebo přejít na aktivní, nikoli na jinou neaktivní roli.
Archivovaná nebo měkce odstraněná osoba i `GraveSite` zůstávají použitelná
a `GraveSite.status` zápis neomezuje. Update pracuje s čerstvou vazbou a
zachovává `created_by`, `created_at` a všechna lifecycle metadata.

Služby nevytvářejí kompatibilitní matici role a typu, automatické párování
`remains_relocated_from` a `remains_relocated_to`, unikátnost, deduplikaci
ani mapování obecného `IntegrityError`. Nevzniká migrace, selector,
autorizované čtení, lifecycle služba ani permission policy.

M2.7e-1 přidává nízkoúrovňový globální selector:

```python
def get_grave_sites() -> QuerySet[GraveSite]:
    return GraveSite.objects.filter(
        deleted_at__isnull=True,
    ).select_related(
        "grave_site_type",
        "place",
        "created_by",
    )
```

Selector nemá vstupní objekt ani actor a vrací lazy `QuerySet`. Jediným
filtrem je vyloučení soft-deleted řádků. Archivované `GraveSite`, statusy
`existing`, `destroyed` a `unknown`, všechny access a verification hodnoty
a aktivní, neaktivní, systémové i uživatelské typy jsou součástí
výsledku. Jde o interní permissionless vrstvu, která nesmí být bez vyšší
autorizace použita jako veřejný HTTP, API nebo exportní výstup.

Řazení přebírá `GraveSite.Meta.ordering`: `cemetery_name`, `section`,
`row`, `grave_number`, `pk`. `select_related()` načítá povinný typ,
volitelné `Place` a autora v jediném SELECTu; profil je konstantní pro
jeden i více výsledků. Samotné sestavení QuerySetu databázi nevyhodnotí.

Selector znovu nevolá modelovou validaci a vrací i historicky nevalidní,
ale nesmazaný řádek. Nepoužívá `prefetch_related()`, nenačítá
`person_links`, nepočítá osoby a nemění žádný objekt. Nevzniká migrace,
autorizované čtení ani permission policy.

M2.7e-2 doplňuje dva nízkoúrovňové selectory vazeb:

```python
def get_person_grave_site_links(
    *,
    person: Person,
) -> QuerySet[PersonGraveSite]:
    ...


def get_grave_site_person_links(
    *,
    grave_site: GraveSite,
) -> QuerySet[PersonGraveSite]:
    ...
```

Oba vstupy jsou keyword-only. Chybějící PK nebo fyzicky neexistující
databázový řádek vyvolá `ValidationError` s klíčem `person` a kódem
`person_unsaved`, respektive klíčem `grave_site` a kódem
`grave_site_unsaved`. Každé úspěšné volání provede právě jeden
`exists()` dotaz. Archivovaný nebo měkce odstraněný vstup se přijímá;
u `GraveSite` se nefiltruje ani `status`.

Výsledný `QuerySet[PersonGraveSite]` filtruje pouze zadaný FK a
`deleted_at IS NULL`. Archivované vazby, vazby na archivovanou nebo měkce
odstraněnou protistranu, všechny access a verification hodnoty a aktivní,
neaktivní, systémové i uživatelské role zůstávají zahrnuté. Více rolí a
zcela shodná tvrzení se vracejí samostatně. Selectory nepoužívají
`distinct()`, nevolají `full_clean()` a nekontrolují kompatibilitu role s
typem místa.

Přehled osoby používá:

```python
.order_by(
    "grave_site__cemetery_name",
    "grave_site__section",
    "grave_site__row",
    "grave_site__grave_number",
    "grave_site_id",
    "role__sort_order",
    "role__name",
    "pk",
)
```

Přehled jednoho místa používá:

```python
.order_by(
    "person_id",
    "role__sort_order",
    "role__name",
    "pk",
)
```

Oba QuerySety přes `select_related()` načítají `person`, `grave_site`,
`grave_site__grave_site_type`, `grave_site__place`, `role` a
`created_by`. Samotný SELECT vazeb se provede až při materializaci a jeho
počet neroste s počtem výsledků. Nevzniká prefetch, agregace, zápis,
migrace ani autorizovaná varianta; ta následuje v M2.7f.

M2.7f-1 přidává autorizovaný katalog:

```python
def get_visible_grave_sites(
    *,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[GraveSite]:
    visible_access_levels = tuple(
        access_level
        for access_level in _ACCESS_LEVELS
        if can_view_access_level(
            actor=actor,
            access_level=access_level,
        )
    )
    return get_grave_sites().filter(
        access_level__in=visible_access_levels,
    )
```

Každá známá hodnota `AccessLevel` se vyhodnotí nejvýše jednou. Centrální
policy validuje `actor_invalid` a `actor_unsaved` a pro uloženého
autentizovaného actora vždy načte čerstvý databázový stav. AnonymousUser
a neaktivní uživatel vidí pouze `public`, běžný aktivní uživatel také
`authenticated`, `restricted` a `admin_only` používají oddělené
permissions, `is_staff` samo přístup nerozšiřuje a aktivní superuser vidí
všechny úrovně.

Selector nevytváří vlastní základní dotaz. Filtr navazuje na
`get_grave_sites()`, takže zachovává `deleted_at IS NULL`, archivované
záznamy, `GraveSite.Meta.ordering` a
`select_related("grave_site_type", "place", "created_by")`. Neviditelné
access úrovně se tiše odfiltrují; nevyvolává se `PermissionDenied`.

Status `existing`, `destroyed` ani `unknown`, stav ověření, aktivita nebo
systémovost typu a lifecycle či access připojeného `Place` výběr dále
nemění. GraveSite nemá vlastní lifecycle permissions a soft-deleted řádek
se nevrací ani superuserovi. Výsledný QuerySet zůstává lazy a počet actor,
permission i výsledných dotazů je konstantní vzhledem k počtu míst.
Nevzniká migrace, změna centrální policy ani autorizace
`PersonGraveSite`; ta následuje v M2.7f-2.

M2.7f-2 doplňuje autorizované kolekční selectory:

```python
def get_visible_person_grave_site_links(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[PersonGraveSite]:
    ...


def get_visible_grave_site_person_links(
    *,
    grave_site: GraveSite,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[PersonGraveSite]:
    ...
```

Oba vstupy jsou keyword-only a představují chráněný cílový objekt.
Chybějící PK nebo fyzicky neexistující řádek zachovává klíč, kód i zprávu
permissionless `person_unsaved`, respektive `grave_site_unsaved`.
Existující vstup, který actor nesmí zobrazit, vyvolá `PermissionDenied`;
prázdný QuerySet se pro tento případ nepoužije.

Každou známou hodnotu `AccessLevel` selector vyhodnotí nejvýše jednou
centrálním `can_view_access_level()`. U vstupní osoby se nad čerstvým
stavem současně kontrolují `people.view_archived_person` a
`people.view_deleted_person`. U vstupního `GraveSite` archivace ani status
`existing`, `destroyed` nebo `unknown` přístup neomezují, ale soft-delete
jej odmítá i aktivnímu superuserovi. Actor kontrakt zachovává čerstvý stav,
`actor_invalid`, `actor_unsaved`, anonymní policy neaktivního uživatele a
oddělené `restricted` a `admin_only` permissions.

Po autorizaci vstupu se naváže na
`get_person_grave_site_links(person=current_person)`, respektive
`get_grave_site_person_links(grave_site=current_grave_site)`. Výsledný
ORM filtr vyžaduje `access_level__in` současně pro vazbu, osobu a hrobové
místo. Person lifecycle se přidává databázovou `Q` podmínkou podle obou
existujících oprávnění. `GraveSite.deleted_at IS NULL` je povinné;
permissionless základ už vylučuje měkce odstraněné `PersonGraveSite`.
Archivované vazby a místa zůstávají zahrnuté. Neviditelný
jednotlivý řádek nebo protistrana se na rozdíl od vstupu tiše odfiltrují.

Status, verification, aktivita či systémovost `GraveSiteType` a
`PersonGraveSiteRole` výběr nemění. `Place` se neautorizuje samostatně.
Nepoužívá se Python filtrování, prefetch ani `distinct()`, takže legitimní
duplicitní tvrzení zůstávají samostatnými řádky.

Oba QuerySety zachovávají přesné ordering a `select_related()` M2.7e-2
pro `person`, `grave_site`, `grave_site__grave_site_type`,
`grave_site__place`, `role` a `created_by`. Samotný SELECT vazeb zůstává
lazy a actor, permission a vstupní dotazy mají konstantní počet bez
ohledu na množství výsledků. Krok nic nezapisuje a nevytváří modelovou
změnu, migraci, nový permission codename ani ACP.

## 11. Přílohy

První implementační řez zavádí dva prázdné katalogy:

- `AttachmentCategory` — uživatelsky rozšiřitelná kategorie přílohy,
- `AttachmentRole` — uživatelsky rozšiřitelný význam explicitního propojení.

Oba přímo dědí z `LookupModel`, mají pouze jeho společná pole a používají
admin guard systémové identity. Migrace `materials.0001_attachment_lookups`
je čistě strukturální a záměrně nevytváří žádné neschválené seed hodnoty.

Druhý řez zavádí pevný `FileStatus`:

| Hodnota | Význam |
|---|---|
| `pending` | Databázový záznam existuje, fyzický soubor ještě není potvrzen jako připravený. |
| `available` | Fyzický soubor je dostupný pro běžné použití. |
| `missing` | Očekávaný fyzický soubor není dostupný. |
| `quarantined` | Soubor je záměrně vyřazen kvůli bezpečnostní nebo integritní kontrole. |

Výchozí je `pending`. Pouze `available` smí budoucí doručovací vrstva vydat;
ostatní stavy jsou fail-closed bez ohledu na actorova oprávnění. `FileStatus`
není access úroveň a zůstává nezávislý na archivaci a soft-delete.

Konkrétní `Attachment` dědí v tomto pořadí z `TimestampedModel`,
`PartialDateModel`, `AccessControlledModel`, `AuthoredModel`, `LifecycleModel`
a `models.Model`; `VerifiableModel` nepoužívá. Obsahuje:

- povinnou chráněnou `category` na `AttachmentCategory`,
- volitelný `display_name` a `description`,
- povinný `original_filename`, unikátní neprůhledný `storage_key`, `mime_type`
  a nezápornou `size_bytes`,
- lowercase SHA-256 délky 64 s indexem bez unikátnosti,
- indexovaný `file_status` s výchozím `pending`,
- volitelné `creator_name`, `provenance`, `original_owner` a `language`,
- `technical_metadata` jako JSON objekt s výchozí prázdnou mapou,
- společná pole neúplného data, access, autorství a lifecycle.

`storage_key` je pouze backendově neutrální interní identifikátor objektu.
Migrace `materials.0002_attachments` má swappable dependency na User a
nevytváří fyzický soubor ani volbu storage backendu. `Attachment` není
registrován v adminu a zatím nemá službu, selector, vazby, URL, API ani UI.
Budoucí doručení musí kombinovat `available` s nejpřísnější policy přílohy,
vazby a cílového objektu; přímý storage odkaz není autorizační hranice.

Příloha reprezentuje jeden fyzicky uložený digitální soubor a jeho metadata.

Obsahuje zejména:

- kategorii,
- uživatelský název a popis,
- původní název souboru,
- interní klíč úložiště,
- MIME typ a velikost,
- kontrolní součet SHA-256,
- stav souboru,
- autora nebo původce,
- původ materiálu,
- vlastníka originálu,
- jazyk,
- datum vzniku,
- technická metadata,
- přístupovou úroveň.

Soubor se ukládá pouze jednou. Připojuje se explicitními spojovacími modely k osobě, události, vazbě, bydlišti, zdravotnímu záznamu, hrobovému místu, místu a zdroji.

Spojení obsahuje:

- roli přílohy,
- popis souvislosti,
- pořadí,
- příznak hlavní přílohy.

Budoucí ověřená hlavní fotografie smí být reprezentována pouze přes
`PersonAttachment`; na osobě není druhý přímý odkaz. Současný obecný příznak
`is_primary` sám fotografický význam nezakládá.

Třetí implementační řez konkretizuje šest aktuálně realizovatelných vazeb:
`PersonAttachment`, `EventAttachment`, `RelationshipAttachment`,
`ResidenceAttachment`, `GraveSiteAttachment` a `PlaceAttachment`. Společný
abstraktní základ dědí `TimestampedModel`, `AccessControlledModel`,
`AuthoredModel` a `LifecycleModel`; nepoužívá `VerifiableModel` ani
`PartialDateModel`. Každý konkrétní model používá `PROTECT` pro cíl,
`Attachment` i `AttachmentRole` a obsahuje `context_description`, nezáporné
`sort_order` s výchozí nulou a `is_primary` s výchozí `False`.

Pouze `PersonAttachment` má podmíněnou databázovou unikátnost osoby pro
`is_primary=True` a `deleted_at IS NULL`. Archivovaná vazba zůstává v tomto
významu aktivní, měkce odstraněná nikoli. `is_primary` zatím znamená primární
reprezentaci osoby, nikoli automaticky fotografii; neexistuje seed role ani
kontrola kategorie či MIME. Stav přílohy vazbu automaticky nemění.

`AttachmentLinkInput` a čtrnáct veřejných create/update služeb v
`materials.services` znovu načítá roli, autora, oba endpointy a při update i
vazbu pod transakčními zámky a volá `full_clean()`. Create odmítá archivovaný
nebo měkce odstraněný endpoint. Update dovoluje zachovat tentýž mezitím
archivovaný endpoint, ale nepřipojí jiný archivovaný endpoint a vždy odmítne
soft-delete; archivovanou vazbu lze měnit, soft-deleted nikoli. Neaktivní
roli nelze nově použít, ale stávající lze při update zachovat. Potvrzený
souběžný konflikt primární vazby se převádí na stabilní validační kód a jiné
`IntegrityError` se nemaskují.

Migrace `materials.0003_attachment_links` je strukturální. Modely nejsou v
adminu a nevzniká selector, URL, upload, doručení ani UI. Budoucí aplikační
zápis musí před službou serverově autorizovat při create cíl, přílohu i
vytvoření kontextu; při update existující vazbu v dosavadním kontextu a každý
měněný endpoint i oprávnění mutace. Budoucí čtení a doručení musí být
kontextové přes konkrétní vazbu a vyhodnotit nejpřísnější
access/lifecycle přílohy, vazby a cíle společně s `FileStatus.AVAILABLE`.
`HealthRecordAttachment` a `HealthRecordSource` doplňují explicitní vazby ke
zdravotnímu záznamu. Případné další vazby na dosud nepokryté doménové cíle
zůstávají samostatnými budoucími modely.

První čtecí řez nad vazbami osoby zavádí
`get_person_attachment_links(*, person)` a
`get_visible_person_attachment_links(*, person, actor)`. Permissionless
varianta vrací lazy interní historii vazeb s `deleted_at IS NULL` bez
autorizace, filtrování stavu přílohy nebo jejího lifecycle. Autorizovaná
varianta nejprve chrání vstupní osobu čerstvým stavem access a jejími
existujícími lifecycle permissions a pak databázově vyžaduje viditelnou access
úroveň osoby, vazby i přílohy, měkce neodstraněnou vazbu a přílohu a
`attachment.file_status = available`. Vazba i příloha navíc musí být
nearchivované; dokud pro materiály neexistuje explicitní lifecycle oprávnění,
je běžné actor-aware čtení v této vrstvě konzervativně fail-closed.

Archivované vazby a přílohy zůstávají dostupné pouze v permissionless interní
historii; neaktivní kategorie a role nejsou samostatnou autorizační vrstvou.
Oba selectory zachovávají modelové řazení a přednačítají osobu, přílohu,
kategorii, roli a autory jedním výsledkovým dotazem bez N+1. Nevydávají fyzický
soubor ani storage URL a budoucí doručení musí konkrétní kontext autorizovat
znovu. Další cílové typy dostanou vlastní kontextové selectory až podle své
target policy; obecný `Place` tento řez nezpřístupňuje.

Kontext události analogicky poskytuje `get_event_attachment_links(*, event)`
a `get_visible_event_attachment_links(*, event, actor)`. Permissionless
varianta zachovává interní historii všech měkce neodstraněných vazeb události.
Actor-aware varianta nejprve načte aktuální událost a odmítne neviditelnou,
archivovanou nebo měkce odstraněnou událost. Výsledkový SQL filtr znovu
vyžaduje viditelnou access úroveň události, vazby a přílohy, nearchivovaný a
měkce neodstraněný stav všech tří vrstev a `FileStatus.AVAILABLE`.

Oba event selectory zachovávají modelové řazení a přednačítají událost, její
typ a místo, přílohu, kategorii, roli a autory bez výsledkového N+1. Aktivita
typu události, kategorie a role není samostatnou autorizační vrstvou. Ani tento
kontext nevydává fyzický soubor či storage URL a budoucí doručení musí
konkrétní vazbu autorizovat znovu.

## 12. Zdroje

Zdroj popisuje původ informace, nikoli samotný digitální soubor.

`Source` je znovupoužitelný informační pramen. Povinný `SourceType` klasifikuje
jeho druh a `SourceRole` patří až explicitní vazbě, kde popisuje význam zdroje
vůči jednomu konkrétnímu doménovému objektu. Oba katalogy jsou uživatelsky
rozšiřitelné modely nad `LookupModel` a první strukturální migrace
`materials.0004_source_lookups` je vytváří prázdné bez systémových seed hodnot.

Kromě názvu a typu mohou být bibliografické údaje neúplné. Globální hodnocení
důvěryhodnosti zdroje se v této etapě nemodeluje. Implementovaný `Source` dědí
`TimestampedModel`, `PartialDateModel`, `AccessControlledModel`,
`AuthoredModel` a `LifecycleModel`; nedědí `VerifiableModel`.

Vlastní pole modelu jsou:

- `source_type` — povinný `ForeignKey` na `SourceType`, `null=False`,
  `blank=False`, `on_delete=models.PROTECT`, `related_name="sources"`,
- `title` — povinný `CharField(max_length=255)`; vlastní modelová validace
  odmítne název tvořený pouze mezerami kódem `source_title_required`,
- `full_citation` — `TextField(blank=True)`,
- `institution`, `fonds` a `shelfmark` — volitelné `CharField(max_length=255)`,
- `volume` a `inventory_number` — volitelné `CharField(max_length=100)`,
- `creator_name` — `CharField(max_length=255, blank=True)`,
- `publication_details` — `TextField(blank=True)`,
- `url` — `URLField(max_length=500, blank=True)`,
- `accessed_on` — `DateField(null=True, blank=True)`,
- `external_identifier` — `CharField(max_length=255, blank=True)`,
- `note` — `TextField(blank=True)`.

Neúplné historické nebo publikační datum je uloženo společnými poli
`PartialDateModel`; přesné datum přístupu zůstává oddělené. Bibliografická pole
nemají dodatečnou unikátnost. Metadata používají `verbose_name = "Zdroj"`,
`verbose_name_plural = "Zdroje"` a `ordering = ("title", "pk")`.
Strukturální migrace `materials.0005_sources` vytváří jedinou tabulku bez seed
dat. Model zatím není registrován v adminu ani vystaven službou, selectorem,
API nebo UI.

Zdroj se explicitně váže ke konkrétním strukturovaným záznamům, zejména k:

- dalšímu jménu osoby,
- události,
- vazbě,
- bydlišti,
- zdravotnímu záznamu,
- hrobovému místu,
- příloze.

Propojení obsahuje roli zdroje, citovanou část, krátký úryvek, výklad a sílu podpory. Zdroj může tvrzení potvrzovat, naznačovat, doplňovat nebo mu odporovat.

Implementovaný pevný `SourceSupport` obsahuje technické hodnoty `confirms`,
`suggests`, `supplements` a `contradicts` s českými popisky. Nemá databázovou
tabulku ani výchozí hodnotu. Společný abstraktní `SourceLinkModel` dědí
`TimestampedModel`, `AccessControlledModel`, `AuthoredModel` a
`LifecycleModel` a obsahuje:

- `source` — povinný chráněný FK na `Source`,
- `role` — povinný chráněný FK na `SourceRole`,
- `cited_part` — `CharField(max_length=255, blank=True)`,
- `excerpt` a `interpretation` — `TextField(blank=True)`,
- `support_strength` — povinný `CharField(max_length=20,
  choices=SourceSupport.choices)` bez defaultu.

Migrace `materials.0006_source_links` vytvořila modely `PersonNameSource`,
`EventSource`, `RelationshipSource`, `ResidenceSource`, `GraveSiteSource` a
`AttachmentSource`; pozdější `materials.0008_health_record_source` přidává
sedmý model `HealthRecordSource`. Každý používá povinný `ForeignKey` na jediný
pojmenovaný cíl s `on_delete=models.PROTECT` a
`related_name="source_links"`; zdroj i role jsou rovněž chráněné. Duplicity
nejsou dodatečně zakázané a žádný model nepoužívá generický vztah. Strukturální
migrace nevkládají seed data. Modely nejsou registrované v adminu ani vystavené
API nebo UI; interní služby a actor-aware selectory vznikají v navazujících
samostatných řezech.

Interní zápisová hranice používá frozen slotted `SourceLinkInput` a samostatné
typované create/update funkce pro všech sedm modelů. V transakci vždy znovu
načte konkrétní cíl, zdroj, roli a volitelného autora a před uložením provede
`full_clean()`. Create odmítá archivovaný či odstraněný cíl nebo zdroj a
neaktivní roli. Update odmítá odstraněnou vazbu nebo endpoint, dovoluje však
zachovat stejný mezitím archivovaný cíl či zdroj a stejnou mezitím neaktivní
roli; na jiný takový endpoint přejít nesmí. Archivovaná vazba zůstává
editovatelná a textový kontext se ořezává.

Tyto služby neověřují actor oprávnění. Před aplikačním použitím musí
volající autorizovat create nad cílem, zdrojem a vznikem kontextu; update musí
nejprve autorizovat dosavadní konkrétní cestu a potom každý měněný endpoint i
samotnou mutaci. Pro jednotlivé kontexty existují samostatné actor-aware read
selectory včetně `HealthRecordSource`; admin, API a UI zatím nevznikají.

První čtecí hranice zdrojů je záměrně kontextová. Permissionless
`get_person_name_source_links(*, person_name)` vrací lazy historii všech
měkce neodstraněných `PersonNameSource`. Actor-aware
`get_visible_person_name_source_links(*, person_name, actor)` vyžaduje
viditelnou rodičovskou osobu a viditelné, nearchivované a neodstraněné jméno.
Výsledek současně databázově filtruje access osoby, jména, vazby a zdroje a
vylučuje archivované či odstraněné jméno, vazbu a zdroj. Lifecycle osoby
respektuje `people.view_archived_person` a `people.view_deleted_person` a je
znovu součástí výsledkového filtru, takže změna mezi vytvořením a vyhodnocením
lazy querysetu selže uzavřeně.

Oba selectory načítají `PersonName`, osobu, typ jména, `Source`, typ zdroje,
roli a autory přes `select_related()`. Jiná viditelná vazba ke stejnému zdroji
se dotazu neúčastní a nemůže potvrdit chráněný cíl. Obecný selector podle
`Source.id`, admin, API ani UI nevznikají.

Kontext události tvoří `get_event_source_links(*, event)` a
`get_visible_event_source_links(*, event, actor)`. Permissionless varianta
vrací lazy historii nesmazaných `EventSource`. Actor-aware varianta nejprve
vyžaduje viditelný, nearchivovaný a neodstraněný vstupní `Event` a výsledek
znovu databázově filtruje access a lifecycle události, vazby a zdroje. Načítá
event, jeho typ, místo a autora, zdroj, typ zdroje a autora, roli a autora vazby
přes `select_related()` bez N+1.

Dotaz je omezen konkrétním `event_id`; žádná jiná vazba ke sdílenému zdroji se
jej neúčastní a nemůže potvrdit chráněnou událost. Obecný selector podle
`Source.id`, admin, API a UI nevznikají.

Kontext vztahu používá `get_relationship_source_links(*, relationship)` a
`get_visible_relationship_source_links(*, relationship, actor)`. Actor-aware
varianta vyžaduje viditelný neodstraněný vztah a obě viditelné propojené osoby.
Archivovaný vztah zůstává historicky čitelný, archivovaná osoba vyžaduje
`people.view_archived_person` a odstraněná osoba se nevydá ani superuserovi.
Výsledek znovu databázově filtruje access a lifecycle vztahu, obou osob,
zdrojové vazby a zdroje; vazba a zdroj musí být nearchivované a neodstraněné.

Selectory přednačítají typ vztahu, obě osoby, zdroj a jeho typ, roli a autory.
Dotaz je omezen konkrétním `relationship_id`, takže jiná vazba ke sdílenému
zdroji nemůže odhalit chráněný vztah ani účastníka.

Přílohy vztahu používají `get_relationship_attachment_links(*, relationship)`
a `get_visible_relationship_attachment_links(*, relationship, actor)`.
Actor-aware varianta chrání vztah i obě osoby stejnou policy jako zdrojový
kontext a výsledné SQL vyžaduje viditelnou, nearchivovanou a neodstraněnou
vazbu i přílohu a `FileStatus.AVAILABLE`.

Selectory přednačítají typ vztahu, obě osoby, přílohu a její kategorii, roli a
autory. Dotaz je omezen konkrétním `relationship_id`; sdílená příloha proto
neodhaluje jiné chráněné vztahy. Selector nevydává storage URL a není
autorizační hranicí budoucího doručení souboru.

Přílohy bydliště používají `get_residence_attachment_links(*, residence)` a
`get_visible_residence_attachment_links(*, residence, actor)`. Actor-aware
varianta vyžaduje viditelné měkce neodstraněné bydliště a viditelnou
rodičovskou osobu; její lifecycle respektuje `people.view_archived_person` a
`people.view_deleted_person`. Archivované bydliště zůstává zahrnuté a připojené
`Place` není samostatnou autorizační vrstvou.

Výsledné SQL znovu filtruje access a lifecycle bydliště a osoby, vazby a
přílohy a vyžaduje `FileStatus.AVAILABLE`. Selectory přednačítají celý kontext
bez N+1, jsou omezené konkrétním `residence_id`, nevydávají storage URL a
sdílená příloha nemůže odhalit jiné chráněné bydliště.

Zdroje bydliště používají `get_residence_source_links(*, residence)` a
`get_visible_residence_source_links(*, residence, actor)`. Actor-aware varianta
chrání bydliště a rodičovskou osobu stejnou policy jako přílohový kontext,
zachovává archivované bydliště a neautorizuje samostatně připojené `Place`.

Výsledné SQL znovu filtruje access a lifecycle bydliště, osoby, vazby a zdroje.
Selectory přednačítají celý kontext bez N+1 a jsou omezené konkrétním
`residence_id`, takže sdílený zdroj nemůže potvrdit jiné chráněné bydliště.

Přílohy hrobového místa používají
`get_grave_site_attachment_links(*, grave_site)` a
`get_visible_grave_site_attachment_links(*, grave_site, actor)`. Actor-aware
varianta vyžaduje viditelné, měkce neodstraněné hrobové místo a zachovává jeho
archivaci. Status, verification, typ a připojené `Place` se samostatně
neautorizují.

Výsledné SQL znovu filtruje access a lifecycle místa, vazby a přílohy a
vyžaduje `FileStatus.AVAILABLE`. Selectory přednačítají celý kontext bez N+1,
jsou omezené konkrétním `grave_site_id`, nevydávají storage URL a sdílená
příloha nemůže odhalit jiné chráněné místo.

Zdroje hrobového místa používají `get_grave_site_source_links(*, grave_site)`
a `get_visible_grave_site_source_links(*, grave_site, actor)`. Actor-aware
varianta chrání hrobové místo stejnou policy jako přílohový kontext, zachovává
jeho archivaci a neautorizuje samostatně status, verification, typ ani
připojené `Place`.

Výsledné SQL znovu filtruje access a lifecycle místa, vazby a zdroje. Selectory
přednačítají celý kontext bez N+1 a jsou omezené konkrétním `grave_site_id`,
takže sdílený zdroj nemůže potvrdit jiné chráněné hrobové místo.

Access policy cílového doménového objektu je pro každou vazbu povinná.
Případná vlastní access úroveň vazby nebo zdroje ji smí pouze zpřísnit a
lifecycle se vyhodnocuje na všech objektech konkrétní cesty. Existence jiné
přístupné vazby ke stejnému `Source` nesmí zpřístupnit ani potvrdit existenci
chráněného cíle. Budoucí actor-aware čtení proto musí zůstat kontextové;
obecný lookup podle `Source.id` není autorizační hranice.

Univerzální systém zdrojování libovolného databázového pole není součástí první verze.

## 13. Zdravotní záznamy

Zdravotní záznam patří právě jedné osobě a má samostatný typ.

První realizovaný strukturální řez vytváří konkrétní
`health.HealthRecordType` nad společným `LookupModel`. Nepřidává vlastní pole,
seed data ani stabilní systémové kódy.

Navazující `HealthRecord` dědí timestamp, access, verification, autorství,
lifecycle a neúplný čas. Povinné `person` a `record_type` i volitelné `place`
používají `PROTECT`; textová data tvoří `title`, `description`,
`provider_name` a `note`, přičemž název nebo popis musí být neprázdný.
Nevzniká unikátnost ani dodatečný index nad obsahem.

Podporované typy zahrnují:

- diagnózu,
- vyšetření,
- operaci,
- úraz,
- očkování,
- alergii,
- lék,
- hospitalizaci,
- dlouhodobý stav,
- tělesnou zvláštnost,
- jiné zdravotní informace.

Záznam obsahuje název nebo popis, časový údaj, lékaře či zařízení, volitelné místo, stav ověření, přílohy, zdroje a přístupovou úroveň.

Výchozí a nejširší povolená viditelnost je `restricted`; databázový constraint
zakazuje `public` a `authenticated` a dovoluje také přísnější `admin_only`.
V M2 se nezavádí zdravotní permission. Všechna současná i budoucí actor-aware
použití musí procházet `health.permissions.can_view_health_record_access()`, který
dnes deleguje na obecný access helper a zachovává místo pro budoucí rozšíření
bez změny modelu. Zdravotní záznam se neukládá současně jako obecná událost,
ale může se zobrazit v obecné časové ose. Strukturální migrace
`health.0002_health_records` nevystavuje model adminem, službou, selectorem,
API ani UI.

Transakční create/update služby používají úplný `HealthRecordInput`, explicitní
actor parametr, čerstvé uzamčené FK a `full_clean()`. Čerstvě načtený aktivní
actor musí mít existující standardní Django permission
`health.add_healthrecord`, respektive `health.change_healthrecord`, a obsahový
přístup k osobě i health access záznamu. Create nastaví `created_by` na actora.
Update načte zamčený aktuální záznam přes úplný health visibility filtr a
zachová jeho čerstvé autorství i lifecycle. Skrytý, archivovaný, odstraněný,
chybějící nebo typově neaktivní aktuální cíl je jednotně nedostupný. Aktivní typ
je povinný i pro navržený stav; dřívější výjimka pro zachování neaktivního typu
neplatí. Tento řez nevytváří další migraci ani vlastní permission.

Actor-aware read selectory používají jediný centralizovaný health filtr.
Záznam se vydá pouze tehdy, když je osoba běžně viditelná a aktivní, jeho
vlastní access projde health policy, záznam není archivovaný ani odstraněný a
typ je aktivní. Kolekce i detail staví nad stejným lazy querysetem a
přednačítají osobu, typ, místo i autora. Neplatný či skrytý detail je jednotně
nedostupný. Nevzniká nový permission, modelová nebo migrační změna.

Volitelné `Place` je pouze kontext záznamu; jeho access ani lifecycle se v
health selectoru samostatně neautorizují a nemění viditelnost záznamu.

`HealthRecordAttachment` dědí beze změny ze společného `AttachmentLinkModel` a
obsahuje chráněné FK `health_record`, `attachment` a `role`. Reverse vazby jsou
`HealthRecord.attachment_links` a `Attachment.health_record_links`; řazení je
podle záznamu, `sort_order`, pořadí role a PK. Migrace
`materials.0007_health_record_attachment` je čistě strukturální.

Zápisy používají stávající `AttachmentLinkInput`. Konkrétní health attachment
create/update služby jsou actor-aware: vyžadují čerstvého aktivního actora se
standardním `materials.add_healthrecordattachment`, respektive
`materials.change_healthrecordattachment`, a samy vynucují centrální health
policy, access a aktivní lifecycle vazby i přílohy a
`FileStatus.AVAILABLE`. Create nastavuje autora na actora a update zachovává
autorství i lifecycle. Obecné attachment služby jiných kontextů zůstávají
permissionless podle svého dosavadního kontraktu. Veřejné čtení je pouze
`get_visible_health_record_attachment_links(*, health_record, actor)`. Selector
ověří vstup přes `get_health_record_visibility_filter()` a stejný filtr vloží i
do výsledného SQL. Dále filtruje access a aktivní lifecycle vazby i přílohy a
vyžaduje `FileStatus.AVAILABLE`. Vrací lazy přednačtený
`QuerySet[HealthRecordAttachment]`; nečte fyzický soubor, nevydává storage URL a
neexistuje obecný selector podle ID přílohy nebo vazby.

`HealthRecordSource` dědí ze společného `SourceLinkModel` a chráněnými FK
propojuje `HealthRecord`, `Source` a `SourceRole`. Reverse vazby jsou
`HealthRecord.source_links` a `Source.healthrecordsource_links`; řazení je podle
záznamu, pořadí role a PK. Create/update používají stávající `SourceLinkInput` a
generickou transakční source service. Strukturální migrace
`materials.0008_health_record_source` nevkládá data.

Jediný veřejný read selector je
`get_visible_health_record_source_links(*, health_record, actor)`. Vstup ověří
centralizovaným health filtrem a stejnou policy ponechá i v lazy výsledném SQL.
Zdrojová vazba i zdroj musí projít obecný access a být nearchivované a
neodstraněné. Selector vrací přednačtený `QuerySet[HealthRecordSource]`; obecná
cesta podle ID zdroje nebo vazby nevzniká.

První aplikační read-only hranici tvoří `health.use_cases` s keyword-only
`list_health_records(*, person, actor)` a
`get_health_record_detail(*, health_record_id, actor)`. Obě funkce pouze vracejí
výsledek existujících actor-aware health selectorů, a proto nevytvářejí vlastní
ORM visibility dotaz ani access/lifecycle pravidla. Detail zachovává původní
`HealthRecord.DoesNotExist`. Use-case nepřipojuje zdroje či přílohy, nečte
reverse relations a nemění model ani migrace; nevzniká HTTP, API, UI nebo zápis.

Stejný modul vystavuje také keyword-only
`create_health_record(*, data, actor)` a
`update_health_record(*, health_record, data, actor)`. Obě aplikační funkce
pouze vracejí výsledek stejnojmenné actor-aware doménové služby a nepoužívají
vlastní ORM, permission, access, lifecycle ani validační podmínky. Výjimky
service vrstvy propouštějí beze změny.

Pro vazbu přílohy modul obdobně vystavuje
`create_health_record_attachment(*, health_record, data, actor)` a
`update_health_record_attachment(*, link, health_record, data, actor)`. Jde o
přesné delegace na autorizované materials služby bez vlastního ORM nebo policy;
nevydávají storage URL ani obsah souboru.

## 14. Uživatelé a oprávnění

Použije se vlastní Django uživatelský model založený na standardních mechanismech Djanga.

Základní skupiny:

- Čtenář,
- Editor,
- Správce.

Nepřihlášený návštěvník není databázová role.

Django Groups a Permissions budou doplněny zvláštními oprávněními například pro:

- zdravotní údaje,
- omezené záznamy,
- správu přístupových úrovní,
- archivaci a obnovu,
- exporty,
- systémové číselníky,
- citlivý audit.

Volitelné propojení účtu s evidovanou osobou vznikne v samostatném profilu až po vytvoření modelu Osoba.

Výsledný přístup se posuzuje podle nejpřísnějšího omezení objektu, propojení, přílohy nebo zdroje a zvláštních oprávnění uživatele.

Permission základ M2.5h-1 přidává modelová oprávnění:

- `accounts.view_restricted_content`,
- `accounts.view_admin_only_content`,
- `people.view_archived_person`,
- `people.view_deleted_person`.

Skupiny Čtenář a Editor nezískávají žádné z těchto zvýšených oprávnění
automaticky. Skupina Správce získává všechna čtyři, ale nikoli automaticky
ostatní modelová oprávnění, `is_staff` nebo `is_superuser`.

Obecné API je:

```python
def can_view_access_level(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    access_level: str,
) -> bool:
    ...
```

Helper ověřuje aktuální databázový stav autentizovaného actora. `public`
vidí každý; `authenticated` aktivní existující přihlášený uživatel;
`restricted` a `admin_only` vyžadují příslušnou permission nebo aktivního
superusera. Neaktivní actor se posuzuje jako anonymní a `is_staff` přístup
nerozšiřuje. Neplatný actor používá `actor_invalid`, chybějící autentizovaný
actor `actor_unsaved` a neznámá úroveň `invalid_access_level`.

Migrační graf obsahuje nezávislé strukturální migrace `accounts.0002` a
`people.0009` a následnou datovou `accounts.0003` závislou na obou; pořadí
obou strukturálních větví proto není významové. Datová migrace sama
bezpečně vytváří potřebné `Permission` a `Group` řádky a
přiřazuje zvýšená oprávnění pouze Správci. Reverse pouze odebere tato čtyři
oprávnění ze tří systémových skupin; skupiny, permissions ani členství
uživatelů nemaže. Autorizovaný relationship selector M2.5h-2 tato
oprávnění používá bez další změny permission katalogu.

## 15. Audit

Audit má dvě úrovně:

- `AuditOperation` — jedna uživatelská nebo systémová operace,
- `AuditFieldChange` — jednotlivé změněné pole.

Auditní operace uchovává:

- původce,
- čas,
- druh operace,
- typ a ID objektu,
- orientační název objektu,
- komentář,
- přístupovou úroveň,
- identifikátor požadavku,
- technický kontext.

Audit používá generickou identifikaci objektu, protože jde o historický záznam, nikoli aktivní obchodní vazbu.

Citlivé údaje zůstávají chráněné i v auditu. Hesla, tokeny a obsah souborů se do auditu neukládají.

Běžné prohlížení stránek se v první verzi neaudituje. Auditují se změny, exporty, stažení citlivých příloh a správní operace.

## 16. Rozdělení validace

### Databáze

Databáze hlídá zejména:

- povinné hodnoty,
- cizí klíče,
- unikátní kódy,
- jednoduché `CheckConstraint`,
- přesné aktivní duplicity,
- zákaz vazby osoby sama na sebe,
- jednu aktivní hlavní fotografii,
- jedinečnou účast osoby ve stejné roli na stejné události.

### Model a formulář

Modelová validace hlídá zejména:

- alespoň jméno nebo příjmení,
- strukturu neúplného data,
- souřadnice,
- hierarchii místa,
- povinný lokalizační údaj bydliště,
- název nebo popis zdravotního záznamu,
- vhodnost hlavní fotografie.

### Doménová služba

Servisní vrstva řeší pravidla přes více objektů:

- vytvoření a změnu události s účastníky,
- narození, úmrtí a sňatek,
- rodičovské cykly,
- symetrické vazby,
- hlavní fotografii,
- přílohy a zdroje,
- archivaci a obnovu,
- oprávnění,
- audit celé operace.

Pro účastníky události služba ověří aktivní `AllowedEventRole`, aktivitu
`ParticipantRole`, minimální a maximální počet a úplnost povinných rolí
nad celou sadou účastníků. Model `EventParticipant` tuto měnitelnou
konfiguraci dynamicky nekontroluje.

Významné zápisy probíhají v `transaction.atomic()`.

## 17. Selektory a výkon

Složitější čtecí dotazy budou soustředěny v modulech `selectors.py`, například:

- seznam osob,
- detail osoby,
- časová osa,
- skupiny vztahů,
- materiály osoby.

Selektory zajišťují filtrování odstraněných záznamů, kontrolu viditelnosti a optimalizované `select_related()` a `prefetch_related()`.

Prioritní indexy podporují:

- normalizované jméno a příjmení,
- kategorii a stav osoby,
- účast osoby v narození a úmrtí,
- časové osy podle osoby a `sort_date`,
- obě strany vazby,
- hlavní fotografii,
- kontrolní součet souboru,
- archivní identifikaci zdroje,
- historii konkrétního objektu.

Počty záznamů, věk, stav osoby, římská číslice a další agregace se zatím počítají za běhu.

RC 0.1 realizuje tento výpočet autorizovaným
`get_visible_person_presentations(*, actor, as_of=None)`. Selector vrací
neměnné `PersonPresentation` a `PersonDerivedFacts`, načítá pouze běžně
viditelné osoby a jejich viditelné, nearchivované a měkce neodstraněné
události s konzistentní dvojicí `birth` + `born_person` nebo `death` +
`deceased_person`. Skryté zdroje podle ACP-007 neovlivní žádný výstup.

Datum se formátuje z uložených částečných komponent, nikoli z technických mezí
jako z falešně přesného faktu. Věk se zobrazí jen tehdy, když všechny možné
kombinace viditelných mezí dávají stejný nezáporný celý věk. Při více
viditelných narozeních nebo úmrtích selector náhodně nevybírá jeden záznam.
Římské pořadí používá přesně shodnou uloženou dvojici hlavních jmen, známá
narození řadí podle technických mezí a PK, neznámá až za nimi a pracuje jen
s actorovi viditelnou kohortou. Modely ani migrace se tím nemění.

## 18. Pořadí migrací

Skutečné pořadí dosavadních implementovaných migrací je:

```text
accounts.0001_initial
people.0001_person_category
people.0002_initial_person_categories
people.0003_person
people.0004_name_type_person_name
people.0005_initial_name_types
places.0001_place_type
places.0002_place
events.0001_event_type
events.0002_initial_event_types
events.0003_participant_role_allowed_event_role
events.0004_initial_participant_roles
events.0005_initial_allowed_event_roles
events.0006_event
events.0007_event_participant
events.0008_deathdetail
people.0006_relationship_type
people.0007_initial_relationship_types
people.0008_relationship
people.0009_alter_person_options
people.0010_person_titles_biography
accounts.0002_alter_user_options
accounts.0003_initial_permission_groups
places.0003_residence_type
places.0004_initial_residence_types
places.0005_residence
places.0006_grave_site_lookups
places.0007_initial_grave_site_lookups
places.0008_gravesite
places.0009_persongravesite
materials.0001_attachment_lookups
materials.0002_attachments
materials.0003_attachment_links
materials.0004_source_lookups
materials.0005_sources
materials.0006_source_links
accounts.0004_person_editor_permissions
health.0001_health_record_types
health.0002_health_records
materials.0007_health_record_attachment
materials.0008_health_record_source
```

Následující plánované migrace začínají:

```text
audit.0001_initial
accounts.0005_user_profile_person_link
```

Datové migrace základních číselníků budou malé a rozdělené podle aplikací.
`PersonGraveSite` vzniká v samostatné strukturální migraci po hlavním
objektu M2.7b.

## 19. Hlavní technická rizika

1. Podmíněná unikátní omezení je nutné ověřit proti zvolené verzi Djanga a SQLite.
2. Model obsahuje mnoho číselníků; běžný editor je nebude spravovat a systémové hodnoty vzniknou datovou migrací.
3. Explicitní propojení příloh a zdrojů znamená více tabulek, ale zachovává referenční integritu.
4. Validace přes více objektů nesmí být rozptýlena ve views ani pouze v metodách `save()`.
5. Přímý přístup k fyzickým souborům nesmí obejít kontrolu oprávnění.
6. Audit nesmí vytvořit vedlejší únik citlivých údajů.

Žádné z těchto rizik nevyžaduje změnu schválených ACP.

## 20. Kritéria připravenosti k implementaci

Návrh je připraven k implementaci, protože:

- entity mají jasnou odpovědnost,
- kardinality a povinnosti jsou určeny,
- odvozené hodnoty se zbytečně neukládají,
- přílohy a zdroje jsou znovu použitelné,
- neúplná data jsou strukturovaná bez falešné přesnosti,
- integrita je rozdělena mezi databázi, modely a služby,
- hlavní indexy jsou známé,
- oprávnění, archivace a audit jsou součástí návrhu,
- existuje ER diagram,
- návrh prošel architektonickou revizí,
- otevřené otázky neblokují první migraci.
