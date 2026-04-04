import { useMemo, useState } from "react";

export default function NotebookPage({ notes, onDeleteNote, onClearNotes }) {
  const [filter, setFilter] = useState("Все");

  const visibleNotes = useMemo(
    () => notes.filter((note) => (filter === "Все" ? true : note.mark === filter)),
    [filter, notes],
  );

  return (
    <div className="page">
      <div className="card toolbar">
        <h2>Блокнот</h2>
        <div className="filters-grid">
          <label>
            Фильтр
            <select value={filter} onChange={(event) => setFilter(event.target.value)}>
              {["Все", "Обязательно", "Необязательно"].map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <div className="filter-counter">{visibleNotes.length} заметок</div>
          <div className="report-actions">
            <button
              type="button"
              className="ghost-button"
              onClick={onClearNotes}
              disabled={!notes.length}
            >
              Очистить блокнот
            </button>
          </div>
        </div>
      </div>

      <div className="cards-stack">
        {visibleNotes.map((note) => (
          <article key={note.id} className="card notebook-note animate-in">
            <div className="note-head">
              <strong>{note.topicTitle}</strong>
              <span>{note.mark}</span>
            </div>
            <p>{note.text}</p>
            <div className="problem-meta">
              <span>{note.region}</span>
              <span>{note.municipality}</span>
              <span>{note.createdAt}</span>
            </div>
            <div className="problem-actions">
              <button type="button" className="ghost-button" onClick={() => onDeleteNote(note.id)}>
                Удалить
              </button>
            </div>
          </article>
        ))}
      </div>

      {!visibleNotes.length && (
        <div className="card empty-state">
          В блокноте пока нет заметок. Откройте тему и нажмите кнопку блокнота для добавления.
        </div>
      )}
    </div>
  );
}
