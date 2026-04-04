import { useEffect, useMemo, useState } from "react";

export default function RegionPage({ regions, selectedRegion, onSaveRegion, onNotify, locale = "ru" }) {
  const [nextRegion, setNextRegion] = useState(selectedRegion);
  const isRu = locale === "ru";

  useEffect(() => {
    setNextRegion(selectedRegion);
  }, [selectedRegion]);

  const selectedCard = useMemo(
    () => regions.find((region) => region.name === selectedRegion),
    [regions, selectedRegion],
  );

  return (
    <div className="page">
      <div className="card region-current animate-in">
        <h2>{isRu ? "Выбор региона" : "Region selection"}</h2>
        <p>
          {isRu ? "Текущий регион:" : "Current region:"} <strong>{selectedRegion}</strong>
        </p>
        <p className="muted">
          {isRu
            ? "Раздел готов к масштабированию: регион выбирается из выпадающего списка и сохраняется локально."
            : "The section is scalable: region is selected from dropdown and saved locally."}
        </p>
      </div>

      <div className="card region-select-card animate-in">
        <label>
          {isRu ? "Регион" : "Region"}
          <select value={nextRegion} onChange={(event) => setNextRegion(event.target.value)}>
            {regions.map((region) => (
              <option key={region.id} value={region.name}>
                {region.name}
              </option>
            ))}
          </select>
        </label>

        <div className="region-selected-line">
          <span>{isRu ? "Статус:" : "Status:"}</span>
          <strong>{isRu ? "Выбрано" : "Selected"}</strong>
        </div>

        <div className="problem-actions">
          <button
            type="button"
            className="primary-button"
            onClick={() => {
              onSaveRegion(nextRegion);
              onNotify(
                isRu ? `Регион сохранён: ${nextRegion}.` : `Region saved: ${nextRegion}.`,
              );
            }}
          >
            {isRu ? "Сохранить регион" : "Save region"}
          </button>
        </div>
      </div>

      {selectedCard && (
        <div className="card animate-in">
          <h3>{selectedCard.name}</h3>
          <p>{selectedCard.description}</p>
        </div>
      )}
    </div>
  );
}
