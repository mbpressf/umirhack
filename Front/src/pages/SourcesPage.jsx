import { useMemo, useState } from "react";
import SelectField from "../components/common/SelectField";
import { SOURCE_STATUS_OPTIONS, SOURCE_TYPE_OPTIONS } from "../data/mockData";

export default function SourcesPage({ sources, globalSearch, onSearchChange }) {
  const [typeFilter, setTypeFilter] = useState("Все");
  const [statusFilter, setStatusFilter] = useState("Все");
  const [sortBy, setSortBy] = useState("share");

  const filtered = useMemo(() => {
    const query = globalSearch.trim().toLowerCase();
    return sources
      .filter((source) => (typeFilter === "Все" ? true : source.type === typeFilter))
      .filter((source) => (statusFilter === "Все" ? true : source.status === statusFilter))
      .filter((source) => (query ? source.name.toLowerCase().includes(query) : true))
      .sort((a, b) => {
        if (sortBy === "topics") {
          return b.topicCount - a.topicCount;
        }
        if (sortBy === "reliability") {
          return b.reliability - a.reliability;
        }
        return b.share - a.share;
      });
  }, [globalSearch, sortBy, sources, statusFilter, typeFilter]);

  const totalShare = filtered.reduce((sum, source) => sum + source.share, 0);
  const resetFilters = () => {
    onSearchChange("");
    setTypeFilter("Все");
    setStatusFilter("Все");
    setSortBy("share");
  };

  return (
    <div className="page">
      <div className="card toolbar">
        <h2>Источники</h2>
        <div className="filters-grid">
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
            ariaLabel="Тип площадки"
            value={typeFilter}
            onChange={setTypeFilter}
            options={SOURCE_TYPE_OPTIONS.map((option) => ({
              value: option,
              label: option === "Все" ? "Тип площадки" : option,
            }))}
          />
          <SelectField
            className="page-compact-control"
            ariaLabel="Статус источника"
            value={statusFilter}
            onChange={setStatusFilter}
            options={SOURCE_STATUS_OPTIONS.map((option) => ({
              value: option,
              label: option === "Все" ? "Статус источника" : option,
            }))}
          />
          <SelectField
            className="page-compact-control"
            ariaLabel="Сортировка"
            value={sortBy}
            onChange={setSortBy}
            options={[
              { value: "share", label: "Сортировка" },
              { value: "topics", label: "По числу тем" },
              { value: "reliability", label: "По надёжности" },
            ]}
          />
          <div className="filter-counter">Доля в выборке: {totalShare}%</div>
        </div>
        <div className="filters-actions">
          <button type="button" className="ghost-button" onClick={resetFilters}>
            Сбросить фильтры
          </button>
        </div>
      </div>

      <div className="cards-stack">
        {filtered.map((source) => (
          <article className="card source-card animate-in" key={source.id}>
            <div className="source-head">
              <h3>{source.name}</h3>
              <span>{source.status}</span>
            </div>
            <div className="source-meta">
              <span>Тип: {source.type}</span>
              <span>Тем: {source.topicCount}</span>
              <span>Последняя активность: {source.lastSeen}</span>
            </div>
            <div className="progress-line">
              <div className="progress-fill" style={{ width: `${Math.min(source.share * 4, 100)}%` }} />
            </div>
            <div className="source-foot">
              <strong>Вклад: {source.share}%</strong>
              <small>Надёжность: {(source.reliability * 100).toFixed(0)}%</small>
            </div>
          </article>
        ))}
      </div>

      {!filtered.length && <div className="card empty-state">Источники по выбранным фильтрам не найдены.</div>}
    </div>
  );
}
