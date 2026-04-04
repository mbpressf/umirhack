const PRIORITY_TONE = {
  Критический: "critical",
  Высокий: "high",
  Средний: "medium",
  Наблюдение: "neutral",
};

export const getPriorityTone = (priority) => PRIORITY_TONE[priority] ?? "neutral";

export default function Badge({ text, tone = "neutral", outlined = false }) {
  return (
    <span className={`badge badge-${tone} ${outlined ? "badge-outlined" : ""}`.trim()}>
      {text}
    </span>
  );
}

