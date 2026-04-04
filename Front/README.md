# Сигнал — frontend-прототип

Интерактивный frontend-концепт аналитической платформы «Сигнал» для мониторинга проблем региона (MVP на моковых данных, без backend).

Текущий пилот в данных: **Ростовская область**.

## Стек

- React 18
- Vite 5
- Чистый CSS

## Требования

- Node.js **20+** (LTS рекомендуется)
- npm (идет вместе с Node.js)

Проверка:

```bash
node -v
npm -v
```

## Запуск у себя

1. Открыть проект в терминале:

```bash
cd signal-frontend
```

2. Установить зависимости:

```bash
npm install
```

3. Запустить dev-сервер:

```bash
npm run dev
```

4. Открыть в браузере:

`http://localhost:5173`

## Production-сборка

```bash
npm run build
npm run preview
```

## Если в PowerShell ошибка «npm не распознано»

Установить Node.js LTS:

```powershell
winget install OpenJS.NodeJS.LTS
```

Перезапустить терминал и проверить:

```powershell
node -v
npm -v
```

Если блокируется `npm.ps1`, запускать так:

```powershell
npm.cmd install
npm.cmd run dev
```

## Как передать проект другу (правильно)

Перед отправкой **не включай** в архив:

- `node_modules`
- `dist`

Передавать нужно исходники:

- `src`
- `public`
- `package.json`
- `package-lock.json`
- `vite.config.js`
- `index.html`
- `README.md`
- `HANDOFF.md` (если нужен контекст по проекту)

После получения другу достаточно:

```bash
npm install
npm run dev
```

## Основные разделы интерфейса

- Обзор
- Топ проблем
- Темы и события
- Тренды
- Источники
- География
- Отчёты
- Блокнот
- Профиль (MVP-экран)
- Настройки
- Выбор региона

## Важно про MVP

- Это frontend-прототип: данные моковые.
- Реальные API/авторизация/серверный экспорт в текущей версии не подключены.

