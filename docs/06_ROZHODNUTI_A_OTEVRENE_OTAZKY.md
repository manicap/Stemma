# Rozhodnutí a otevřené otázky

**Dokument:** 06  
**Verze:** 0.6  
**Stav:** průběžně doplňovaný dokument  
**Datum revize:** 15. 7. 2026

## 1. Přijatá rozhodnutí

Rozhodnutí 1–70 z verze 0.5 zůstávají v platnosti.

### Databázová etapa

71. Logický databázový návrh je uzavřen jako schválený pracovní základ.
72. Pohlaví osoby má hodnoty muž, žena a neznámé.
73. Hlavní jméno a příjmení zůstávají přímo na osobě; další, historická a alternativní jména se ukládají samostatně.
74. Neúplné a nejisté datum používá společný strukturovaný model bez falešných hodnot typu 1. 1. daného roku.
75. Technický řadicí bod data se může ukládat jako automaticky odvozená hodnota kvůli indexům a řazení.
76. Typy událostí a role účastníků jsou číselníky; povolené role a jejich minimální a maximální počty se konfigurují pro každý typ události.
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

## 2. Otevřené otázky

### Implementace a provoz

- Které konkrétní podporované verze Pythonu a Djanga budou použity?
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

- Zdravotní záznam je samostatná entita.
- Typy částečných a nejistých dat pro první verzi jsou určeny.
- Základní role jsou Čtenář, Editor a Správce; návštěvník je anonymní uživatel.
- Přílohy a zdroje používají explicitní spojovací modely.
- Audit je na úrovni objektové operace i jednotlivých změněných polí.
- Technický návrh Django aplikací a pořadí migrací jsou určeny.
