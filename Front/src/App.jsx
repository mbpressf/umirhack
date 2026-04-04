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
import ProfilePage from "./pages/ProfilePage";
import SettingsPage from "./pages/SettingsPage";
import NotebookPage from "./pages/NotebookPage";
import { DEFAULT_SETTINGS, SIDEBAR_SECTIONS, getRegionData } from "./data/mockData";
import { fetchFrontendSnapshot, fetchMetadata } from "./lib/api";

const STORAGE = {
  settings: "signal:settings",
  history: "signal:region-history",
  notes: "signal:notebook-notes",
};

const DEFAULT_REGION = "Ростовская область";
const LIVE_REFRESH_MS = Number(import.meta.env.VITE_AUTO_REFRESH_MS ?? 60000);

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
    notebook: "Notebook",
    profile: "Profile",
    settings: "Settings",
  },
};

export default function App() {
  const [activeSection, setActiveSection] = useState("overview");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const selectedRegion = DEFAULT_REGION;
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
  const [metadata, setMetadata] = useState(null);
  const backendRegion = DEFAULT_REGION;

  const locale = settings.language === "en" ? "en" : "ru";
  const sectionLabels = SECTION_LABELS[locale] ?? SECTION_LABELS.ru;
  const currentSectionLabel = sectionLabels[activeSection] ?? sectionLabels.overview;

  const data = useMemo(() => {
    if (
      selectedRegion === liveSnapshot?.meta?.regionName &&
      liveSnapshot?.meta?.dataReady !== false
    ) {
      return liveSnapshot;
    }

    return getRegionData(selectedRegion);
  }, [liveSnapshot, selectedRegion]);

  const localizedSections = useMemo(
    () =>
      SIDEBAR_SECTIONS.filter((section) => section.id !== "region").map((section) => ({
        ...section,
        label: sectionLabels[section.id] ?? section.label,
      })),
    [sectionLabels],
  );

  const pilotNotice = useMemo(() => {
    if (selectedRegion === backendRegion && liveState.error) {
      return locale === "ru"
        ? "Live-данные временно недоступны, поэтому интерфейс показывает резервный набор."
        : "Live data is temporarily unavailable, fallback data is shown.";
    }
    if (selectedRegion === backendRegion && liveState.loading) {
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
  }, [backendRegion, data.meta.pilot, liveState.error, liveState.loading, locale, selectedRegion]);

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
    let controller = new AbortController();
    fetchMetadata(controller.signal)
      .then((payload) => setMetadata(payload))
      .catch((error) => {
        if (error.name !== "AbortError") {
          // keep silent fallback to local mock options
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (selectedRegion !== backendRegion) {
      setLiveState({ loading: false, error: "" });
      return undefined;
    }

    let controller = null;

    const loadSnapshot = async ({ silent = false } = {}) => {
      controller?.abort();
      controller = new AbortController();

      if (!silent) {
        setLiveState((current) => ({ ...current, loading: true, error: "" }));
      }

      try {
        const payload = await fetchFrontendSnapshot(controller.signal);
        setLiveSnapshot(payload);
        setLiveState({ loading: false, error: "" });
      } catch (error) {
        if (error.name === "AbortError") {
          return;
        }
        setLiveState({ loading: false, error: error.message });
      }
    };

    loadSnapshot();
    const intervalId = window.setInterval(() => {
      loadSnapshot({ silent: true });
    }, LIVE_REFRESH_MS);

    return () => {
      controller?.abort();
      window.clearInterval(intervalId);
    };
  }, [backendRegion, selectedRegion]);

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

  const notebookNewsOptions = useMemo(() => {
    const now = Date.now();
    const sevenDaysAgo = now - 7 * 24 * 60 * 60 * 1000;
    const topics = Array.isArray(data?.topics) ? data.topics : [];
    return topics
      .filter((topic) => {
        if (!topic?.updatedAt) {
          return true;
        }
        const stamp = new Date(topic.updatedAt).getTime();
        if (!Number.isFinite(stamp)) {
          return true;
        }
        return stamp >= sevenDaysAgo;
      })
      .map((topic) => ({
        id: topic.id,
        title: topic.title,
        summary: topic.summary,
        municipality: topic.municipality,
        score: topic.score ?? 0,
        rank: topic.rank ?? null,
      }));
  }, [data?.topics]);

  const createNotebookNote = ({ selectedNews, text, mark }) => {
    const note = {
      id: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      topicId: selectedNews?.id ?? "",
      topicTitle: selectedNews?.title ?? "Без привязки к новости",
      region: selectedRegion,
      municipality: selectedNews?.municipality ?? "Без локации",
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
    const backendSectors =
      metadata?.filters?.sectors?.length
        ? metadata.filters.sectors
        : DEFAULT_SETTINGS.prioritySectors;

    switch (activeSection) {
      case "overview":
        return (
          <OverviewPage
            data={data}
            globalSearch={globalSearch}
            onSearchChange={setGlobalSearch}
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
            onSearchChange={setGlobalSearch}
            onOpenTopic={setModalTopic}
          />
        );
      case "topics":
        return (
          <TopicsPage
            topics={data.topics}
            globalSearch={globalSearch}
            onSearchChange={setGlobalSearch}
            onOpenTopic={setModalTopic}
          />
        );
      case "trends":
        return <TrendsPage trends={data.trends} />;
      case "sources":
        return <SourcesPage sources={data.sources} globalSearch={globalSearch} onSearchChange={setGlobalSearch} />;
      case "geography":
        return (
          <GeographyPage
            municipalities={data.municipalities}
            topProblems={data.topProblems}
            globalSearch={globalSearch}
            onOpenTopic={setModalTopic}
          />
        );
      case "notebook":
        return (
          <NotebookPage
            notes={notes}
            availableNews={notebookNewsOptions}
            onCreateNote={createNotebookNote}
            onDeleteNote={(id) => {
              setNotes((current) => current.filter((note) => note.id !== id));
              showToast(locale === "ru" ? "Заметка удалена." : "Note removed.");
            }}
            onClearNotes={() => {
              setNotes([]);
              showToast(locale === "ru" ? "Блокнот очищен." : "Notebook cleared.");
            }}
            locale={locale}
          />
        );
      case "profile":
        return <ProfilePage locale={locale} onNotify={showToast} />;
      case "settings":
        return (
          <SettingsPage
            settings={settings}
            onSave={setSettings}
            onNotify={showToast}
            locale={locale}
            availableSectors={backendSectors}
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

