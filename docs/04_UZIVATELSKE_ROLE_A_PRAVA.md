# Uživatelské role a oprávnění

**Dokument:** 04  
**Verze:** 0.2
**Stav:** pracovní návrh  
**Datum revize:** 22. 7. 2026

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

## 5.1 Systémové skupiny a zvýšená oprávnění

Databázové skupiny jsou `Čtenář`, `Editor` a `Správce`.

- Čtenář automaticky nezískává zvýšená obsahová ani lifecycle oprávnění.
- Editor automaticky nezískává přístup k omezenému nebo
  administrátorskému obsahu.
- Správce získává `accounts.view_restricted_content`,
  `accounts.view_admin_only_content`, `people.view_archived_person` a
  `people.view_deleted_person`.

Správce tím nezískává všechna standardní add/change/delete/view oprávnění,
`is_staff` ani `is_superuser`. Konkrétní permission lze uživateli nebo jiné
schválené skupině přidělit samostatně.

Lifecycle osoby se posuzuje odděleně od její přístupové úrovně. Zobrazení
archivované osoby vyžaduje `people.view_archived_person`; zobrazení měkce
odstraněné osoby vyžaduje `people.view_deleted_person`. Aplikační použití
těchto oprávnění vznikne v M2.5h-2.

## 6. Zamčený obsah

Uživatel bez oprávnění má být informován, že chráněný obsah existuje.

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
