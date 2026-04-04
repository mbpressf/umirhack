import { useEffect, useState } from "react";
import { loginUser, registerUser } from "../lib/api";

const AUTH_STORAGE_KEY = "signal:auth-user";

export default function ProfilePage({ locale = "ru", onNotify }) {
  const isRu = locale === "ru";
  const [authMode, setAuthMode] = useState("login");
  const [modalOpen, setModalOpen] = useState(false);
  const [user, setUser] = useState(null);
  const [form, setForm] = useState({ login: "", password: "", passwordConfirm: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    try {
      const raw = localStorage.getItem(AUTH_STORAGE_KEY);
      setUser(raw ? JSON.parse(raw) : null);
    } catch (readError) {
      setUser(null);
    }
  }, []);

  const openModal = (mode) => {
    setAuthMode(mode);
    setForm({ login: "", password: "", passwordConfirm: "" });
    setError("");
    setModalOpen(true);
  };

  const closeModal = () => {
    if (!submitting) {
      setModalOpen(false);
      setError("");
    }
  };

  const onChange = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
  };

  const onSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      const payload =
        authMode === "register"
          ? {
              login: form.login,
              password: form.password,
              password_confirm: form.passwordConfirm,
            }
          : {
              login: form.login,
              password: form.password,
            };

      const response = authMode === "register" ? await registerUser(payload) : await loginUser(payload);
      setUser(response.user);
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(response.user));
      setModalOpen(false);
      onNotify(authMode === "register" ? "Регистрация успешна." : "Вход выполнен.");
    } catch (submitError) {
      setError(submitError.message || "Ошибка авторизации");
    } finally {
      setSubmitting(false);
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(AUTH_STORAGE_KEY);
    onNotify(isRu ? "Вы вышли из профиля." : "You are signed out.");
  };

  return (
    <div className="page">
      <div className="card auth-card animate-in">
        <h2>{isRu ? "Профиль" : "Profile"}</h2>
        {user ? (
          <>
            <p>
              {isRu ? "Вы вошли как" : "Signed in as"} <strong>{user.login}</strong>
            </p>
            <div className="problem-actions">
              <button type="button" className="ghost-button" onClick={logout}>
                {isRu ? "Выйти" : "Sign out"}
              </button>
            </div>
          </>
        ) : (
          <>
            <p>
              {isRu
                ? "Войдите или зарегистрируйтесь, чтобы сохранить персональные настройки."
                : "Sign in or register to keep personal settings."}
            </p>
            <div className="problem-actions">
              <button type="button" className="primary-button" onClick={() => openModal("login")}>
                {isRu ? "Войти" : "Sign in"}
              </button>
              <button type="button" className="secondary-button" onClick={() => openModal("register")}>
                {isRu ? "Регистрация" : "Register"}
              </button>
            </div>
          </>
        )}
      </div>

      {modalOpen && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-card auth-modal-card" onClick={(event) => event.stopPropagation()}>
            <button type="button" className="icon-button close-button" onClick={closeModal} disabled={submitting}>
              ×
            </button>
            <h3>{authMode === "register" ? (isRu ? "Регистрация" : "Register") : isRu ? "Вход" : "Sign in"}</h3>

            <div className="segmented auth-mode-switch">
              <button
                type="button"
                className={authMode === "login" ? "active" : ""}
                onClick={() => setAuthMode("login")}
                disabled={submitting}
              >
                {isRu ? "Вход" : "Sign in"}
              </button>
              <button
                type="button"
                className={authMode === "register" ? "active" : ""}
                onClick={() => setAuthMode("register")}
                disabled={submitting}
              >
                {isRu ? "Регистрация" : "Register"}
              </button>
            </div>

            <form className="auth-form" onSubmit={onSubmit}>
              <input
                type="text"
                value={form.login}
                onChange={onChange("login")}
                placeholder={isRu ? "Почта или телефон" : "Email or phone"}
                autoComplete="username"
                required
              />
              <input
                type="password"
                value={form.password}
                onChange={onChange("password")}
                placeholder={isRu ? "Пароль" : "Password"}
                autoComplete={authMode === "register" ? "new-password" : "current-password"}
                required
              />
              {authMode === "register" && (
                <input
                  type="password"
                  value={form.passwordConfirm}
                  onChange={onChange("passwordConfirm")}
                  placeholder={isRu ? "Подтверждение пароля" : "Confirm password"}
                  autoComplete="new-password"
                  required
                />
              )}
              {error && <p className="auth-error">{error}</p>}
              <div className="auth-submit">
                <button type="submit" className="primary-button" disabled={submitting}>
                  {submitting ? (isRu ? "Отправка..." : "Submitting...") : authMode === "register" ? (isRu ? "Зарегистрироваться" : "Register") : isRu ? "Войти" : "Sign in"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
