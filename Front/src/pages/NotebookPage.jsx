import { useMemo, useState } from "react";
import SelectField from "../components/common/SelectField";

const DEFAULT_MARK = "Обязательно";

export default function NotebookPage({
  notes,
  availableNews = [],
  onCreateNote,
  onDeleteNote,
  onClearNotes,
  locale = "ru",
}) {
  const isRu = locale === "ru";
  const [filter, setFilter] = useState("Все");
  const [modalOpen, setModalOpen] = useState(false);
  const [newsQuery, setNewsQuery] = useState("");
  const [selectedNewsId, setSelectedNewsId] = useState("");
  const [text, setText] = useState("");
  const [mark, setMark] = useState(DEFAULT_MARK);
  const [isNewsOpen, setIsNewsOpen] = useState(false);

  const visibleNotes = useMemo(
    () => notes.filter((note) => (filter === "Все" ? true : note.mark === filter)),
    [filter, notes],
  );

  const importantNews = useMemo(() => {
    return [...availableNews]
      .sort((a, b) => {
        const aRank = a.rank ?? Number.POSITIVE_INFINITY;
        const bRank = b.rank ?? Number.POSITIVE_INFINITY;
        if (aRank !== bRank) {
          return aRank - bRank;
        }
        return (b.score ?? 0) - (a.score ?? 0);
      })
      .slice(0, 5);
  }, [availableNews]);

  const filteredNews = useMemo(() => {
    const query = newsQuery.trim().toLowerCase();
    if (!query) {
      return importantNews;
    }
    return availableNews
      .filter((item) =>
        [item.title, item.summary, item.municipality].join(" ").toLowerCase().includes(query),
      )
      .slice(0, 8);
  }, [availableNews, importantNews, newsQuery]);

  const resetModalFields = () => {
    setNewsQuery("");
    setSelectedNewsId("");
    setText("");
    setMark(DEFAULT_MARK);
    setIsNewsOpen(false);
  };

  const openCreateModal = () => {
    resetModalFields();
    setModalOpen(true);
  };

  const closeCreateModal = () => {
    setModalOpen(false);
  };

  const selectNews = (item) => {
    setSelectedNewsId(item.id);
    setNewsQuery(item.title);
    setIsNewsOpen(false);
  };

  const clearLinkedNews = () => {
    setSelectedNewsId("");
    setNewsQuery("");
    setIsNewsOpen(false);
  };

  const submitNote = () => {
    if (!text.trim()) {
      return;
    }

    const selectedNews = availableNews.find((item) => item.id === selectedNewsId) ?? null;
    onCreateNote({
      selectedNews,
      text: text.trim(),
      mark,
    });

    setModalOpen(false);
    resetModalFields();
  };

  return (
    <div className="page">
      <div className="card toolbar">
        <h2>Блокнот</h2>
        <div className="filters-grid">
          <SelectField
            className="page-compact-control"
            ariaLabel="Фильтр заметок"
            value={filter}
            onChange={setFilter}
            options={[
              { value: "Все", label: "Фильтр заметок" },
              { value: "Обязательно", label: "Обязательно" },
              { value: "Необязательно", label: "Необязательно" },
            ]}
          />
          <div className="filter-counter">{visibleNotes.length} заметок</div>
          <div className="notebook-toolbar-actions">
            <button type="button" className="primary-button" onClick={openCreateModal}>
              {isRu ? "Создать заметку" : "Create note"}
            </button>
            <button type="button" className="ghost-button" onClick={onClearNotes} disabled={!notes.length}>
              {isRu ? "Очистить блокнот" : "Clear notebook"}
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
                {isRu ? "Удалить" : "Delete"}
              </button>
            </div>
          </article>
        ))}
      </div>

      {!visibleNotes.length && <div className="card empty-state">{isRu ? "В блокноте пока нет заметок." : "No notes yet."}</div>}

      {modalOpen && (
        <div className="modal-overlay" onClick={closeCreateModal}>
          <div className="modal-card notebook-modal-card" onClick={(event) => event.stopPropagation()}>
            <button type="button" className="icon-button close-button" onClick={closeCreateModal}>
              ×
            </button>

            <div className="notebook-modal-head">
              <h3>{isRu ? "Создать заметку" : "Create note"}</h3>
              <p>
                {isRu
                  ? "Выберите новость из списка или оставьте заметку без привязки."
                  : "Pick a news item or keep the note unlinked."}
              </p>
            </div>

            <div className="note-box notebook-modal-form">
              <div className="filters-grid notebook-modal-filters">
                <div className="notebook-news-picker">
                  <input
                    className="page-compact-control"
                    type="search"
                    value={newsQuery}
                    onFocus={() => setIsNewsOpen(true)}
                    onBlur={() => {
                      window.setTimeout(() => setIsNewsOpen(false), 120);
                    }}
                    onChange={(event) => {
                      setNewsQuery(event.target.value);
                      setSelectedNewsId("");
                      setIsNewsOpen(true);
                    }}
                    placeholder={isRu ? "Поиск" : "Search"}
                  />

                  {isNewsOpen && (
                    <div className="notebook-news-list">
                      <button
                        type="button"
                        className={`notebook-news-item ${selectedNewsId === "" ? "active" : ""}`}
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={clearLinkedNews}
                      >
                        {isRu ? "Без привязки к новости" : "Without linked news"}
                      </button>

                      {filteredNews.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          className={`notebook-news-item ${selectedNewsId === item.id ? "active" : ""}`}
                          onMouseDown={(event) => event.preventDefault()}
                          onClick={() => selectNews(item)}
                        >
                          {item.title}
                        </button>
                      ))}

                      {!filteredNews.length && (
                        <div className="notebook-news-empty">{isRu ? "Ничего не найдено" : "No matches found"}</div>
                      )}
                    </div>
                  )}
                </div>

                <SelectField
                  className="page-compact-control"
                  ariaLabel={isRu ? "Обязательность" : "Importance"}
                  value={mark}
                  onChange={setMark}
                  options={[
                    { value: "Обязательно", label: "Обязательно" },
                    { value: "Необязательно", label: "Необязательно" },
                  ]}
                />
              </div>

              <label className="notebook-modal-label">
                {isRu ? "Текст заметки" : "Note text"}
                <textarea
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  placeholder={isRu ? "Введите текст заметки" : "Type your note"}
                />
              </label>
            </div>

            <div className="notebook-create-actions">
              <button type="button" className="primary-button" onClick={submitNote} disabled={!text.trim()}>
                {isRu ? "Создать заметку" : "Create note"}
              </button>
              <button type="button" className="ghost-button" onClick={closeCreateModal}>
                {isRu ? "Отмена" : "Cancel"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
