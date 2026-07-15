# Návrh UI/UX

**Dokument:** 10  
**Verze:** 0.1  
**Stav:** schválený pracovní základ  
**Datum revize:** 15. 7. 2026

## 1. Účel dokumentu

Tento dokument definuje základní podobu, strukturu a chování uživatelského rozhraní aplikace **Stemma** pro první verzi a interaktivní prototyp.

Stemma není primárně genealogický program. Je to studijní a poznávací nástroj o předcích, doplněný o aktuální členy rodiny a další osoby významné pro rodinný příběh.

## 2. Základní charakter rozhraní

Rozhraní musí být:

- jednoduché a intuitivní na první pohled,
- vizuálně klidné a nepřeplácané,
- domácí a lidské, ale profesionálně zpracované,
- vhodné pro čtení a poznávání osoby, nikoli jen pro správu databázových polí,
- použitelné pro méně technicky zkušené uživatele,
- konzistentní napříč celou aplikací.

Pokročilé funkce nesmějí překážet běžnému prohlížení. Mají se zobrazovat až ve chvíli, kdy jsou potřeba a kdy k nim má uživatel oprávnění.

## 3. Responzivita a dotykové ovládání

Aplikace bude navržena pro:

- počítače,
- tablety,
- mobilní telefony.

Ovládání musí být plnohodnotně použitelné myší i dotykem.

Pravidla:

- tlačítka a klikací plochy budou dostatečně velké,
- mezi ovládacími prvky budou bezpečné rozestupy,
- žádná důležitá funkce nebude dostupná pouze po najetí myší,
- text bude čitelný bez nutnosti přibližování,
- formuláře budou vhodné pro dotykovou klávesnici,
- mobilní zobrazení zachová kontext právě vybrané osoby.

## 4. Designový systém a motivy

Rozhraní bude od začátku připraveno pro změnu vzhledu pomocí designových proměnných a znovu použitelných komponent. Budoucí podrobné nastavení vzhledu bude součástí profilu přihlášeného uživatele, ale v první verzi zůstane neaktivní.

Od první verze budou existovat dva rovnocenné základní motivy:

1. **Stemma světlý**
2. **Stemma tmavý**

Nejde o dvě odlišná rozhraní. Oba motivy používají:

- stejné rozložení,
- stejné komponenty,
- stejné ovládání,
- stejné významy stavů,
- stejné funkční chování.

Liší se pouze vizuálním zpracováním.

Přepínač světlého a tmavého režimu bude dostupný v horní liště i nepřihlášenému uživateli. Volba nepřihlášeného uživatele se uloží lokálně v prohlížeči. Později ji bude možné ukládat i k uživatelskému profilu.

### 4.1 Světlý motiv

Charakter:

- teplý,
- světlý,
- vzdušný,
- klidný,
- připomínající moderní rodinný archiv.

Základní barevné proměnné:

```css
:root,
[data-theme="light"] {
  --color-page: #F5F1E8;
  --color-surface: #FFFCF6;
  --color-surface-muted: #F0EADF;

  --color-text: #243033;
  --color-text-muted: #6E7472;
  --color-border: #DDD5C8;

  --color-primary: #167D7B;
  --color-primary-hover: #106966;
  --color-primary-soft: #D7ECE7;

  --color-male: #3569A8;
  --color-female: #C94F4F;

  --color-success-bg: #E5F2DF;
  --color-success-text: #35602F;
  --color-info-bg: #E2EEF4;
  --color-info-text: #315C70;

  --color-danger: #B64242;
  --color-warning: #B07A2E;
  --color-shadow: rgba(52, 46, 38, 0.12);
}
```

### 4.2 Tmavý motiv

Charakter:

- grafitový,
- elegantní,
- klidný,
- vhodný pro večerní používání,
- bez čisté černé a bez neonových akcentů.

Základní barevné proměnné:

```css
[data-theme="dark"] {
  --color-page: #151B1D;
  --color-surface: #1D2528;
  --color-surface-muted: #252F32;

  --color-text: #EDF1EF;
  --color-text-muted: #A9B2B0;
  --color-border: #374347;

  --color-primary: #35B7AD;
  --color-primary-hover: #48C8BE;
  --color-primary-soft: #234C49;

  --color-male: #6E9ED8;
  --color-female: #E06A6A;

  --color-success-bg: #243B2A;
  --color-success-text: #A9D6A2;
  --color-info-bg: #263B46;
  --color-info-text: #A7CEDF;

  --color-danger: #E06A6A;
  --color-warning: #D6A352;
  --color-shadow: rgba(0, 0, 0, 0.35);
}
```

### 4.3 Použití barev

- Petrolejová je hlavní akcentní barva aplikace.
- Používá se pro hlavní tlačítka, aktivní záložku, vybranou osobu, ikony, odkazy a indikátor načítání.
- Jména mužů uvedená jako druhotné informace nebo odkazy se výchozím způsobem zobrazují modře.
- Jména žen uvedená jako druhotné informace nebo odkazy se výchozím způsobem zobrazují červeně.
- Barevné rozlišení pohlaví se nepoužívá na hlavní jméno osoby v záhlaví.
- Význam chyby, varování nebo zamčení nesmí být vyjádřen pouze barvou; vždy jej doplní text nebo ikona.

## 5. Horní lišta aplikace

Horní lišta bude jednoduchá a nízká.

### Vlevo

- jednoduchý piktogram rozvětveného stromu,
- název **Stemma**,
- kliknutí na název nebo symbol otevře hlavní obrazovku.

### Vpravo

- přepínač světlého a tmavého režimu,
- u nepřihlášeného uživatele tlačítko **Přihlásit se**,
- u přihlášeného uživatele profilové menu,
- budoucí nastavení vzhledu bude součástí profilového menu.

## 6. Hlavní obrazovka

Desktopová hlavní obrazovka používá dvousloupcový model:

- vlevo je seznam osob,
- vpravo je detail vybrané osoby.

Kliknutí na osobu změní detail vpravo bez opuštění hlavní obrazovky.

### Tablet

- zachová se dvousloupcové rozhraní,
- levý seznam bude možné sbalit,
- po sbalení využije detail většinu šířky.

### Telefon

- detail osoby se zobrazuje přes celou obrazovku,
- seznam osob se otevírá jako panel vysunutý zleva,
- panel zabírá přibližně 85 % šířky,
- lze jej zavřít tlačítkem, klepnutím mimo panel nebo gestem,
- po výběru osoby se panel automaticky zavře.

## 7. Seznam osob

### 7.1 Jeden záznam

Každá osoba zabírá přibližně dva textové řádky.

Vlevo:

- malá fotografie nebo výchozí busta přes výšku obou řádků.

Vpravo nahoře:

- jméno,
- příjmení,
- případná automaticky dopočítaná římská číslice.

Vpravo dole:

- datum nebo rok narození,
- datum nebo rok úmrtí, pokud existuje,
- kategorie osoby.

Příklad:

`Jan Novák II.  `  
`12. 3. 1842–6. 8. 1901 · Přímá rodina`

Vybraná osoba bude výrazně označena kombinací jemného podbarvení a barevného akcentu na okraji.

### 7.2 Vyhledávání

Nad seznamem bude vyhledávací pole s našeptávačem.

Vyhledávání pracuje minimálně s:

- jménem,
- příjmením,
- rodným příjmením,
- dalšími jmény,
- přezdívkou,
- rokem narození.

Pokud našeptávač nenajde shodu, zobrazí:

> Nebyla nalezena žádná odpovídající osoba.

Stejná informace se zobrazí také v prostoru seznamu. Editor může navíc vidět akci **+ Přidat novou osobu**.

### 7.3 Filtr kategorie

Pod vyhledáváním bude rozbalovací filtr:

- Všechny osoby,
- Přímá rodina,
- Ostatní rodina,
- Blízcí rodině,
- Duchovní,
- Další související osoby.

Aktivní filtr musí být stále zřetelně viditelný.

### 7.4 Řazení

Rozbalovací nabídka řazení obsahuje:

- Od nejmladších – výchozí,
- Od nejstarších,
- Příjmení A–Z,
- Příjmení Z–A,
- Jméno A–Z,
- Jméno Z–A.

Osoby bez známého data narození se při řazení podle věku zobrazí až za osobami se známým datem.

Vyhledávání, filtr a řazení fungují současně.

### 7.5 Archivované osoby

- Archivované osoby se ve výchozím seznamu nezobrazují.
- Oprávněný uživatel je může zobrazit volbou **Zobrazit archivované osoby**.
- Archivované osoby mají tlumený vzhled a označení **Archivováno**.
- V detailu archivované osoby je dostupná akce **Obnovit osobu**.

## 8. Detail osoby

Detail osoby se skládá z trvale viditelného záhlaví, záložek a obsahu zvolené karty.

### 8.1 Záhlaví osoby

Záhlaví zůstává viditelné při přepínání mezi kartami.

Obsahuje:

- hlavní fotografii nebo výchozí bustu,
- jméno a příjmení,
- případnou římskou číslici,
- kategorii osoby,
- pohlaví,
- věk,
- datum narození,
- datum úmrtí, pokud existuje,
- tlačítka **Zpět** a **Vpřed**,
- tlačítko **Upravit osobu** pro oprávněného uživatele,
- tlačítko pro vytvoření souhrnného **PDF A4**.

Tlačítka Zpět a Vpřed procházejí historii zobrazených osob podobně jako v prohlížeči.

- Pokud v daném směru žádná historie neexistuje, tlačítko je šedé a neaktivní.
- Po otevření další osoby se aktivuje Zpět.
- Po návratu zpět se aktivuje Vpřed.
- Otevření nové osoby po návratu zpět odstraní dosavadní větev historie vpřed.

### 8.2 Souhrnné PDF A4

PDF není snímkem obrazovky. Aplikace vytvoří samostatně formátovaný souhrnný profil osoby optimalizovaný pro A4.

Může obsahovat:

- základní údaje a hlavní fotografii,
- životopisný přehled,
- klíčové události,
- rodinné vztahy,
- vybrané materiály,
- zdroje,
- datum vytvoření dokumentu.

Rozsah může být podle množství dat vícestránkový.

## 9. Záložky detailu osoby

Pod záhlavím jsou hlavní záložky:

1. Přehled
2. Vztahy
3. Události
4. Bydliště
5. Zdraví
6. Materiály

Výchozí záložkou je **Přehled**.

Aktivní záložka bude označena kombinací:

- výraznějšího textu,
- odlišného pozadí,
- barevné spodní linky.

Obsah každé karty bude mít vlastní nadpis a může obsahovat velmi jemný tematický piktogram v pozadí. Piktogram je pouze dekorativní a nesmí rušit text.

## 10. Karta Přehled

Karta Přehled není tabulka. Je to stylizovaný životní profil osoby.

Obsahuje:

- podrobnější informace o narození,
- podrobnější informace o sňatku nebo partnerství,
- podrobnější informace o úmrtí,
- krátký životopisný text,
- klíčové životní události,
- zajímavosti,
- stručný přehled nejbližších rodinných vazeb.

Událost může mít příznak **Zobrazit v přehledu osoby**. Takto označené události se zobrazí mezi klíčovými životními okamžiky.

Životopisný text může být navržen pomocí AI z evidovaných informací. AI:

- pracuje pouze s dostupnými údaji,
- nesmí doplňovat vymyšlená fakta,
- musí respektovat nejistá a neúplná data,
- vytváří pouze návrh,
- výsledný text může uživatel před uložením upravit.

## 11. Karta Vztahy

Vztahy se zobrazují v jednoduchých skupinách:

- rodiče,
- sourozenci,
- partneři,
- děti,
- ostatní vztahy.

U každé propojené osoby se zobrazí pouze:

- jméno a příjmení,
- případná římská číslice,
- rok narození a úmrtí v závorce.

Kliknutí otevře detail vybrané osoby.

Karta nenahrazuje samostatný rodokmen.

## 12. Karta Události

Události se zobrazují jako svislá časová osa seřazená od nejstarší po nejnovější.

Každý záznam obsahuje:

- datum nebo období,
- název události,
- stručný popis.

Kliknutí otevře podrobnosti události.

Oprávněný uživatel vidí tlačítko **+ Přidat událost**. Po kliknutí se přímo v kartě zobrazí malý formulář. Po uložení se událost automaticky zařadí na správné místo časové osy.

## 13. Karta Bydliště

Bydliště se zobrazuje jako svislá chronologická časová osa od nejstaršího po nejnovější.

Každý záznam obsahuje:

- datum nebo období,
- místo nebo adresu,
- krátkou poznámku, pokud existuje.

Oprávněný uživatel může přímo v kartě otevřít mini formulář pomocí tlačítka **+ Přidat bydliště**.

## 14. Karta Zdraví

Karta Zdraví je dostupná pouze uživateli s příslušným oprávněním.

Obsahuje chráněnou chronologickou časovou osu zdravotních záznamů, například:

- vyšetření,
- diagnózy,
- úrazy,
- operace,
- očkování,
- alergie,
- léky,
- dlouhodobé zdravotní stavy,
- tělesné zvláštnosti,
- jiné historicky doložené zdravotní informace.

Příklad historického záznamu:

`1865 — Chybějící prst`  
`Ve vojenském záznamu je uvedeno, že osobě chyběl prst na pravé ruce.`

U dlouhodobého stavu lze uvést období nebo počáteční datum.

## 15. Karta Materiály

Karta Materiály představuje souhrnný pohled na všechny přílohy propojené s osobou.

Přílohy se člení podle kategorií, například:

- Fotografie,
- Dokumenty,
- Události,
- Bydliště,
- Zdraví,
- Ostatní.

Seznam obsahuje:

- kategorii,
- název materiálu,
- krátký popis,
- případně datum.

Po kliknutí se zobrazí:

- samotný materiál nebo jeho náhled,
- podrobný textový popis,
- související záznamy,
- zdroj a další metadata, pokud existují.

Jedna příloha se neukládá duplicitně. V Materiálech se pouze zobrazí ve všech odpovídajících souvislostech.

## 16. Přidání a editace osoby

Oprávněný uživatel vidí nad seznamem tlačítko **+ Přidat osobu**.

Po kliknutí se formulář zobrazí v pravém panelu místo detailu osoby.

Formulář bude vizuálně vycházet ze stejného rozložení jako detail osoby:

- stejné místo pro fotografii nebo bustu,
- pole jména v místě běžného záhlaví,
- stejné rozestupy, typografie a komponenty,
- hlavní akce **Uložit osobu**,
- vedlejší akce **Zrušit**.

Po uložení se nová osoba:

- přidá do seznamu,
- automaticky vybere,
- otevře v detailu,
- získá případnou automaticky dopočítanou římskou číslici.

Tlačítko **Upravit osobu** v záhlaví upravuje základní údaje osoby a záhlaví.

## 17. Editace jednotlivých záznamů

U jednotlivých položek v kartách jsou pro oprávněného uživatele malé ikony:

- Upravit,
- Odstranit.

Před odstraněním se vždy zobrazí potvrzovací dialog.

Jednotlivé záznamy se technicky odstraňují měkce. Celá osoba se nikdy běžně nemaže, ale pouze archivuje.

Archivace osoby:

- je umístěna v méně výrazné doplňkové nabídce,
- vyžaduje potvrzení,
- umožňuje pozdější obnovení.

## 18. Okamžitá aktualizace rozhraní

Po uložení změny se upravené údaje bez ručního obnovení stránky ihned promítnou všude, kde jsou v aktuálním rozhraní zobrazeny.

Příklady:

- změna jména se projeví v záhlaví, seznamu i kartě Vztahy,
- změna data narození se projeví ve věku, seznamu i přehledu,
- změna kategorie se projeví v záhlaví, seznamu a filtrech.

Pro dílčí aktualizace se použije HTMX.

## 19. Oprávnění v UI

Rozhraní zobrazuje jen akce, které může uživatel skutečně provést.

- Nepřihlášený uživatel a čtenář nevidí editační akce.
- Editor vidí přidávání a úpravy v rozsahu svých oprávnění.
- Správce vidí také správní akce, archivaci a obnovu.
- Akce bez oprávnění se většinou vůbec nezobrazují.
- Zamčený obsah může zůstat označen jako existující, ale jeho data se nezobrazí.

## 20. Prázdné stavy

Pokud není vybrána osoba:

> Není vybrána žádná osoba.

Pokud karta neobsahuje data:

> Tato karta zatím neobsahuje žádné údaje.

Editor může v prázdném stavu vidět odpovídající tlačítko pro přidání prvního záznamu.

## 21. Načítání a ukládání

### Načítání

Indikátor načítání je součástí motivu. Ve výchozích motivech jde o kruhovou animaci tvořenou menšími body pohybujícími se po obvodu kruhu.

Indikátor se zobrazuje přímo v oblasti, která se načítá.

### Ukládání

- Během ukládání je potvrzovací tlačítko dočasně neaktivní.
- Zobrazí text **Ukládám…**.
- Po úspěchu se data ihned aktualizují.

## 22. Upozornění a chyby

Důležitá upozornění se nezobrazují pouze jako malá zpráva v rohu. Vždy se zobrazí přímo v místě, kde uživatel pracuje.

Příklady:

- chyba formuláře nad formulářem a současně u konkrétního pole,
- potvrzení uložení v upravené oblasti,
- zamčený obsah místo obsahu příslušné karty,
- chyba načítání v prostoru, kde měl být obsah,
- potvrzení odstranění nebo archivace v dialogu uprostřed obrazovky.

Po úspěšném uložení se zobrazí:

> Změny byly uloženy.

Při chybě ukládání zůstane formulář vyplněný. Chyba může nastat například kvůli:

- neplatným nebo chybějícím údajům,
- nedostatečnému oprávnění,
- konfliktu dat,
- technickému problému nebo výpadku spojení.

## 23. Ochrana neuložených změn

Pokud uživatel opouští rozpracovanou editaci, aplikace zobrazí upozornění:

> Máte neuložené změny. Chcete je zahodit?

Akce:

- **Pokračovat v úpravě**
- **Zahodit změny**

## 24. Vizuální reference

Schváleným výchozím směrem je návrh zobrazující světlý a tmavý režim vedle sebe, včetně hlavní obrazovky, seznamu osob, detailu osoby a základních komponent.

Doporučený soubor reference v projektu:

`docs/references/stemma-light-dark-ui-concept.png`

Reference určuje vizuální směr, nikoli přesné pixelové rozměry všech prvků.

## 25. Otevřené otázky pro další fázi

- Přesná typografická rodina a licenční podmínky fontů.
- Přesné breakpointy pro počítač, tablet a telefon.
- Detailní podoba mini formulářů.
- Detailní návrh dialogů a náhledu materiálů.
- Rozsah první implementace generování PDF A4.
- Rozsah a technické řešení AI návrhu životopisného textu.
- Samostatný návrh rodokmenu a dalších globálních obrazovek.
