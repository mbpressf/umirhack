import { useEffect, useState } from "react";
import SelectField from "../components/common/SelectField";

const DEFAULT_SECTORS = [
  "ЖКХ",
  "Транспорт",
  "Здравоохранение",
  "Образование",
  "Экология/ЧС",
  "Экономика/промышленность",
  "Благоустройство",
];

export default function SettingsPage({ settings, onSave, onNotify, locale = "ru", availableSectors = DEFAULT_SECTORS }) {
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
            <SelectField
              ariaLabel={isRu ? "Тема интерфейса" : "Theme"}
              value={draft.theme}
              onChange={(nextValue) => setDraft((current) => ({ ...current, theme: nextValue }))}
              options={[
                { value: "light", label: isRu ? "Светлая" : "Light" },
                { value: "dark", label: isRu ? "Тёмная" : "Dark" },
              ]}
            />
          </label>

          <label>
            {isRu ? "Язык интерфейса" : "Interface language"}
            <SelectField
              ariaLabel={isRu ? "Язык интерфейса" : "Interface language"}
              value={draft.language}
              onChange={(nextValue) => setDraft((current) => ({ ...current, language: nextValue }))}
              options={[
                { value: "ru", label: "Русский" },
                { value: "en", label: "English" },
              ]}
            />
          </label>

          <label>
            {isRu ? "Частота обновления" : "Refresh rate"}
            <SelectField
              ariaLabel={isRu ? "Частота обновления" : "Refresh rate"}
              value={draft.refreshRate}
              onChange={(nextValue) => setDraft((current) => ({ ...current, refreshRate: nextValue }))}
              options={[
                { value: "5 минут", label: "5 минут" },
                { value: "15 минут", label: "15 минут" },
                { value: "30 минут", label: "30 минут" },
                { value: "60 минут", label: "60 минут" },
              ]}
            />
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
            {availableSectors.map((sector) => (
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
