# Rozhodnutí a otevřené otázky

**Dokument:** 06  
**Verze:** 0.27
**Stav:** průběžně doplňovaný dokument  
**Datum revize:** 22. 7. 2026

## 1. Přijatá rozhodnutí

Rozhodnutí 1–70 z verze 0.5 zůstávají v platnosti.

### Databázová etapa

71. Logický databázový návrh je uzavřen jako schválený pracovní základ.
72. Pohlaví osoby má hodnoty muž, žena a neznámé.
73. Hlavní jméno a příjmení zůstávají přímo na osobě; další, historická a alternativní jména se ukládají samostatně.
74. Neúplné a nejisté datum používá společný strukturovaný model bez falešných hodnot typu 1. 1. daného roku.
75. Technický řadicí bod data se může ukládat jako automaticky odvozená hodnota kvůli indexům a řazení.
76. Typy událostí a role účastníků jsou spravovatelné číselníky. `AllowedEventRole` konfiguruje pro jedinečnou dvojici typu a role minimální a maximální počet, pořadí, aktivitu a systémový příznak. Neomezené maximum se ukládá jako `NULL`; manželský partner používá jedinou genderově neutrální roli `spouse`.
77. Událost může být propojena s více přílohami, například se snímkem matriky, a s více zdroji.
78. Příčina a okolnosti úmrtí se ukládají ve specializovaném detailu události úmrtí.
79. Jedna osoba smí mít nejvýše jednu aktivní událost narození a jednu aktivní událost úmrtí prostřednictvím systémové role účastníka.
80. Symetrické vazby se ukládají v normalizovaném pořadí; směrové vazby zachovávají význam osob A a B.
81. Biologické sourozenectví se primárně odvozuje ze společných biologických rodičů a běžně se neukládá.
82. Genealogicky nemožné vazby jsou tvrdé chyby; nepravděpodobné nebo rozporné údaje vyvolávají varování.
83. Místo je znovu použitelný objekt; detailní adresa může zůstat u konkrétního bydliště nebo události.
84. Bydliště, pohřební událost a hrobové místo jsou rozdílné skutečnosti.
85. Jedna osoba může být spojena s více hrobovými nebo pamětními místy a jedno hrobové místo s více osobami.
86. Přílohy a zdroje používají explicitní spojovací tabulky, nikoli generické Django vztahy.
87. Hlavní fotografie osoby je role spojení Osoba–Příloha; osoba nemá druhý přímý odkaz na soubor.
88. Zdroj a příloha jsou rozdílné objekty: zdroj popisuje původ informace, příloha konkrétní digitální soubor.
89. Zdroje se v první verzi vážou ke strukturovaným záznamům, nikoli univerzálně ke každému poli.
90. Zdravotní záznam je samostatná entita a zdravotní skutečnost se neukládá současně jako obecná událost.
91. Významný zdravotní záznam se může zobrazit v obecné časové ose bez vytvoření kopie.
92. Přístupová úroveň je pevný výčet: veřejné, pouze přihlášení, omezené, pouze správce.
93. Základní role se realizují prostřednictvím Django Groups a konkrétní oprávnění prostřednictvím Django Permissions.
94. Hlavní entity rozlišují archivaci a měkké odstranění; číselníky používají aktivitu a systémový příznak.
95. Audit eviduje jednu operaci a její jednotlivé změny polí.
96. Audit používá generickou identifikaci typu a ID objektu; obchodní vazby nadále používají skutečné cizí klíče.
97. Významné zápisy se provádějí prostřednictvím transakčních doménových služeb, nikoli sérií přímých volání `save()` ve views.
98. Složitější čtecí dotazy a optimalizace se soustředí v selektorech.
99. Django projekt bude rozdělen na aplikace `accounts`, `common`, `people`, `places`, `events`, `materials`, `health` a `audit`.
100. Vlastní uživatelský model vznikne v první migraci; volitelné propojení účtu s osobou až v pozdější migraci.
101. Databázová etapa neodhalila potřebu nového ACP.
102. Databázový návrh je připraven k implementaci Django modelů, migrací a testů integrity.

### Zahájení implementace MVP

103. Podporovaným základem implementace je Python 3.14 a Django 5.2 LTS.
104. Milník M0 byl ověřen s Pythonem 3.14.6, Django 5.2.16 a SQLite 3.50.4.
105. Vývojové prostředí používá standardní `venv` a `pip`; přímé závislosti se evidují v `requirements.txt`.
106. Konfigurační balíček Django projektu se jmenuje `config` a doménové aplikace jsou umístěny přímo v kořeni repozitáře.
107. Vlastní uživatelský model `accounts.User` založený na `AbstractUser` vznikl v migraci `accounts.0001_initial` před prvním provozním použitím databáze.
108. Lokální `SECRET_KEY`, `DEBUG` a `ALLOWED_HOSTS` jsou uloženy v ignorovaném souboru `config/settings_local.py`; v repozitáři je pouze vzor.
109. Implementace MVP probíhá ve větvi `feature/mvp`.
110. Dokončení M0 nevyžaduje nové ACP; jde o realizaci a konkretizaci ACP-001, ACP-004 a schváleného databázového návrhu.
111. Aplikace `common` je společným technickým základem a nevlastní obchodní entity.
112. V M1 bylo implementováno pět aktuálně potřebných pevných výčtů: pohlaví, přístupová úroveň, stav ověření, přesnost data a kvalifikátor data; další systémové výčty vzniknou v příslušných doménových milnících.
113. Společná pole poskytují abstraktní modely `TimestampedModel`, `AuthoredModel`, `AccessControlledModel`, `VerifiableModel`, `LifecycleModel`, `PartialDateModel` a `LookupModel`.
114. Neúplné datum se validuje společnou čistou logikou; historické části data zůstávají zdrojem pravdy a `sort_date` a `sort_date_end` jsou pouze automaticky odvozené technické meze.
115. Přímé `save()` nevolá `full_clean()`; validaci zajišťují formuláře, explicitní `full_clean()` nebo doménové služby, zatímco uložení pouze přepočítá technické řadicí hodnoty.
116. Milník M1 je dokončen bez nové projektové migrace a bez potřeby nového ACP. Následujícím krokem je M2 – jádro Osoba, Místo, Událost a Vazba.
117. `EventType.default_access_level` a `EventType.default_show_in_overview` jsou snapshotové návrhy pro novou událost. Budoucí doménová služba je při založení zkopíruje, pokud uživatel neuvede vlastní hodnotu; změna typu ani jeho defaultů existující `Event` zpětně nepřepisuje. Model, `clean()` ani `save()` tuto automatizaci neprovádějí.
118. `EventParticipant` je minimalistický spojovací model bez common mixinů a s jedinečnou trojicí událost, osoba a role. Aktuální `AllowedEventRole`, aktivita role a minimální či maximální počty se kontrolují při vytvoření nebo změně účasti v budoucí transakční doménové službě; model je dynamicky nekontroluje a změna konfigurace sama zpětně nezneplatňuje historické účasti.
119. Účastníci jedné události se mění atomickou náhradou celé sady pomocí `replace_event_participants()`. Aktivita a povolenost rolí, duplicity a `max_count` se kontrolují při každé změně; `min_count` pouze při `require_complete=True`. Nová výsledná sada se striktně ověřuje proti aktuální konfiguraci bez grandfatheringu, ale samotná změna konfigurace existující historické účasti automaticky nemění ani nemaže.
120. `RelationshipType` je uživatelsky rozšiřitelný číselník odvozený pouze z `LookupModel`; kategorie vztahů jsou pevný doménový výčet. Uložený směr A → B popisuje osobu B podle jejího genderu a opačný směr osobu A podle jejího genderu. Symetrický typ vyžaduje shodu všech genderových názvů obou směrů. `supports_date_range` pouze povoluje přesnost `RANGE` budoucí konkrétní vazby a `is_derivable` samo nic neodvozuje. V první sadě čtrnácti systémových typů je odvoditelné pouze biologické sourozenectví. Konkrétní `Relationship`, normalizace dvojice osob a algoritmus odvození vzniknou v dalších krocích M2.5. Tato konkretizace nevyžaduje nové ACP.
121. Jeden `Relationship` představuje jedno souvislé období vztahu a používá úplný `PartialDateModel`. Stejné osoby mohou mít více období stejného typu. U symetrického typu je kanonické pořadí podle PK `person_a_id < person_b_id`; model je pouze validuje a budoucí služba bude vstup normalizovat. Vztah osoby k sobě zakazuje model i databáze. Aktivní unikátnost znamená `deleted_at IS NULL`: archivovaný záznam zůstává součástí unikátnosti, měkce odstraněný nikoli. Zvláštní podmíněné constrainty rozlišují neznámý a známý čas. Odvoditelný typ lze explicitně uložit. M2.5b neřeší grafové cykly, překryvy období ani automatické vztahy z událostí a nevyžaduje nové ACP.
122. Veřejné vytvoření a změnu jednotlivého `Relationship` zajišťují `create_relationship()` a `update_relationship()` v `people/services.py` nad frozen dataclass `RelationshipInput`. Služba používá aktuální databázový stav, `transaction.atomic()`, při update `select_for_update()`, normalizaci symetrických osob podle PK a `full_clean()`. Create může nastavit `created_by`, update autora ani lifecycle pole nemění. Neaktivní typ nelze použít pro nový vztah ani na něj přejít; stávající neaktivní typ lze zachovat. Archivovaný vztah lze upravit, měkce odstraněný nikoli. Potvrzený souběžný konflikt se převádí na `duplicate_relationship`, ostatní `IntegrityError` se nemaskují. M2.5c nevytváří migraci ani nové ACP a neřeší cykly, překryvy či odvozování vztahů.
123. Rodičovský graf M2.5d tvoří společně kódy `biological_parent`, `adoptive_parent`, `step_parent` a `foster_parent`; `guardian` patří do péče a poručenství a do grafu nevstupuje. Hrana vede od `person_a` k `person_b`. Zahrnují se všechny vztahy s `deleted_at IS NULL` bez ohledu na archivaci, aktivitu typu a časové vymezení. Navrhovaná hrana A → B je neplatná pouze při existující cestě B → A. Update vylučuje vlastní řádek a validuje výsledný stav, takže může starší cyklus odstranit a nesouvisející nekonzistence jinde změnu neblokuje. Chyba používá `person_b` a kód `relationship_parent_cycle`. Kontrola je transakční servisní pravidlo bez modelové změny, migrace nebo nového ACP; zámky SQLite ani běžné řádkové zámky neposkytují absolutní ochranu proti všem souběžným phantom scénářům.
124. `get_biological_siblings(*, person)` v `people/selectors.py` odvozuje lazy `QuerySet[Person]` pouze z měkce neodstraněných vztahů `biological_parent` ke společnému rodiči; jeden společný rodič stačí a plní či poloviční sourozenci se nerozlišují. Archivace, aktivita typu ani čas rodičovského vztahu se neposuzují. Archivovaná výsledná osoba se zahrne, měkce odstraněná nikoli; vstup může být archivovaný i měkce odstraněný, ale musí mít existující řádek, jinak vznikne `person_unsaved`. Explicitní sourozenecké vztahy se neslučují. Selector nic nezapisuje, zachovává pořadí `Person` a neřeší oprávnění; vyšší aplikační vrstva musí před zveřejněním výsledku vynutit `access_level` a viditelnost. M2.5e nemění modely, migrace ani ACP.
125. `get_sibling_overview(*, person)` vrací tuple frozen slotted položek `SiblingOverviewItem(person, relationship_codes)` a seskupuje každou osobu podle PK. Zachovává všechny důvody v pořadí `biological`, `sibling`, `adoptive_sibling`, `step_sibling`, `social_sibling`; první kód je odvozený, ostatní jsou explicitní typy vztahů vyhodnocené na obou stranách. Zahrnují se měkce neodstraněné vztahy bez ohledu na archivaci, aktivitu typu a čas a měkce neodstraněné výsledné osoby bez ohledu na archivaci. Výsledek se řadí podle příjmení, jména a PK a vzniká třemi konstantními dotazy bez N+1. Selector nic neukládá ani neřeší oprávnění; vyšší vrstva musí filtrovat osoby i explicitní důvody. M2.5f nemění modely, migrace ani ACP.
126. `get_relationship_overview(*, person)` poskytuje celkový permissionless read model vztahů osoby jako tuple frozen slotted položek `RelationshipOverviewItem(person, reasons)`. Každý `RelationshipOverviewReason(category, relationship_code, label, relationship_ids, is_derived)` zachovává vlastní kategorii, směrový genderovaný název a provenance všech sloučených explicitních období. Biologický sourozenec používá kód `biological`, genderovaný český název, prázdná ID a příznak odvození. Přehled zahrnuje všechny systémové i uživatelské typy, seskupuje podle druhé osoby, používá stabilní pořadí kategorií, důvodů a osob a konstantní pětidotazový profil bez N+1. Zahrnuje měkce neodstraněné vztahy bez ohledu na archivaci, aktivitu typu a čas a vylučuje měkce odstraněné výsledné osoby. Selector nic nezapisuje ani neřeší oprávnění; vyšší vrstva musí filtrovat osoby, explicitní vztahy podle `relationship_ids` i biologicky odvozený důvod. M2.5g nemění modely, systémová data, migrace ani ACP.
127. Permission základ M2.5h-1 určuje přesný význam čtyř `AccessLevel` a zavádí obecný helper `can_view_access_level(*, actor, access_level)`. `public` vidí každý, `authenticated` pouze aktivní existující přihlášený uživatel, `restricted` vyžaduje `accounts.view_restricted_content` a `admin_only` `accounts.view_admin_only_content`; aktivní superuser má plný přístup a `is_staff` sám nestačí. Neaktivní actor se posuzuje jako anonymní. Model `Person` deklaruje `people.view_archived_person` a `people.view_deleted_person`. Datová migrace vytváří skupiny Čtenář, Editor a Správce; pouze Správce získává všechna čtyři nová zvýšená oprávnění, nikoli ostatní modelová práva nebo uživatelské příznaky. M2.5h-1 nemění pole modelů ani neimplementuje autorizovaný přehled vztahů; ten následuje v M2.5h-2. Konkretizace používá schválené Django Groups a Permissions a nevyžaduje ACP.
128. `get_visible_relationship_overview(*, person, actor)` je autorizovaná čtecí vrstva nad nezměněným permissionless M2.5g. Ověřuje aktuálního actora a vstupní osobu, kombinuje `access_level` s lifecycle oprávněními, tiše odstraňuje neviditelné výsledné osoby a z explicitních důvodů zachovává pouze viditelná měkce neodstraněná `relationship_ids`. Biologický důvod vyžaduje kompletní viditelnou cestu přes jednoho stejného společného rodiče a dvě orientované hrany `biological_parent`; měkce odstraněný rodič ani hrana se nepoužijí. Pořadí a frozen read model M2.5g se nemění, dotazy jsou dávkové bez N+1 a krok nic nezapisuje, nemění modely, systémová data ani migrace a nevyžaduje ACP.
129. Blok M2.6 začíná rozšiřitelným číselníkem `places.ResidenceType`, který přímo dědí z `LookupModel` a nepřidává vlastní pole. Systémové kódy jsou `primary_residence`, `temporary_residence`, `official_residence`, `institutional_residence` a `other`; uživatelské typy jsou povolené. Hlavní bydliště znamená faktické obvyklé bydliště, úřední bydliště administrativně evidovanou adresu a kódy `permanent` ani `permanent_residence` se nepoužívají. Při kolizi systémového kódu s uživatelským záznamem datová migrace selže před prvním zápisem; reverse odstraní pouze schválené kódy, které jsou stále systémové. M2.6a používá oddělené migrace `places.0003` a `places.0004`, neimplementuje `Residence` a nevyžaduje ACP.
130. Jeden `places.Residence` představuje jeden souvislý pobyt povinné osoby a povinného uživatelsky rozšiřitelného typu. Volitelné strukturované místo a textový detail `address_text` délky 500 lze použít samostatně i současně, ale alespoň jedna lokalizace musí být neprázdná. Všechny tři vazby používají `PROTECT`. Historický čas poskytuje úplný `PartialDateModel`; lifecycle časy jej nenahrazují. Model dále dědí timestamp, access, verification a author metadata, toleruje neaktivní typ, nemá vlastní unikátnost ani dodatečné indexy a řadí podle osoby, technických mezí data, pořadí typu a PK. M2.6b vytváří pouze strukturální `places.0005_residence`; služby, selectory a oprávněné čtení následují později a konkretizace nevyžaduje ACP.
131. Veřejné zápisové API bydlišť tvoří frozen slotted úplný snapshot `ResidenceInput` a keyword-only služby `create_residence()` a `update_residence()` v `places/services.py`. Update může opravit osobu, typ i místo, ale nemění `created_by` ani lifecycle. Služby načítají čerstvý databázový stav všech FK, textová pole stripují, používají `transaction.atomic()`, `full_clean()` před `save()` a při update `select_for_update()` nad Residence. Nový záznam ani přechod nesmí použít neaktivní typ, stejný neaktivní typ lze zachovat. Archivovaný Residence lze upravit, měkce odstraněný nikoli; lifecycle existující osoby a místa se na této permissionless zápisové vrstvě nefiltruje. Služba nededuplikuje ani nemapuje obecný `IntegrityError`. M2.6c nemění model, migrace nebo permission policy, neimplementuje selectory a nevyžaduje ACP.
132. Permissionless `get_person_residences(*, person)` v `places/selectors.py` vrací lazy `QuerySet[Residence]` úplné historie jedné existující osoby. Zahrnuje archivované, neveřejné, historické a budoucí Residence i neaktivní nebo uživatelské typy, ale vylučuje `deleted_at IS NOT NULL`. Vstupní osoba může být archivovaná i měkce odstraněná; neuložená nebo fyzicky chybějící používá `person_unsaved`. Výsledek se bez zvláštního NULL pravidla řadí podle `sort_date`, `sort_date_end`, pořadí a názvu typu a PK. `select_related()` pro osobu, typ, místo a autora drží profil na jednom validačním `exists()` a jednom lazy SELECT bez N+1. Selector neřeší access ani permissions a nesmí být přímo veřejně použit; autorizovaná vrstva následuje v M2.6e. M2.6d nemění modely, služby, migrace ani ACP.
133. `get_visible_person_residences(*, person, actor)` je autorizovaná lazy `QuerySet[Residence]` vrstva nad nezměněným M2.6d. Přes centrální `can_view_access_level()` ověřuje aktuálního actora a podle čerstvého databázového stavu vstupní osoby kombinuje její `access_level` s `people.view_archived_person` a `people.view_deleted_person`; neviditelný vstup odmítá obecnou `PermissionDenied`. Výsledek databázově filtruje pouze podle povolených `AccessLevel`, zachovává archivované a vylučuje měkce odstraněné Residence, nezavádí vlastní Residence lifecycle permission ani policy pro Place a nemění typ, ověření či historickou platnost. Zachovává řazení, `select_related()`, lazy vyhodnocení a konstantní dotazový profil bez N+1. M2.6e nic nezapisuje, nemění modely, služby, systémová data ani migrace a nevyžaduje ACP.
134. M2.7a potvrzuje budoucí modely `GraveSite` a `PersonGraveSite`, ale implementuje jen pevný `GraveSiteStatus(existing, destroyed, unknown)` a rozšiřitelné přímé `LookupModel` katalogy `GraveSiteType` a `PersonGraveSiteRole`. Typy jsou `grave`, `tomb`, `urn_site`, `ossuary`, `scattering_place`, `memorial`, `cenotaph`, `other`; role `buried`, `urn_placed`, `ashes_scattered`, `commemorated`, `remains_relocated_from`, `remains_relocated_to`, `other`. Kenotaf je typ objektu a `commemorated` role osoby. Přemístění není status a směrové role zatím nejsou automaticky párovány. Fyzický status je nezávislý na `VerificationStatus` i `LifecycleModel`; `destroyed` samo nemění archivaci, soft delete ani ověření. Strukturální migrace `places.0006_grave_site_lookups` a datová `places.0007_initial_grave_site_lookups` používají společnou předzápisovou kontrolu kolizí obou katalogů a bezpečný reverse. Hlavní objekt ani vazba, služby, selectory a permissions nevznikají a konkretizace nevyžaduje ACP.

## 2. Otevřené otázky

### Implementace a provoz

- Kde budou fyzicky ukládány fotografie a dokumenty v prvním nasazení?
- Kde bude aplikace nasazena?
- Jak bude řešeno zálohování databáze a souborů?
- Jak bude řešeno verzování a obnova příloh?
- Jak dlouho se bude uchovávat auditní historie?
- Bude podporován offline režim?
- Jaké konkrétní přihlašovací metody budou podporovány?

### Budoucí funkce

- Jak přesně se bude zobrazovat rodokmen?
- Jak bude řešeno slučování duplicit?
- Jaké exportní formáty budou podporovány?
- Bude podporován GEDCOM?
- Zda bude „Příběh nebo vzpomínka“ samostatná entita, nebo typ dokumentu či poznámky.
- Zda bude později zaveden univerzální model tvrzení pro zdrojování jednotlivých polí.

## 3. Uzavřené dřívější otázky

- Podporovaným základem jsou Python 3.14 a Django 5.2 LTS; M0 byl ověřen na Pythonu 3.14.6 a Django 5.2.16.

- Zdravotní záznam je samostatná entita.
- Typy částečných a nejistých dat pro první verzi jsou určeny.
- Základní role jsou Čtenář, Editor a Správce; návštěvník je anonymní uživatel.
- Přílohy a zdroje používají explicitní spojovací modely.
- Audit je na úrovni objektové operace i jednotlivých změněných polí.
- Technický návrh Django aplikací a pořadí migrací jsou určeny.
