import { useMemo, useState } from "react";
import SelectField from "../components/common/SelectField";

const PERIODS = [
  { value: "24h", label: "24 часа" },
  { value: "7d", label: "7 дней" },
  { value: "30d", label: "30 дней" },
];

export default function ReportsPage({ reportPreview, topProblems, overviewSummary, locale = "ru" }) {
  const [period, setPeriod] = useState("7d");
  const [actionMessage, setActionMessage] = useState("");
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

  const copyReport = async () => {
    try {
      await navigator.clipboard.writeText(previewText);
      setActionMessage(isRu ? "Сводка скопирована." : "Summary copied.");
    } catch (error) {
      setActionMessage(isRu ? "Не удалось скопировать сводку." : "Unable to copy summary.");
    }
  };

  const downloadReport = () => {
    const blob = new Blob([previewText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const date = new Date().toISOString().slice(0, 10);
    link.href = url;
    link.download = `report-${period}-${date}.txt`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setActionMessage(isRu ? "Файл отчёта скачан." : "Report file downloaded.");
  };

  return (
    <div className="page">
      <div className="card toolbar">
        <h2>{isRu ? "Отчёты" : "Reports"}</h2>
        <div className="filters-grid">
          <label>
            {isRu ? "Период" : "Period"}
            <SelectField
              ariaLabel={isRu ? "Период" : "Period"}
              value={period}
              onChange={setPeriod}
              options={PERIODS}
            />
          </label>
          <div className="report-actions">
            <button type="button" className="secondary-button" onClick={copyReport}>
              {isRu ? "Скопировать" : "Copy"}
            </button>
            <button type="button" className="primary-button" onClick={downloadReport}>
              {isRu ? "Скачать .txt" : "Download .txt"}
            </button>
            {actionMessage && <span className="muted">{actionMessage}</span>}
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
