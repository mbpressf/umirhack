import { useEffect, useMemo, useRef, useState } from "react";

function toOption(item) {
  if (typeof item === "string") {
    return { value: item, label: item };
  }
  return item;
}

export default function SelectField({
  options,
  value,
  onChange,
  placeholder,
  ariaLabel,
  className = "",
  disabled = false,
}) {
  const rootRef = useRef(null);
  const [isOpen, setIsOpen] = useState(false);

  const normalizedOptions = useMemo(() => options.map(toOption), [options]);
  const selected = normalizedOptions.find((item) => item.value === value);
  const label = selected?.label ?? placeholder ?? "";

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    const handlePointerDown = (event) => {
      if (!rootRef.current?.contains(event.target)) {
        setIsOpen(false);
      }
    };

    const handleEscape = (event) => {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    };

    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen]);

  return (
    <div ref={rootRef} className={`select-field ${isOpen ? "open" : ""} ${disabled ? "disabled" : ""}`}>
      <button
        type="button"
        className={`select-field-trigger ${className}`.trim()}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        disabled={disabled}
        onClick={() => setIsOpen((current) => !current)}
      >
        <span className={`select-field-value ${selected ? "" : "placeholder"}`}>{label}</span>
        <span className="select-field-chevron" aria-hidden />
      </button>

      {isOpen && (
        <div className="select-field-menu" role="listbox" aria-label={ariaLabel}>
          {normalizedOptions.map((option) => {
            const active = option.value === value;
            return (
              <button
                key={`${option.value}`}
                type="button"
                role="option"
                aria-selected={active}
                className={`select-field-option ${active ? "active" : ""}`}
                onClick={() => {
                  onChange(option.value);
                  setIsOpen(false);
                }}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
