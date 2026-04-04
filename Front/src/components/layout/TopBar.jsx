import SignalLogo from "../common/SignalLogo";

export default function TopBar({
  selectedRegion,
  searchQuery,
  onSearchChange,
  onClearSearch,
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

      <div className="topbar-search">
        <input
          type="search"
          value={searchQuery}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={
            isRu
              ? "Поиск по темам, муниципалитетам и источникам"
              : "Search by topics, municipalities and sources"
          }
          aria-label={isRu ? "Поиск" : "Search"}
        />
        {searchQuery && (
          <button
            type="button"
            className="icon-button clear-search"
            onClick={onClearSearch}
            aria-label={isRu ? "Очистить поиск" : "Clear search"}
          >
            ✕
          </button>
        )}
      </div>
    </header>
  );
}
