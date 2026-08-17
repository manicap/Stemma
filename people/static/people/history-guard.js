(function () {
  const indexKey = "stemmaHistoryIndex";
  const originalPushState = window.history.pushState.bind(window.history);
  const originalReplaceState = window.history.replaceState.bind(window.history);
  const stateIndex = (state) => (
    state && Number.isInteger(state[indexKey]) ? state[indexKey] : null
  );
  const indexedState = (state, index) => ({
    ...(state && typeof state === "object" ? state : {}),
    [indexKey]: index,
  });
  let currentIndex = stateIndex(window.history.state) ?? 0;
  let currentNavigationIndex = window.navigation?.currentEntry?.index ?? null;
  let restoringEditEntry = false;
  let pendingTargetUrl = null;

  originalReplaceState(
    indexedState(window.history.state, currentIndex),
    "",
    window.location.href,
  );
  window.history.pushState = (state, title, url) => {
    const nextIndex = currentIndex + 1;
    const result = originalPushState(indexedState(state, nextIndex), title, url);
    currentIndex = nextIndex;
    currentNavigationIndex = window.navigation?.currentEntry?.index ?? null;
    return result;
  };
  window.history.replaceState = (state, title, url) => originalReplaceState(
    indexedState(state, currentIndex),
    title,
    url,
  );

  window.addEventListener("popstate", (event) => {
    const previousIndex = currentIndex;
    const targetIndex = stateIndex(event.state);
    const previousNavigationIndex = currentNavigationIndex;
    const targetNavigationIndex = window.navigation?.currentEntry?.index ?? null;
    if (targetIndex !== null) currentIndex = targetIndex;
    currentNavigationIndex = targetNavigationIndex;

    if (restoringEditEntry) {
      event.stopImmediatePropagation();
      restoringEditEntry = false;
      window.dispatchEvent(new CustomEvent("stemma:confirm-history-discard", {
        detail: { targetUrl: pendingTargetUrl },
      }));
      pendingTargetUrl = null;
      return;
    }

    const form = document.querySelector('[data-person-form][data-dirty="true"]');
    if (!form) return;
    const restoreDelta = targetIndex !== null
      ? previousIndex - targetIndex
      : previousNavigationIndex - targetNavigationIndex;
    if (!Number.isInteger(restoreDelta) || restoreDelta === 0) return;
    event.stopImmediatePropagation();
    pendingTargetUrl = window.location.href;
    restoringEditEntry = true;
    window.history.go(restoreDelta);
  });
}());
