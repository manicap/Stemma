(function () {
  const root = document.documentElement;
  const storedTheme = window.localStorage.getItem("stemma-theme");
  if (storedTheme === "dark" || storedTheme === "light") {
    root.dataset.theme = storedTheme;
  }

  const themeToggle = document.querySelector("[data-theme-toggle]");
  const updateThemeLabel = () => {
    const isDark = root.dataset.theme === "dark";
    if (!themeToggle) return;
    themeToggle.setAttribute("aria-pressed", String(isDark));
    themeToggle.setAttribute("aria-label", `Přepnout na ${isDark ? "světlý" : "tmavý"} motiv`);
    themeToggle.textContent = isDark ? "Světlý motiv" : "Tmavý motiv";
  };
  updateThemeLabel();

  themeToggle?.addEventListener("click", () => {
    const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = nextTheme;
    window.localStorage.setItem("stemma-theme", nextTheme);
    updateThemeLabel();
  });

  const peoplePanel = document.querySelector("#people-panel");
  const listToggle = document.querySelector("[data-person-list-open]");
  const setListOpen = (isOpen) => {
    peoplePanel?.classList.toggle("is-open", isOpen);
    listToggle?.setAttribute("aria-expanded", String(isOpen));
  };
  setListOpen(peoplePanel?.classList.contains("is-open") ?? false);
  listToggle?.addEventListener("click", () => setListOpen(!peoplePanel?.classList.contains("is-open")));
  document.querySelector("[data-person-list-close]")?.addEventListener("click", () => setListOpen(false));

  const selectCurrentPerson = () => {
    document.querySelectorAll(".person-list-item").forEach((link) => {
      const isCurrent = new URL(link.href).pathname === window.location.pathname;
      link.classList.toggle("is-selected", isCurrent);
      if (isCurrent) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  };
  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail.target.id !== "person-detail") return;
    selectCurrentPerson();
    setListOpen(false);
  });
  const showRequestError = (event) => {
    const detail = event.detail.target;
    if (!(detail instanceof Element) || detail.id !== "person-detail") return;
    if (event.type === "htmx:responseError" && event.detail.xhr.status === 404) {
      detail.innerHTML = event.detail.xhr.responseText;
      return;
    }
    detail.innerHTML = '<div class="detail-empty" role="alert"><h2>Detail se nepodařilo načíst.</h2><p>Zkuste akci zopakovat.</p></div>';
  };
  document.body.addEventListener("htmx:responseError", showRequestError);
  document.body.addEventListener("htmx:sendError", showRequestError);
}());
