import { useMemo, useState } from "react";
import Badge, { getPriorityTone } from "../components/common/Badge";
import LineChart from "../components/common/LineChart";

const KPI_TITLES = [
  { key: "totalTopics", label: "Всего тем за период" },
  { key: "newCriticalTopics", label: "Новых критических тем" },
  { key: "municipalitiesWithSignals", label: "Муниципалитетов с сигналами" },
  { key: "officialConfirmedShare", label: "Доля официально подтверждённых сообщений", postfix: "%" },
];

export default function OverviewPage({
  data,
  globalSearch,
  onOpenTopic,
  pilotNotice,
  locale = "ru",
}) {
  const isRu = locale === "ru";
  const [summaryMode, setSummaryMode] = useState("day");

  const search = globalSearch.trim().toLowerCase();
  const topList = useMemo(() => {
    if (!search) {
      return data.topProblems.slice(0, 10);
    }

    return data.topProblems.filter((item) =>
      [item.title, item.municipality, item.sector].join(" ").toLowerCase().includes(search),
    );
  }, [data.topProblems, search]);

  return (
    <div className="page">
      {pilotNotice && <div className="pilot-banner">{pilotNotice}</div>}

      <div className="kpi-grid">
        {KPI_TITLES.map((item) => (
          <article key={item.key} className="card kpi-card">
            <span>{item.label}</span>
            <strong>
              {data.kpi[item.key]}
              {item.postfix ?? ""}
            </strong>
          </article>
        ))}
      </div>

      <div className="overview-grid">
        <section className="card animate-in">
          <div className="section-head">
            <h2>{isRu ? "Приоритетные проблемы региона" : "Priority regional issues"}</h2>
            <span>{isRu ? "по интегральной оценке" : "by integral score"}</span>
          </div>
          <div className="top-list">
            {topList.slice(0, 10).map((problem) => (
              <button key={problem.id} type="button" className="top-item" onClick={() => onOpenTopic(problem)}>
                <span className="top-rank">{problem.rank}</span>
                <div>
                  <strong>{problem.title}</strong>
                  <small>
                    {problem.municipality} · {problem.sector}
                  </small>
                </div>
                <Badge text={problem.priority} tone={getPriorityTone(problem.priority)} />
              </button>
            ))}
            {!topList.length && <p className="empty-state">По текущему запросу совпадения не найдены.</p>}
          </div>
        </section>

        <section className="card animate-in">
          <div className="section-head">
            <h2>Краткая сводка</h2>
            <div className="segmented">
              <button type="button" className={summaryMode === "day" ? "active" : ""} onClick={() => setSummaryMode("day")}>
                Сутки
              </button>
              <button type="button" className={summaryMode === "week" ? "active" : ""} onClick={() => setSummaryMode("week")}>
                Неделя
              </button>
            </div>
          </div>
          <p>{summaryMode === "day" ? data.overviewSummary.day : data.overviewSummary.week}</p>
          <div className="mini-chart-wrap">
            <h3>Динамика сигналов</h3>
            <LineChart values={data.miniTrendSeries} labels={data.miniTrendLabels} />
          </div>
        </section>

        <section className="card animate-in">
          <div className="section-head">
            <h2>Последние критические сигналы</h2>
            <span>оперативный список</span>
          </div>
          <ul className="plain-list">
            {data.criticalSignals.map((signal) => (
              <li key={signal.id}>
                <div>
                  <strong>{signal.title}</strong>
                  <small>
                    {signal.municipality} · {signal.source}
                  </small>
                </div>
                <div className="signal-meta">
                  <small>{signal.time}</small>
                  <Badge text={signal.priority} tone={getPriorityTone(signal.priority)} />
                </div>
              </li>
            ))}
            {!data.criticalSignals.length && (
              <li>
                <span>Критические сигналы пока отсутствуют.</span>
              </li>
            )}
          </ul>
        </section>

        <section className="card animate-in">
          <div className="section-head">
            <h2>География сигналов</h2>
            <span>Ростовская область</span>
          </div>
          <div className="municipality-grid">
            {data.municipalities.slice(0, 9).map((item) => (
              <div
                className="municipality-cell"
                key={item.name}
                style={{ "--level": item.level }}
                title={`${item.name}: ${item.signals} сигналов`}
              >
                <strong>{item.name}</strong>
                <small>{item.signals} сигналов</small>
              </div>
            ))}
            {!data.municipalities.length && <p className="empty-state">Геоблок станет доступен после загрузки данных региона.</p>}
          </div>
        </section>
      </div>
    </div>
  );
}
