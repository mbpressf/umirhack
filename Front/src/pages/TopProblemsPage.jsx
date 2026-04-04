import { useMemo, useState } from "react";
import Badge, { getPriorityTone } from "../components/common/Badge";
import SelectField from "../components/common/SelectField";
import { getAllMunicipalities, getAllSectors } from "../data/mockData";

export default function TopProblemsPage({ problems, globalSearch, onSearchChange, onOpenTopic }) {
  const [sector, setSector] = useState("Все");
  const [municipality, setMunicipality] = useState("Все");
  const [priority, setPriority] = useState("Все");
  const [expandedId, setExpandedId] = useState(null);

  const sectors = useMemo(() => ["Все", ...getAllSectors(problems)], [problems]);
  const municipalities = useMemo(() => ["Все", ...getAllMunicipalities(problems)], [problems]);

  const filtered = useMemo(() => {
    const query = globalSearch.trim().toLowerCase();
    return problems
      .filter((item) => (sector === "Все" ? true : item.sector === sector))
      .filter((item) => (municipality === "Все" ? true : item.municipality === municipality))
      .filter((item) => (priority === "Все" ? true : item.priority === priority))
      .filter((item) =>
        query
          ? [item.title, item.summary, item.municipality, item.sector].join(" ").toLowerCase().includes(query)
          : true,
      );
  }, [globalSearch, municipality, priority, problems, sector]);

  const resetFilters = () => {
    onSearchChange("");
    setSector("Все");
    setMunicipality("Все");
    setPriority("Все");
  };

  return (
    <div className="page">
      <div className="toolbar card">
        <h2>Топ проблем</h2>
        <div className="filters-grid">
          <input
            className="page-filter-control page-search-input page-compact-control"
            type="search"
            value={globalSearch}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Поиск"
            aria-label="Поиск"
          />
          <SelectField
            className="page-filter-control page-compact-control"
            ariaLabel="Отрасль"
            value={sector}
            onChange={setSector}
            options={sectors.map((value) => ({
              value,
              label: value === "Все" ? "Отрасль" : value,
            }))}
          />
          <SelectField
            className="page-filter-control page-compact-control"
            ariaLabel="Муниципалитет"
            value={municipality}
            onChange={setMunicipality}
            options={municipalities.map((value) => ({
              value,
              label: value === "Все" ? "Муниципалитет" : value,
            }))}
          />
          <SelectField
            className="page-filter-control page-compact-control"
            ariaLabel="Важность"
            value={priority}
            onChange={setPriority}
            options={["Все", "Критический", "Высокий", "Средний", "Наблюдение"].map((value) => ({
              value,
              label: value === "Все" ? "Важность" : value,
            }))}
          />
          <div className="filter-counter">{filtered.length} карточек</div>
        </div>
        <div className="filters-actions">
          <button type="button" className="ghost-button" onClick={resetFilters}>
            Сбросить фильтры
          </button>
        </div>
      </div>

      <div className="cards-stack">
        {filtered.map((problem) => {
          const expanded = expandedId === problem.id;
          return (
            <article key={problem.id} className="card problem-card animate-in">
              <div className="problem-main">
                <div className="rank-badge">{problem.rank}</div>
                <div className="problem-text">
                  <div className="problem-title-row">
                    <h3>{problem.title}</h3>
                    <Badge text={problem.priority} tone={getPriorityTone(problem.priority)} />
                  </div>
                  <p>{problem.summary}</p>
                  <div className="problem-meta">
                    <span>Отрасль: {problem.sector}</span>
                    <span>Муниципалитет: {problem.municipality}</span>
                    <span>Интегральный балл: {problem.score}</span>
                    <span>Источников: {problem.sourceCount}</span>
                    <span>Официальный сигнал: {problem.officialSignal ? "Да" : "Нет"}</span>
                    <span>Противоречие: {problem.contradiction ? "Да" : "Нет"}</span>
                  </div>
                </div>
              </div>

              {expanded && (
                <div className="problem-extra">
                  <h4>Почему тема в топе</h4>
                  <p>{problem.whyTop}</p>
                  <div className="factor-inline-list">
                    {Object.entries(problem.factors).map(([key, value]) => (
                      <div key={key} className="factor-inline-item">
                        <small>{key}</small>
                        <div className="factor-track">
                          <div className="factor-fill" style={{ width: `${value}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="problem-actions">
                <button type="button" className="secondary-button" onClick={() => onOpenTopic(problem)}>
                  Подробнее
                </button>
                <button type="button" className="ghost-button" onClick={() => onOpenTopic(problem)}>
                  Источники
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => setExpandedId((current) => (current === problem.id ? null : problem.id))}
                >
                  {expanded ? "Скрыть детали" : "Показать детали"}
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {!filtered.length && <div className="card empty-state">По выбранным фильтрам проблем не найдено.</div>}
    </div>
  );
}

