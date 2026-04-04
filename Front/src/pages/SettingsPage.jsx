import { useEffect, useState } from "react";

const SECTORS = [
  "ЖКХ",
  "Транспорт",
  "Здравоохранение",
  "Образование",
  "Экология/ЧС",
  "Экономика/промышленность",
  "Благоустройство",
];

export default function SettingsPage({ settings, onSave, onNotify, locale = "ru" }) {
  const [draft, setDraft] = useState(settings);
  const isRu = locale === "ru";

  useEffect(() => {
    setDraft(settings);
  }, [settings]);

  const toggleSector = (sector) => {
    const exists = draft.prioritySectors.includes(sector);
    setDraft((current) => ({
      ...current,
      prioritySectors: exists
        ? current.prioritySectors.filter((item) => item !== sector)
        : [...current.prioritySectors, sector],
    }));
  };

  const toggleIntegration = (key) => {
    setDraft((current) => ({
      ...current,
      integrations: {
        ...current.integrations,
        [key]: !current.integrations[key],
      },
    }));
  };

  return (
    <div className="page">
      <div className="card settings-card animate-in">
        <h2>{isRu ? "Настройки" : "Settings"}</h2>
        <div className="settings-grid">
          <label>
            {isRu ? "Тема интерфейса" : "Theme"}
            <select
              value={draft.theme}
              onChange={(event) => setDraft((current) => ({ ...current, theme: event.target.value }))}
            >
              <option value="light">{isRu ? "Светлая" : "Light"}</option>
              <option value="dark">{isRu ? "Тёмная" : "Dark"}</option>
            </select>
          </label>

          <label>
            {isRu ? "Язык интерфейса" : "Interface language"}
            <select
              value={draft.language}
              onChange={(event) => setDraft((current) => ({ ...current, language: event.target.value }))}
            >
              <option value="ru">Русский</option>
              <option value="en">English</option>
            </select>
          </label>

          <label>
            {isRu ? "Частота обновления" : "Refresh rate"}
            <select
              value={draft.refreshRate}
              onChange={(event) => setDraft((current) => ({ ...current, refreshRate: event.target.value }))}
            >
              <option>5 минут</option>
              <option>15 минут</option>
              <option>30 минут</option>
              <option>60 минут</option>
            </select>
          </label>

          <label className="single-check">
            <input
              type="checkbox"
              checked={draft.publicOnly}
              onChange={(event) =>
                setDraft((current) => ({ ...current, publicOnly: event.target.checked }))
              }
            />
            <span>
              {isRu ? "Учитывать только публичные данные" : "Use only public data"}
            </span>
          </label>
        </div>

        <section>
          <h3>{isRu ? "Приоритетные отрасли" : "Priority sectors"}</h3>
          <div className="chip-grid">
            {SECTORS.map((sector) => (
              <button
                key={sector}
                type="button"
                className={`chip ${draft.prioritySectors.includes(sector) ? "active" : ""}`}
                onClick={() => toggleSector(sector)}
              >
                {sector}
              </button>
            ))}
          </div>
        </section>

        <section>
          <h3>{isRu ? "Будущие интеграции" : "Future integrations"}</h3>
          <div className="switch-list">
            <label>
              <input
                type="checkbox"
                checked={draft.integrations.federalAppeals}
                onChange={() => toggleIntegration("federalAppeals")}
              />
              <span>
                {isRu ? "Федеральные площадки обращений" : "Federal appeals platforms"}
              </span>
            </label>
            <label>
              <input
                type="checkbox"
                checked={draft.integrations.system112}
                onChange={() => toggleIntegration("system112")}
              />
              <span>{isRu ? "Система 112" : "System 112"}</span>
            </label>
            <label>
              <input
                type="checkbox"
                checked={draft.integrations.incidentsCenter}
                onChange={() => toggleIntegration("incidentsCenter")}
              />
              <span>
                {isRu ? "Ситуационный центр инцидентов" : "Incident response center"}
              </span>
            </label>
          </div>
        </section>

        <div className="form-actions">
          <button
            type="button"
            className="primary-button"
            onClick={() => {
              onSave(draft);
              onNotify(
                isRu
                  ? "Системные настройки сохранены."
                  : "System settings have been saved.",
              );
            }}
          >
            {isRu ? "Сохранить настройки" : "Save settings"}
          </button>
        </div>
      </div>
    </div>
  );
}
