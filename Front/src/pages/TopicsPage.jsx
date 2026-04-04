import { useMemo, useState } from "react";
import Badge, { getPriorityTone } from "../components/common/Badge";
import SelectField from "../components/common/SelectField";
import { getAllMunicipalities, getAllSectors } from "../data/mockData";

const WINDOWS = [
  { value: "all", label: "Любой период" },
  { value: "24", label: "24 часа" },
  { value: "7", label: "7 дней" },
  { value: "30", label: "30 дней" },
];

export default function TopicsPage({ topics, globalSearch, onSearchChange, onOpenTopic }) {
  const [sector, setSector] = useState("Все");
  const [municipality, setMunicipality] = useState("Все");
  const [sourceType, setSourceType] = useState("Все");
  const [windowFilter, setWindowFilter] = useState("all");
  const [sortBy, setSortBy] = useState("score");
  const [viewMode, setViewMode] = useState("cards");

  const sectors = useMemo(() => ["Все", ...getAllSectors(topics)], [topics]);
  const municipalities = useMemo(() => ["Все", ...getAllMunicipalities(topics)], [topics]);

  const filtered = useMemo(() => {
    const mergedQuery = `${globalSearch}`.trim().toLowerCase();
    return topics
      .filter((item) => (sector === "Все" ? true : item.sector === sector))
      .filter((item) => (municipality === "Все" ? true : item.municipality === municipality))
      .filter((item) =>
        sourceType === "Все" ? true : item.sourceTypes?.some((type) => type.toLowerCase().includes(sourceType.toLowerCase())),
      )
      .filter((item) => {
        if (windowFilter === "all") {
          return true;
        }
        if (windowFilter === "24") {
          return item.rank !== null && item.rank <= 5;
        }
        if (windowFilter === "7") {
          return item.rank !== null ? item.rank <= 10 : item.score >= 58;
        }
        return item.score >= 60;
      })
      .filter((item) =>
        mergedQuery
          ? [item.title, item.summary, item.municipality, item.sector].join(" ").toLowerCase().includes(mergedQuery)
          : true,
      )
      .sort((a, b) => {
        if (sortBy === "score") {
          return b.score - a.score;
        }
        if (sortBy === "sources") {
          return b.sourceCount - a.sourceCount;
        }
        return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
      });
  }, [globalSearch, municipality, sector, sortBy, sourceType, topics, windowFilter]);

  const resetFilters = () => {
    onSearchChange("");
    setSector("Все");
    setMunicipality("Все");
    setSourceType("Все");
    setWindowFilter("all");
    setSortBy("score");
  };

  return (
    <div className="page">
      <div className="card toolbar">
        <h2>Темы и события</h2>
        <div className="filters-grid topics-filters">
          <input
            className="page-search-input page-compact-control"
            type="search"
            value={globalSearch}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Поиск"
            aria-label="Поиск"
          />
          <SelectField
            className="page-compact-control"
            ariaLabel="Отрасль"
            value={sector}
            onChange={setSector}
            options={sectors.map((value) => ({
              value,
              label: value === "Все" ? "Отрасль" : value,
            }))}
          />
          <SelectField
            className="page-compact-control"
            ariaLabel="Муниципалитет"
            value={municipality}
            onChange={setMunicipality}
            options={municipalities.map((value) => ({
              value,
              label: value === "Все" ? "Муниципалитет" : value,
            }))}
          />
          <SelectField
            className="page-compact-control"
            ariaLabel="Тип источника"
            value={sourceType}
            onChange={setSourceType}
            options={["Все", "СМИ", "Telegram", "ВКонтакте", "Официальный"].map((value) => ({
              value,
              label: value === "Все" ? "Тип источника" : value,
            }))}
          />
          <SelectField
            className="page-compact-control"
            ariaLabel="Период"
            value={windowFilter}
            onChange={setWindowFilter}
            options={WINDOWS.map((windowOption) => ({
              value: windowOption.value,
              label: windowOption.value === "all" ? "Период" : windowOption.label,
            }))}
          />
          <SelectField
            className="page-compact-control"
            ariaLabel="Сортировка"
            value={sortBy}
            onChange={setSortBy}
            options={[
              { value: "score", label: "Сортировка" },
              { value: "updated", label: "По дате обновления" },
              { value: "sources", label: "По числу источников" },
            ]}
          />
        </div>
        <div className="filters-actions">
          <button type="button" className="ghost-button" onClick={resetFilters}>
            Сбросить фильтры
          </button>
        </div>

        <div className="toolbar-end">
          <div className="view-switch segmented">
            <button type="button" className={viewMode === "cards" ? "active" : ""} onClick={() => setViewMode("cards")}>
              Карточки
            </button>
            <button type="button" className={viewMode === "table" ? "active" : ""} onClick={() => setViewMode("table")}>
              Таблица
            </button>
          </div>
          <span>{filtered.length} тем</span>
        </div>
      </div>

      {viewMode === "cards" ? (
        <div className="cards-stack">
          {filtered.map((topic) => (
            <article key={topic.id} className="card topic-card animate-in">
              <div className="topic-card-main">
                <h3>{topic.title}</h3>
                <Badge text={topic.priority} tone={getPriorityTone(topic.priority)} />
              </div>
              <p>{topic.summary}</p>
              <div className="problem-meta">
                <span>{topic.sector}</span>
                <span>{topic.municipality}</span>
                <span>Интегральный балл: {topic.score}</span>
                <span>Источников: {topic.sourceCount}</span>
              </div>
              <div className="problem-actions">
                <button type="button" className="secondary-button topic-open-button" onClick={() => onOpenTopic(topic)}>
                  Открыть карточку
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="card table-wrap animate-in">
          <table>
            <thead>
              <tr>
                <th>Тема</th>
                <th>Отрасль</th>
                <th>Муниципалитет</th>
                <th>Важность</th>
                <th>Интегральный балл</th>
                <th>Источники</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.map((topic) => (
                <tr key={topic.id}>
                  <td>{topic.title}</td>
                  <td>{topic.sector}</td>
                  <td>{topic.municipality}</td>
                  <td>
                    <Badge text={topic.priority} tone={getPriorityTone(topic.priority)} />
                  </td>
                  <td>{topic.score}</td>
                  <td>{topic.sourceCount}</td>
                  <td>
                    <button type="button" className="ghost-button" onClick={() => onOpenTopic(topic)}>
                      Подробнее
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!filtered.length && <div className="card empty-state">По выбранным условиям темы не найдены.</div>}
    </div>
  );
}
