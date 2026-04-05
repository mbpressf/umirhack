import { useEffect, useState } from "react";
import { loginUser, registerUser } from "../lib/api";

const AUTH_STORAGE_KEY = "signal:auth-user";

const COPY = {
  ru: {
    title: "Профиль и доступ",
    signedInAs: "Вы вошли как",
    signedOutText:
      "Войдите или зарегистрируйтесь, чтобы сохранить историю диалогов, пользоваться AI-ассистентом и работать с персональными настройками.",
    signIn: "Войти",
    register: "Регистрация",
    signOut: "Выйти",
    registerSuccess: "Регистрация прошла успешно.",
    loginSuccess: "Вход выполнен.",
    logoutSuccess: "Вы вышли из профиля.",
    authError: "Ошибка авторизации",
    loginLabel: "Почта или телефон",
    passwordLabel: "Пароль",
    confirmPasswordLabel: "Подтвердите пароль",
    modalLogin: "Вход",
    modalRegister: "Регистрация",
    submitting: "Отправка...",
    featureTitle: "Что откроется после входа",
    features: [
      "История диалогов с AI-ассистентом",
      "Персональные настройки интерфейса",
      "Сохранение заметок и рабочих сценариев",
    ],
  },
  en: {
    title: "Profile and access",
    signedInAs: "Signed in as",
    signedOutText:
      "Sign in or register to keep chat history, use the AI assistant, and save personal settings.",
    signIn: "Sign in",
    register: "Register",
    signOut: "Sign out",
    registerSuccess: "Registration completed.",
    loginSuccess: "Signed in successfully.",
    logoutSuccess: "You are signed out.",
    authError: "Authentication error",
    loginLabel: "Email or phone",
    passwordLabel: "Password",
    confirmPasswordLabel: "Confirm password",
    modalLogin: "Sign in",
    modalRegister: "Register",
    submitting: "Submitting...",
    featureTitle: "What unlocks after sign-in",
    features: [
      "Conversation history with the AI assistant",
      "Personal interface settings",
      "Saved notes and work context",
    ],
  },
};

export default function ProfilePage({ locale = "ru", onNotify }) {
  const copy = COPY[locale] ?? COPY.ru;
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
      onNotify(authMode === "register" ? copy.registerSuccess : copy.loginSuccess);
    } catch (submitError) {
      setError(submitError.message || copy.authError);
    } finally {
      setSubmitting(false);
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(AUTH_STORAGE_KEY);
    onNotify(copy.logoutSuccess);
  };

  return (
    <div className="page">
      <section className="card auth-card auth-card-grid animate-in">
        <div className="auth-card-copy">
          <span className="section-kicker">Access</span>
          <h2>{copy.title}</h2>
          {user ? (
            <>
              <p>
                {copy.signedInAs} <strong>{user.login}</strong>
              </p>
              <div className="problem-actions">
                <button type="button" className="ghost-button" onClick={logout}>
                  {copy.signOut}
                </button>
              </div>
            </>
          ) : (
            <>
              <p>{copy.signedOutText}</p>
              <div className="problem-actions">
                <button type="button" className="primary-button" onClick={() => openModal("login")}>
                  {copy.signIn}
                </button>
                <button type="button" className="secondary-button" onClick={() => openModal("register")}>
                  {copy.register}
                </button>
              </div>
            </>
          )}
        </div>

        <div className="auth-side-panel">
          <h3>{copy.featureTitle}</h3>
          <ul className="chat-feature-list">
            {copy.features.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </section>

      {modalOpen ? (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-card auth-modal-card" onClick={(event) => event.stopPropagation()}>
            <button
              type="button"
              className="icon-button close-button"
              onClick={closeModal}
              disabled={submitting}
            >
              ×
            </button>
            <h3>{authMode === "register" ? copy.modalRegister : copy.modalLogin}</h3>

            <div className="segmented auth-mode-switch">
              <button
                type="button"
                className={authMode === "login" ? "active" : ""}
                onClick={() => setAuthMode("login")}
                disabled={submitting}
              >
                {copy.signIn}
              </button>
              <button
                type="button"
                className={authMode === "register" ? "active" : ""}
                onClick={() => setAuthMode("register")}
                disabled={submitting}
              >
                {copy.register}
              </button>
            </div>

            <form className="auth-form" onSubmit={onSubmit}>
              <input
                type="text"
                value={form.login}
                onChange={onChange("login")}
                placeholder={copy.loginLabel}
                autoComplete="username"
                required
              />
              <input
                type="password"
                value={form.password}
                onChange={onChange("password")}
                placeholder={copy.passwordLabel}
                autoComplete={authMode === "register" ? "new-password" : "current-password"}
                required
              />
              {authMode === "register" ? (
                <input
                  type="password"
                  value={form.passwordConfirm}
                  onChange={onChange("passwordConfirm")}
                  placeholder={copy.confirmPasswordLabel}
                  autoComplete="new-password"
                  required
                />
              ) : null}
              {error ? <p className="auth-error">{error}</p> : null}
              <div className="auth-submit">
                <button type="submit" className="primary-button" disabled={submitting}>
                  {submitting
                    ? copy.submitting
                    : authMode === "register"
                      ? copy.register
                      : copy.signIn}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
