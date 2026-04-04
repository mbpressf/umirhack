export default function ProfilePage({ locale = "ru", onNotify }) {
  const isRu = locale === "ru";

  return (
    <div className="page">
      <div className="card auth-card animate-in">
        <h2>{isRu ? "Доступ к профилю" : "Profile access"}</h2>
        <p>
          {isRu
            ? "Раздел профиля временно упрощён для MVP. Используйте вход или регистрацию."
            : "Profile section is simplified for MVP. Use sign in or registration."}
        </p>
        <div className="problem-actions">
          <button
            type="button"
            className="primary-button"
            onClick={() =>
              onNotify(isRu ? "Форма входа будет доступна на следующем этапе." : "Sign-in form comes in next stage.")
            }
          >
            {isRu ? "Войти" : "Sign in"}
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={() =>
              onNotify(
                isRu
                  ? "Форма регистрации будет доступна на следующем этапе."
                  : "Registration form comes in next stage.",
              )
            }
          >
            {isRu ? "Регистрация" : "Register"}
          </button>
        </div>
      </div>
    </div>
  );
}
