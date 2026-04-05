import SignalLogo from "../common/SignalLogo";

function formatLiveUpdate(value, locale) {
  if (!value) {
    return locale === "ru" ? "нет данных" : "n/a";
  }
  return value;
}

export default function TopBar({
  selectedRegion,
  onToggleSidebar,
  currentSectionLabel,
  locale = "ru",
  lastUpdate,
  liveState,
  chatStatus,
}) {
  const isRu = locale === "ru";

  const liveLabel = liveState?.error
    ? isRu
      ? "резервный режим"
      : "fallback mode"
    : liveState?.loading
      ? isRu
        ? "обновляем данные"
        : "refreshing"
      : isRu
        ? "live"
        : "live";

  const chatLabel = chatStatus?.provider === "gigachat"
    ? "GigaChat"
    : isRu
      ? "AI fallback"
      : "AI fallback";

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          type="button"
          className="icon-button menu-toggle"
          onClick={onToggleSidebar}
          aria-label={isRu ? "Открыть меню" : "Open menu"}
        >
          ☰
        </button>
        <SignalLogo compact showSub={false} />
        <div className="topbar-context">
          <strong>{currentSectionLabel}</strong>
          <span>{selectedRegion}</span>
        </div>
      </div>

      <div className="topbar-status">
        <div className={`topbar-pill ${liveState?.error ? "warning" : liveState?.loading ? "loading" : "ok"}`}>
          <span>{isRu ? "Данные" : "Data"}</span>
          <strong>{liveLabel}</strong>
        </div>
        <div className="topbar-pill">
          <span>{isRu ? "AI" : "AI"}</span>
          <strong>{chatLabel}</strong>
        </div>
        <div className="topbar-pill topbar-pill-wide">
          <span>{isRu ? "Последнее обновление" : "Last update"}</span>
          <strong>{formatLiveUpdate(lastUpdate, locale)}</strong>
        </div>
      </div>
    </header>
  );
}
