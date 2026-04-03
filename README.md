# Madrigal Regional Pulse

Локальный MVP для хакатонного кейса по Ростовской области.

Идея проекта простая: мы собираем публичные сигналы региона из новостей, Telegram, VK и ручных выгрузок, склеиваем их в темы, объяснимо ранжируем проблемы и показываем `top-10` для ЛПР в виде сайта-дашборда.

## Что это за продукт

Это не новостной сайт и не чат-бот.

Это инструмент мониторинга региона, который отвечает на вопросы:
- какие проблемы сейчас самые заметные
- где именно они происходят
- что об этом пишут люди и официальные источники
- почему тема попала в топ
- какие источники подтверждают сигнал

На демо мы должны показать не "магический ИИ", а понятную систему:
- вот сигнал
- вот первоисточники
- вот как мы его объединили с похожими сообщениями
- вот почему он важен

## Что уже есть

В текущей версии уже собран рабочий каркас продукта:

- `FastAPI` API для получения `top-issues`, карточек тем, трендов, raw events и запуска ingest
- `SQLite (WAL)` как локальная база событий
- `Streamlit`-дашборд для витрины
- seeded dataset по Ростову и Ростовской области
- live-ingest для `RSS`, `HTML`, публичных `Telegram`-каналов и `VK API`
- `manual import` для `CSV`, `JSON`, `JSONL`
- source catalog для data-команды
- monitoring agent, который собирает briefing по текущему состоянию данных

## Что мы поменяли в текущей версии

Последний большой апдейт был про data layer.

Сделано:
- расширен каталог источников Ростовской области до `39` позиций
- введён единый `source catalog` со статусами `stable`, `candidate`, `blocked`
- live-конфиг теперь строится из каталога автоматически, а не поддерживается в двух местах вручную
- добавлен `manual import`, чтобы можно было руками докидывать выгрузки из VK, MAX, таблиц, порталов обращений и других внешних систем
- добавлена поддержка `VK API` как live-источника через `VK_API_TOKEN`
- MAX оставлен как `manual import`-контур, чтобы не ломать MVP зависимостью от нестабильной внешней интеграции
- collector теперь умеет автоматически подхватывать файлы из папки ручных выгрузок

Итог: у нас теперь не только парсеры, а нормальная база сигналов, которую можно быстро расширять.

## Текущее состояние data layer

Сейчас в проекте:
- `39` источников в полном каталоге
- `20 stable`
- `15 candidate`
- `4 blocked`

Без `VK_API_TOKEN` live-сборка использует стабильные источники из `RSS`, `HTML` и `Telegram`.

Если добавить `VK_API_TOKEN`, то автоматически подключатся и live-источники `VK`, которые помечены как `stable`.

## Архитектура проекта

### 1. Сбор данных

Источники:
- медиа
- официальные каналы
- социальные сигналы
- ручные выгрузки

Поддерживаемые типы ingest:
- `rss`
- `html`
- `telegram`
- `vk_api`
- `manual_import`

### 2. Нормализация

Все входящие данные приводятся к `RawEvent`:
- `event_id`
- `url`
- `source_type`
- `source_name`
- `published_at`
- `text`
- `title`
- `author`
- `municipality`
- `engagement`
- `is_official`
- `metadata`

### 3. Аналитика

Поверх raw events строится аналитический слой:
- дедупликация похожих сообщений
- объединение в темы
- секторная классификация
- извлечение географии
- explainable ranking
- `bot_score`
- `contradiction_flag`
- extractive summary

### 4. Витрина

На фронт и в API выдаются:
- `top-10`
- карточка темы
- тренды
- raw events
- экспорт

## Ключевые файлы

API:
- [D:/umirhack/madrigal_assistant/api/app.py](D:/umirhack/madrigal_assistant/api/app.py)

Сервисный слой:
- [D:/umirhack/madrigal_assistant/services/application.py](D:/umirhack/madrigal_assistant/services/application.py)

Ingest:
- [D:/umirhack/madrigal_assistant/ingest/service.py](D:/umirhack/madrigal_assistant/ingest/service.py)

Аналитика:
- [D:/umirhack/madrigal_assistant/analytics/service.py](D:/umirhack/madrigal_assistant/analytics/service.py)

Dashboard:
- [D:/umirhack/madrigal_assistant/dashboard/app.py](D:/umirhack/madrigal_assistant/dashboard/app.py)

Live-конфиг региона:
- [D:/umirhack/config/demo_region.rostov.json](D:/umirhack/config/demo_region.rostov.json)

Полный каталог источников:
- [D:/umirhack/config/source_catalog.rostov.json](D:/umirhack/config/source_catalog.rostov.json)

Скрипт сборки датасета:
- [D:/umirhack/scripts/collect_rostov_dataset.py](D:/umirhack/scripts/collect_rostov_dataset.py)

Агент-сводчик:
- [D:/umirhack/scripts/run_monitoring_agent.py](D:/umirhack/scripts/run_monitoring_agent.py)

Папка для ручных выгрузок:
- [D:/umirhack/datasets/rostov/manual](D:/umirhack/datasets/rostov/manual)

## Как запускать

Создать окружение и установить зависимости:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
```

Поднять API:

```powershell
.venv\Scripts\uvicorn madrigal_assistant.api.app:app --reload
```

Поднять dashboard:

```powershell
.venv\Scripts\streamlit run madrigal_assistant/dashboard/app.py
```

Запустить тесты:

```powershell
.venv\Scripts\python -m pytest
```

## Как обновлять данные

### Базовая сборка

```powershell
.venv\Scripts\python scripts\collect_rostov_dataset.py --reset-db
```

### С ручными выгрузками

Можно просто положить файлы в папку:
- [D:/umirhack/datasets/rostov/manual](D:/umirhack/datasets/rostov/manual)

Поддерживаются:
- `*.csv`
- `*.json`
- `*.jsonl`

Или передать файлы напрямую:

```powershell
.venv\Scripts\python scripts\collect_rostov_dataset.py --manual-input D:\path\to\vk_dump.json --manual-input D:\path\to\appeals.csv
```

### Что получится на выходе

Артефакты сборки лежат в:
- [D:/umirhack/datasets/rostov/raw](D:/umirhack/datasets/rostov/raw)
- [D:/umirhack/datasets/rostov/catalog](D:/umirhack/datasets/rostov/catalog)
- [D:/umirhack/datasets/rostov/briefings](D:/umirhack/datasets/rostov/briefings)

Главные файлы:
- [D:/umirhack/datasets/rostov/raw/latest_raw_events.jsonl](D:/umirhack/datasets/rostov/raw/latest_raw_events.jsonl)
- [D:/umirhack/datasets/rostov/raw/latest_top_issues.json](D:/umirhack/datasets/rostov/raw/latest_top_issues.json)
- [D:/umirhack/datasets/rostov/raw/latest_problem_cards.json](D:/umirhack/datasets/rostov/raw/latest_problem_cards.json)
- [D:/umirhack/datasets/rostov/raw/latest_source_stats.json](D:/umirhack/datasets/rostov/raw/latest_source_stats.json)
- [D:/umirhack/datasets/rostov/raw/latest_manual_imports.json](D:/umirhack/datasets/rostov/raw/latest_manual_imports.json)
- [D:/umirhack/datasets/rostov/briefings/latest_briefing.md](D:/umirhack/datasets/rostov/briefings/latest_briefing.md)

## Как работает manual import

Manual import нужен для ситуаций, когда:
- нет готового live-парсера
- есть выгрузка из внешней системы
- нужно быстро добить датасет перед демо
- нужно подгрузить исторические данные

Поддерживаются алиасы полей, так что не обязательно строго соблюдать одну схему.

Минимально полезно иметь:
- `published_at` или `date`
- `text` или `message`
- `source_name` или `source`
- `url` или `external_id`

Если некоторых полей нет, сервис старается достроить их автоматически.

## Что с VK

`VK` уже встроен в текущую архитектуру.

Что сделано:
- добавлен fetcher `vk_api`
- в каталог добавлены stable и candidate VK-источники по Ростову
- включение зависит от переменной окружения `VK_API_TOKEN`

Если токен есть, VK становится нормальной частью live-ingest.

Если токена нет, можно грузить VK через `manual import`.

## Что с MAX

`MAX` пока не делаем live-парсером по умолчанию.

Почему:
- для хакатона опасно завязывать demo на интеграцию, которую ещё надо отдельно стабилизировать
- нам важнее широкий и надёжный data layer, чем красивая, но хрупкая интеграция

Текущее решение:
- `MAX` хранится в source catalog как `manual_import`-источник
- данные из MAX можно догружать файлами
- если позже найдём устойчивый и удобный публичный контур для сбора, вынесем в отдельный fetcher

## Что уже готово для фронта

Фронтенд уже может брать данные либо из API, либо из готовых JSON-артефактов.

Главное для фронта:
- `top issues`
- карточка темы
- тренды
- raw events
- export
- source health

Если фронт хочет брать уже готовый файл, то главный вход сейчас:
- [D:/umirhack/datasets/rostov/raw/latest_top_issues.json](D:/umirhack/datasets/rostov/raw/latest_top_issues.json)
- [D:/umirhack/datasets/rostov/raw/latest_problem_cards.json](D:/umirhack/datasets/rostov/raw/latest_problem_cards.json)

## Что мы делаем дальше

Следующий главный фокус не на новые парсеры ради галочки, а на качество сигналов.

### Приоритет 1

Улучшить аналитику:
- лучше склеивать одинаковые жалобы из `Telegram`, `VK`, `media`
- чище отделять реальную проблему от инфошума
- улучшить `bot_penalty`
- усилить `contradiction_flag`

### Приоритет 2

Сделать более полезный output для фронта:
- отдельный `problem_cards.json`
- более удобный contract для карточек проблем
- готовые explanation-блоки для why-in-top

### Приоритет 3

Добить data coverage:
- добавить ещё candidate-источники в live после быстрой проверки
- подгрузить ручные выгрузки из `VK`, `MAX`, обращений, hotlines, open data
- посмотреть, какие районы Ростовской области пока недопокрыты

## Что ещё нужно сделать

Обязательные задачи:
- улучшить дедупликацию
- сделать отдельный output для карточек проблем
- усилить ranking под реальные региональные жалобы
- добавить больше evidence в карточки тем
- улучшить фильтрацию локальной релевантности

Желательные задачи:
- карта по муниципалитетам
- экспорт отчёта в более удобном виде
- health dashboard по источникам
- статус last sync по каждому источнику

## Разделение по команде

### Ты + Максим

Основной контур:
- источники
- выгрузки
- дедупликация
- ranking
- карточки проблем
- AI/аналитика

### Фронт

Фокус:
- главная витрина
- карточка темы
- фильтры
- визуализация score
- тренды
- экспортный экран

### Человек по фишкам

Фокус:
- карта
- source health
- дополнительные виджеты
- polish для демо
- сценарий показа

## Быстрый рабочий сценарий

Если нужно просто продолжать разработку без долгого вникания:

1. Запустить тесты
2. Пересобрать датасет
3. Проверить `latest_top_issues.json`
4. Если есть новые выгрузки, положить их в `datasets/rostov/manual`
5. Повторно прогнать collector
6. После этого уже дорабатывать аналитику или фронт

## Что важно помнить

- продукт делается под demo и объяснимость
- нам не нужен идеальный production
- нам нужен убедительный `top-10`
- каждый важный сигнал должен иметь evidence
- любой источник, который может сломать demo, лучше держать как `candidate` или `manual`

Если коротко: сейчас проект уже умеет собирать и показывать сигналы региона, а следующий этап для нас это сделать аналитику сильнее и подготовить данные в максимально удобном виде для фронта и демо.
