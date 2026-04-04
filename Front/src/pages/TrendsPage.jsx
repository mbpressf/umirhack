import { useEffect, useMemo, useState } from "react";
import { PERIOD_OPTIONS } from "../data/mockData";
import LineChart from "../components/common/LineChart";

export default function TrendsPage({ trends }) {
  const [period, setPeriod] = useState("7d");
  const periodData = trends[period];

  const [activeSector, setActiveSector] = useState("");

  useEffect(() => {
    setActiveSector(periodData.sectorDynamics[0]?.sector ?? "");
  }, [periodData.sectorDynamics]);

  const activeSectorData = useMemo(
    () => periodData.sectorDynamics.find((item) => item.sector === activeSector),
    [activeSector, periodData.sectorDynamics],
  );

  return (
    <div className="page">
      <div className="card toolbar">
        <h2>Тренды</h2>
        <div className="segmented">
          {PERIOD_OPTIONS.map((option) => (
            <button key={option.value} type="button" className={period === option.value ? "active" : ""} onClick={() => setPeriod(option.value)}>
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="overview-grid trends-grid">
        <section className="card animate-in">
          <div className="section-head">
            <h3>Динамика обсуждений</h3>
            <span>{periodData.label}</span>
          </div>
          <LineChart values={periodData.volumeSeries} labels={periodData.timelineLabels} />
        </section>

        <section className="card animate-in">
          <div className="section-head">
            <h3>Всплески за период</h3>
            <span>ключевые события</span>
          </div>
          <ul className="plain-list">
            {periodData.spikes.map((spike) => (
              <li key={`${spike.time}-${spike.title}`}>
                <div>
                  <strong>{spike.title}</strong>
                  <small>{spike.time}</small>
                </div>
                <span className="growth-indicator">{spike.growth}</span>
              </li>
            ))}
            {!periodData.spikes.length && (
              <li>
                <span>В выбранном периоде заметные всплески пока не выявлены.</span>
              </li>
            )}
          </ul>
        </section>

        <section className="card animate-in">
          <div className="section-head">
            <h3>Изменение по отраслям</h3>
            <span>рост к предыдущему периоду</span>
          </div>
          <div className="sector-bars">
            {periodData.sectorDynamics.map((sector) => (
              <button
                type="button"
                key={sector.sector}
                className={`sector-row ${activeSector === sector.sector ? "active" : ""}`}
                onClick={() => setActiveSector(sector.sector)}
              >
                <span>{sector.sector}</span>
                <div className="sector-bar-track">
                  <div className="sector-bar-fill" style={{ width: `${Math.min(sector.change * 2, 100)}%` }} />
                </div>
                <strong>+{sector.change}%</strong>
              </button>
            ))}
            {!periodData.sectorDynamics.length && <p className="empty-state">Данные по отраслям недоступны.</p>}
          </div>
        </section>

        <section className="card animate-in">
          <div className="section-head">
            <h3>Рост географии</h3>
            <span>муниципалитеты с наибольшей динамикой</span>
          </div>
          <ul className="plain-list">
            {periodData.geographyGrowth.map((item) => (
              <li key={item.municipality}>
                <span>{item.municipality}</span>
                <span className="growth-indicator">+{item.growth}%</span>
              </li>
            ))}
            {!periodData.geographyGrowth.length && (
              <li>
                <span>География роста пока не определена.</span>
              </li>
            )}
          </ul>
        </section>

        <section className="card animate-in trend-stat-card">
          <h3>Рост числа жалоб</h3>
          <strong>{periodData.complaintGrowth}%</strong>
          <p>
            Индикатор показывает изменение доли сообщений с формулировкой жалобы относительно предыдущего аналогичного периода.
          </p>
          {activeSectorData && (
            <small>
              Активная отрасль: {activeSectorData.sector}, объём сигналов {activeSectorData.volume}
            </small>
          )}
        </section>
      </div>
    </div>
  );
}
