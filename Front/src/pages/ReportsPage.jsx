import { useMemo, useState } from "react";

const PERIODS = [
  { value: "24h", label: "24 часа" },
  { value: "7d", label: "7 дней" },
  { value: "30d", label: "30 дней" },
];

export default function ReportsPage({ reportPreview, topProblems, overviewSummary, locale = "ru" }) {
  const [period, setPeriod] = useState("7d");
  const isRu = locale === "ru";

  const previewText = useMemo(() => {
    const top3 = topProblems
      .slice(0, 3)
      .map((item) => item.title)
      .join("; ");
    const summary = period === "24h" ? overviewSummary.day : overviewSummary.week;
    return `${summary}\n${
      isRu ? "Ключевые темы" : "Key topics"
    }: ${top3 || (isRu ? "данные в процессе подключения" : "data is being connected")}.\n${reportPreview}`;
  }, [isRu, overviewSummary.day, overviewSummary.week, period, reportPreview, topProblems]);

  return (
    <div className="page">
      <div className="card toolbar">
        <h2>{isRu ? "Отчёты" : "Reports"}</h2>
        <div className="filters-grid">
          <label>
            {isRu ? "Период" : "Period"}
            <select value={period} onChange={(event) => setPeriod(event.target.value)}>
              {PERIODS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <div className="card report-admin-only">
            {isRu
              ? "Экспорт сводок доступен только в админ-панели."
              : "Summary export is available only in admin panel."}
          </div>
        </div>
      </div>

      <section className="card animate-in report-preview">
        <h3>{isRu ? "Предпросмотр сводки" : "Summary preview"}</h3>
        <p>{previewText}</p>
      </section>
    </div>
  );
}
