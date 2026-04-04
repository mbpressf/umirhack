import { useEffect, useState } from "react";
import Badge, { getPriorityTone } from "./Badge";
import SelectField from "./SelectField";

const FACTOR_LABELS = {
  intensity: "Интенсивность обсуждения",
  coverage: "Географический охват",
  socialImpact: "Влияние на население",
  officialGap: "Расхождение с официальной позицией",
};

export default function TopicModal({ topic, onClose, onAddNote }) {
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [noteMark, setNoteMark] = useState("Обязательно");

  useEffect(() => {
    if (!topic) {
      return undefined;
    }

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [topic, onClose]);

  if (!topic) {
    return null;
  }

  const submitNote = () => {
    if (!noteText.trim()) {
      return;
    }

    onAddNote({
      topicId: topic.id,
      topicTitle: topic.title,
      municipality: topic.municipality,
      text: noteText.trim(),
      mark: noteMark,
    });

    setNoteText("");
    setNoteMark("Обязательно");
    setNoteOpen(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(event) => event.stopPropagation()}>
        <button type="button" className="icon-button close-button" onClick={onClose} aria-label="Закрыть">
          ✕
        </button>

        <header className="modal-header">
          <h3>{topic.title}</h3>
          <div className="modal-meta">
            <Badge text={topic.priority} tone={getPriorityTone(topic.priority)} />
            <span>Интегральный балл: {topic.score}</span>
            <span>{topic.periodLabel}</span>
            <button
              type="button"
              className="ghost-button note-button"
              onClick={() => setNoteOpen((current) => !current)}
            >
              🗒 Добавить заметку
            </button>
          </div>
        </header>

        {noteOpen && (
          <div className="note-box">
            <label>
              Тип пометки
              <SelectField
                ariaLabel="Тип пометки"
                value={noteMark}
                onChange={setNoteMark}
                options={[
                  { value: "Обязательно", label: "Обязательно" },
                  { value: "Необязательно", label: "Необязательно" },
                ]}
              />
            </label>
            <label>
              Заметка
              <textarea
                value={noteText}
                onChange={(event) => setNoteText(event.target.value)}
                placeholder="Добавьте рабочую заметку по теме"
                rows={3}
              />
            </label>
            <div className="problem-actions">
              <button type="button" className="secondary-button" onClick={submitNote}>
                Сохранить в блокнот
              </button>
            </div>
          </div>
        )}

        <div className="modal-grid">
          <section className="modal-section">
            <h4>Нейтральная сводка</h4>
            <p>{topic.summary}</p>
            <div className="topic-meta-grid">
              <div>
                <span>Отрасль</span>
                <strong>{topic.sector}</strong>
              </div>
              <div>
                <span>География</span>
                <strong>{topic.municipality}</strong>
              </div>
              <div>
                <span>Источников</span>
                <strong>{topic.sourceCount}</strong>
              </div>
              <div>
                <span>Официальный сигнал</span>
                <strong>{topic.officialSignal ? "Да" : "Нет"}</strong>
              </div>
            </div>
          </section>

          <section className="modal-section">
            <h4>Почему тема в топе</h4>
            <p>{topic.whyTop}</p>
            <div className="factor-list">
              {Object.entries(topic.factors).map(([key, value]) => (
                <div className="factor-item" key={key}>
                  <span>{FACTOR_LABELS[key]}</span>
                  <div className="factor-track">
                    <div className="factor-fill" style={{ width: `${value}%` }} />
                  </div>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          </section>

          <section className="modal-section">
            <h4>Источники</h4>
            <ul className="plain-list">
              {topic.sources.map((source) => (
                <li key={`${source.name}-${source.timestamp}`}>
                  <span>{source.name}</span>
                  <small>{source.type}</small>
                  <small>{source.timestamp}</small>
                </li>
              ))}
            </ul>
          </section>

          <section className="modal-section">
            <h4>Фрагменты подтверждений</h4>
            <ul className="snippet-list">
              {topic.snippets.map((snippet) => (
                <li key={snippet}>{snippet}</li>
              ))}
            </ul>
            <div className="status-pair">
              <Badge text={topic.contradiction ? "Есть противоречие" : "Противоречий не выявлено"} tone={topic.contradiction ? "high" : "neutral"} />
              <Badge text={topic.spamRisk ? "Есть риск спама/ботов" : "Риск спама низкий"} tone={topic.spamRisk ? "high" : "neutral"} outlined />
            </div>
          </section>

          <section className="modal-section modal-full">
            <h4>Таймлайн развития темы</h4>
            <ol className="timeline">
              {topic.timeline.map((item) => (
                <li key={`${item.date}-${item.event}`}>
                  <span>{item.date}</span>
                  <p>{item.event}</p>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>
    </div>
  );
}
