const makePoints = (values) => {
  if (!values.length) {
    return "";
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);

  return values
    .map((value, index) => {
      const x = (index / (values.length - 1 || 1)) * 100;
      const y = 88 - ((value - min) / range) * 70;
      return `${x},${y}`;
    })
    .join(" ");
};

export default function LineChart({ values = [], labels = [], highlight = "var(--accent)" }) {
  const points = makePoints(values);

  return (
    <div className="line-chart">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="График динамики">
        <polyline points="0,88 100,88" className="line-chart-grid" />
        <polyline points={points} className="line-chart-line" style={{ stroke: highlight }} />
      </svg>
      <div className="line-chart-labels">
        {labels.map((label) => (
          <span key={label}>{label}</span>
        ))}
      </div>
    </div>
  );
}
