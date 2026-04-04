import { useEffect, useMemo, useState } from "react";
import Sidebar from "./components/layout/Sidebar";
import TopBar from "./components/layout/TopBar";
import TopicModal from "./components/common/TopicModal";
import OverviewPage from "./pages/OverviewPage";
import TopProblemsPage from "./pages/TopProblemsPage";
import TopicsPage from "./pages/TopicsPage";
import TrendsPage from "./pages/TrendsPage";
import SourcesPage from "./pages/SourcesPage";
import GeographyPage from "./pages/GeographyPage";
import ReportsPage from "./pages/ReportsPage";
import ProfilePage from "./pages/ProfilePage";
import SettingsPage from "./pages/SettingsPage";
import RegionPage from "./pages/RegionPage";
import NotebookPage from "./pages/NotebookPage";
import { DEFAULT_SETTINGS, REGION_OPTIONS, SIDEBAR_SECTIONS, getRegionData } from "./data/mockData";
import { fetchFrontendSnapshot } from "./lib/api";

const STORAGE = {
  region: "signal:selected-region",
  settings: "signal:settings",
  history: "signal:region-history",
  notes: "signal:notebook-notes",
};

const DEFAULT_REGION = "Ростовская область";

const safeRead = (key, fallback) => {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    return fallback;
  }
};

const SECTION_LABELS = {
  ru: Object.fromEntries(SIDEBAR_SECTIONS.map((item) => [item.id, item.label])),
  en: {
    overview: "Overview",
    top: "Top Issues",
    topics: "Topics & Events",
    trends: "Trends",
    sources: "Sources",
    geography: "Geography",
    reports: "Reports",
    notebook: "Notebook",
    profile: "Profile",
    settings: "Settings",
    region: "Region",
  },
};

export default function App() {
  const [activeSection, setActiveSection] = useState("overview");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedRegion, setSelectedRegion] = useState(() => safeRead(STORAGE.region, DEFAULT_REGION));
  const [globalSearch, setGlobalSearch] = useState("");
  const [settings, setSettings] = useState(() => {
    const saved = safeRead(STORAGE.settings, DEFAULT_SETTINGS);
    const normalizedTheme =
      saved?.theme === "dark" || saved?.theme === "Тёмная" || saved?.theme === "Темная"
        ? "dark"
        : "light";
    const normalizedLanguage = saved?.language === "en" ? "en" : "ru";
    return {
      ...DEFAULT_SETTINGS,
      ...saved,
      theme: normalizedTheme,
      language: normalizedLanguage,
    };
  });
  const [regionHistory, setRegionHistory] = useState(() => safeRead(STORAGE.history, []));
  const [notes, setNotes] = useState(() => safeRead(STORAGE.notes, []));
  const [modalTopic, setModalTopic] = useState(null);
  const [toast, setToast] = useState("");
  const [liveSnapshot, setLiveSnapshot] = useState(null);
  const [liveState, setLiveState] = useState({ loading: false, error: "" });

  const locale = settings.language === "en" ? "en" : "ru";
  const sectionLabels = SECTION_LABELS[locale] ?? SECTION_LABELS.ru;
  const currentSectionLabel = sectionLabels[activeSection] ?? sectionLabels.overview;

  const data = useMemo(() => {
    if (
      selectedRegion === DEFAULT_REGION &&
      liveSnapshot?.meta?.regionName === DEFAULT_REGION &&
      liveSnapshot?.meta?.dataReady !== false
    ) {
      return liveSnapshot;
    }

    return getRegionData(selectedRegion);
  }, [liveSnapshot, selectedRegion]);

  const localizedSections = useMemo(
    () =>
      SIDEBAR_SECTIONS.map((section) => ({
        ...section,
        label: sectionLabels[section.id] ?? section.label,
      })),
    [sectionLabels],
  );

  const pilotNotice = useMemo(() => {
    if (selectedRegion === DEFAULT_REGION && liveState.error) {
      return locale === "ru"
        ? "Live-данные временно недоступны, поэтому интерфейс показывает резервный набор."
        : "Live data is temporarily unavailable, fallback data is shown.";
    }
    if (selectedRegion === DEFAULT_REGION && liveState.loading) {
      return locale === "ru"
        ? "Подключаем живую аналитику региона..."
        : "Connecting live regional analytics...";
    }
    if (data.meta.pilot) {
      return "";
    }
    return locale === "ru"
      ? `Для региона «${selectedRegion}» пока доступны базовые разделы интерфейса. Полная аналитика подключается.`
      : `Only base sections are available for ${selectedRegion}. Full analytics is being connected.`;
  }, [data.meta.pilot, liveState.error, liveState.loading, locale, selectedRegion]);

  useEffect(() => {
    localStorage.setItem(STORAGE.region, JSON.stringify(selectedRegion));
  }, [selectedRegion]);

  useEffect(() => {
    localStorage.setItem(STORAGE.settings, JSON.stringify(settings));
  }, [settings]);

  useEffect(() => {
    localStorage.setItem(STORAGE.history, JSON.stringify(regionHistory));
  }, [regionHistory]);

  useEffect(() => {
    localStorage.setItem(STORAGE.notes, JSON.stringify(notes));
  }, [notes]);

  useEffect(() => {
    if (selectedRegion !== DEFAULT_REGION) {
      setLiveState({ loading: false, error: "" });
      return undefined;
    }

    const controller = new AbortController();

    setLiveState({ loading: true, error: "" });
    fetchFrontendSnapshot(controller.signal)
      .then((payload) => {
        setLiveSnapshot(payload);
        setLiveState({ loading: false, error: "" });
      })
      .catch((error) => {
        if (error.name === "AbortError") {
          return;
        }
        setLiveState({ loading: false, error: error.message });
      });

    return () => controller.abort();
  }, [selectedRegion]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", settings.theme === "dark" ? "dark" : "light");
  }, [settings.theme]);

  useEffect(() => {
    if (!toast) {
      return undefined;
    }
    const timer = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const showToast = (message) => setToast(message);

  const saveRegion = (regionName) => {
    setSelectedRegion(regionName);
    setRegionHistory((current) =>
      [
        {
          region: regionName,
          date: new Date().toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" }),
        },
        ...current.filter((item) => item.region !== regionName),
      ].slice(0, 8),
    );
  };

  const addNote = ({ topicId, topicTitle, municipality, text, mark }) => {
    const note = {
      id: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      topicId,
      topicTitle,
      region: selectedRegion,
      municipality,
      mark,
      text,
      createdAt: new Date().toLocaleString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }),
    };
    setNotes((current) => [note, ...current]);
    showToast(locale === "ru" ? "Заметка добавлена в блокнот." : "Note added to notebook.");
  };

  const renderSection = () => {
    switch (activeSection) {
      case "overview":
        return (
          <OverviewPage
            data={data}
            globalSearch={globalSearch}
            onOpenTopic={setModalTopic}
            pilotNotice={pilotNotice}
            locale={locale}
          />
        );
      case "top":
        return (
          <TopProblemsPage
            problems={data.topProblems}
            globalSearch={globalSearch}
            onOpenTopic={setModalTopic}
          />
        );
      case "topics":
        return <TopicsPage topics={data.topics} globalSearch={globalSearch} onOpenTopic={setModalTopic} />;
      case "trends":
        return <TrendsPage trends={data.trends} />;
      case "sources":
        return <SourcesPage sources={data.sources} globalSearch={globalSearch} />;
      case "geography":
        return (
          <GeographyPage
            municipalities={data.municipalities}
            topProblems={data.topProblems}
            globalSearch={globalSearch}
            onOpenTopic={setModalTopic}
          />
        );
      case "reports":
        return (
          <ReportsPage
            reportPreview={data.reportPreview}
            topProblems={data.topProblems}
            overviewSummary={data.overviewSummary}
            locale={locale}
          />
        );
      case "notebook":
        return (
          <NotebookPage
            notes={notes}
            onDeleteNote={(id) => {
              setNotes((current) => current.filter((note) => note.id !== id));
              showToast(locale === "ru" ? "Заметка удалена." : "Note removed.");
            }}
            onClearNotes={() => {
              setNotes([]);
              showToast(locale === "ru" ? "Блокнот очищен." : "Notebook cleared.");
            }}
          />
        );
      case "profile":
        return <ProfilePage locale={locale} onNotify={showToast} />;
      case "settings":
        return <SettingsPage settings={settings} onSave={setSettings} onNotify={showToast} locale={locale} />;
      case "region":
        return (
          <RegionPage
            regions={REGION_OPTIONS}
            selectedRegion={selectedRegion}
            onSaveRegion={saveRegion}
            onNotify={showToast}
            locale={locale}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="app-shell">
      <Sidebar
        sections={localizedSections}
        activeSection={activeSection}
        onSectionChange={setActiveSection}
        selectedRegion={selectedRegion}
        lastUpdate={data.meta.lastUpdate}
        sidebarOpen={sidebarOpen}
        onCloseSidebar={() => setSidebarOpen(false)}
        locale={locale}
      />

      <div className="workspace">
        <TopBar
          selectedRegion={selectedRegion}
          searchQuery={globalSearch}
          onSearchChange={setGlobalSearch}
          onClearSearch={() => setGlobalSearch("")}
          onToggleSidebar={() => setSidebarOpen((current) => !current)}
          currentSectionLabel={currentSectionLabel}
          locale={locale}
        />
        <main className="workspace-main">{renderSection()}</main>
      </div>

      <TopicModal topic={modalTopic} onClose={() => setModalTopic(null)} onAddNote={addNote} />
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
