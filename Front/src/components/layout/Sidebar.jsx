import SignalLogo from "../common/SignalLogo";

const ICONS = {
  overview: "M3 12h18M3 6h18M3 18h18",
  assistant: "M5 7h14v8H8l-3 3V7z M9 11h6 M9 14h4",
  top: "M5 18h14M7 18V8m5 10V5m5 13v-7",
  topics: "M4 6h16v12H4z M8 10h8 M8 14h5",
  trends: "M4 16l5-6 4 3 7-8",
  sources: "M5 6h14v12H5z M8 9h8 M8 13h8",
  geography: "M12 3l8 4v10l-8 4-8-4V7l8-4z",
  reports: "M7 3h8l4 4v14H7z M15 3v4h4",
  notebook: "M6 4h12a2 2 0 0 1 2 2v14l-3-2-3 2-3-2-3 2V6a2 2 0 0 1 2-2z",
  profile: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 21a8 8 0 0 1 16 0",
  settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M3 12h3m12 0h3M12 3v3m0 12v3",
  region: "M3 6h18M6 10h12M8 14h8M9 18h6",
};

function SidebarIcon({ sectionId }) {
  const path = ICONS[sectionId] ?? ICONS.overview;
  return (
    <svg
      viewBox="0 0 24 24"
      className="sidebar-icon"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  );
}

export default function Sidebar({
  sections,
  activeSection,
  onSectionChange,
  selectedRegion,
  lastUpdate,
  sidebarOpen,
  onCloseSidebar,
  locale = "ru",
}) {
  const isRu = locale === "ru";

  return (
    <>
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-head">
          <SignalLogo />
          <button
            type="button"
            className="icon-button sidebar-close"
            onClick={onCloseSidebar}
            aria-label={isRu ? "Закрыть меню" : "Close menu"}
          >
            ✕
          </button>
        </div>

        <nav className="sidebar-nav">
          {sections.map((section) => (
            <button
              type="button"
              key={section.id}
              className={`sidebar-link ${activeSection === section.id ? "active" : ""}`}
              onClick={() => {
                onSectionChange(section.id);
                onCloseSidebar();
              }}
            >
              <SidebarIcon sectionId={section.id} />
              <span>{section.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-foot">
          <p>{isRu ? "Текущий регион" : "Current region"}</p>
          <strong>{selectedRegion}</strong>
          <span className="sidebar-update">
            {isRu ? "Обновлено: " : "Updated: "}
            {lastUpdate}
          </span>
        </div>
      </aside>
      <div className={`sidebar-backdrop ${sidebarOpen ? "show" : ""}`} onClick={onCloseSidebar} />
    </>
  );
}

