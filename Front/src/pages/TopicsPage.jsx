import { useMemo, useState } from "react";
import Badge, { getPriorityTone } from "../components/common/Badge";
import { getAllMunicipalities, getAllSectors } from "../data/mockData";

const WINDOWS = [
  { value: "all", label: "Любой период" },
  { value: "24", label: "24 часа" },
  { value: "7", label: "7 дней" },
  { value: "30", label: "30 дней" },
];

export default function TopicsPage({ topics, globalSearch, onOpenTopic }) {
  const [localSearch, setLocalSearch] = useState("");
  const [sector, setSector] = useState("Все");
  const [municipality, setMunicipality] = useState("Все");
  const [sourceType, setSourceType] = useState("Все");
  const [windowFilter, setWindowFilter] = useState("all");
  const [sortBy, setSortBy] = useState("score");
  const [viewMode, setViewMode] = useState("cards");

  const sectors = useMemo(() => ["Все", ...getAllSectors(topics)], [topics]);
  const municipalities = useMemo(() => ["Все", ...getAllMunicipalities(topics)], [topics]);

  const filtered = useMemo(() => {
    const mergedQuery = `${globalSearch} ${localSearch}`.trim().toLowerCase();
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
  }, [globalSearch, localSearch, municipality, sector, sortBy, sourceType, topics, windowFilter]);

  return (
    <div className="page">
      <div className="card toolbar">
        <h2>Темы и события</h2>
        <div className="filters-grid topics-filters">
          <label>
            Поиск
            <input
              type="search"
              value={localSearch}
              onChange={(event) => setLocalSearch(event.target.value)}
              placeholder="Название темы или ключевые слова"
            />
          </label>
          <label>
            Отрасль
            <select value={sector} onChange={(event) => setSector(event.target.value)}>
              {sectors.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Муниципалитет
            <select value={municipality} onChange={(event) => setMunicipality(event.target.value)}>
              {municipalities.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Тип источника
            <select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
              {["Все", "СМИ", "Telegram", "ВКонтакте", "Официальный"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Период
            <select value={windowFilter} onChange={(event) => setWindowFilter(event.target.value)}>
              {WINDOWS.map((windowOption) => (
                <option key={windowOption.value} value={windowOption.value}>
                  {windowOption.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Сортировка
            <select value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
              <option value="score">По интегральному баллу</option>
              <option value="updated">По дате обновления</option>
              <option value="sources">По числу источников</option>
            </select>
          </label>
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
