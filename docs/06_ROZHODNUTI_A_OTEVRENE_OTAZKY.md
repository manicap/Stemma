# Rozhodnutí a otevřené otázky

**Dokument:** 06  
**Verze:** 0.2  
**Stav:** průběžně doplňovaný dokument  
**Datum revize:** 14. 7. 2026

## 1. Přijatá rozhodnutí

1. Projekt je rodinná databáze a informační systém, ne pouze rodokmen.
2. Backend a frontend budou součástí jednoho projektu.
3. Bez přihlášení je aplikace primárně pouze pro čtení.
4. Hlavní obrazovka má trvale viditelný seznam osob a detail vybrané osoby.
5. Nad seznamem je vyhledávání s našeptávačem.
6. Narození a úmrtí jsou speciální typy událostí.
7. Stav žijící/zemřelý se odvozuje z existence události Úmrtí.
8. Věk se dopočítává automaticky.
9. Událost Úmrtí může obsahovat příčinu úmrtí.
10. Osoby se shodným jménem a příjmením dostávají automatickou římskou číslici podle data narození.
11. Římská číslice se zobrazuje v seznamu i detailu.
12. Vazby mezi osobami jsou univerzální a obousměrné.
13. Opačný význam vazby se dopočítává automaticky.
14. Vazby mohou zahrnovat rodiče, děti, partnery, sourozence, kmotry, pěstouny, nevlastní rodiče, poručníky a vlastní typy.
15. Každá osoba může mít neomezený počet událostí, bydlišť, fotografií, dokumentů a příloh.
16. Každá osoba může mít jednu hlavní fotografii.
17. Pokud hlavní fotografie neexistuje, zobrazí se silueta busty.
18. Fotografie mají název a samostatný popis.
19. Zdravotní informace tvoří samostatnou záložku.
20. Zdravotní záznamy zahrnují i očkování.
21. Zdravotní záznamy jsou ve výchozím stavu omezené.
22. Hrobové místo je samostatná entita, nikoli událost.
23. Jedno hrobové místo může být propojeno s více osobami.
24. Přílohy jsou univerzální a mohou být znovu použity.
25. Štítky nejsou součástí projektu.
26. Záznamy se nemají fyzicky mazat jako výchozí operace.
27. Dokumentace je hlavní zdroj pravdy.
28. Při práci se vychází z nejnovější verze.
29. Asistent připomene aktualizaci dokumentace, když hrozí ztráta kontextu.
30. Asistent kontroluje konzistenci návrhu s dokumentací.
31. Role hlavního architekta projektu se označuje jménem Marcus.
32. Významná změna schválené architektury se řeší formou ACP.
33. Projekt se řídí zásadou „nejdříve návrh, potom implementace“.
34. Hlavním implementačním jazykem bude Python.
35. Webová aplikace bude postavena na frameworku Django.
36. Rozhraní bude primárně serverově renderované.
37. Pro dílčí aktualizace bude použit HTMX.
38. Vlastní JavaScript bude omezen na nezbytné minimum.
39. Aplikace nebude navržena jako SPA.
40. Výchozí databází bude SQLite.
41. PostgreSQL se použije pouze při skutečné provozní potřebě.
42. Oficiální repozitář je https://github.com/manicap/Stemma.
43. Ve zdrojích projektu je pouze aktuální dokumentace.
44. Historii dokumentace uchovává GitHub.
45. Pravidla implementace budou vedena v 09_CODING_STANDARD.md.

## 2. Otevřené otázky

- Kde budou ukládány fotografie a dokumenty?
- Kde bude aplikace nasazena?
- Bude podporován offline režim?
- Jak bude řešeno přihlašování?
- Kolik rolí bude skutečně potřeba v první verzi?
- Jak bude vypadat mobilní panel seznamu osob?
- Jak přesně se bude zobrazovat rodokmen?
- Jak bude řešeno slučování duplicit?
- Jaké exportní formáty budou podporovány?
- Bude podporován GEDCOM?
- Jak bude řešeno zálohování?
- Jak dlouho se bude uchovávat historie změn?
- Jak bude řešeno verzování a obnova příloh?
- Zda bude „Příběh nebo vzpomínka“ samostatná entita, nebo typ dokumentu/poznámky.
- Zda bude zdravotní záznam samostatná entita, nebo specializovaný typ události v technické implementaci.
- Jaké typy částečných a nejistých dat budou podporovány v první verzi.


## 3. Odůvodnění technologického rozhodnutí

Django bylo zvoleno kvůli rychlému vývoji, vestavěné autentizaci a administraci, lehkému serverově renderovanému rozhraní a možnosti používat Python také pro importy, exporty, údržbové skripty a budoucí zpracování dokumentů.

HTMX umožní měnit pouze potřebné části stránky bez velkého javascriptového frameworku. SQLite odpovídá malému počtu uživatelů a převážně čtecímu provozu.
