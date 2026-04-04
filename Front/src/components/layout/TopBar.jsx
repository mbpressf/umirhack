import SignalLogo from "../common/SignalLogo";

export default function TopBar({
  selectedRegion,
  onToggleSidebar,
  currentSectionLabel,
  locale = "ru",
}) {
  const isRu = locale === "ru";

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

    </header>
  );
}

