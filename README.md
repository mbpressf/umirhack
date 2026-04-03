# Madrigal Regional Pulse

Локальный MVP для хакатонного кейса: сбор публичных сообщений региона, дедупликация, объяснимый `top-10` проблем и дашборд для ЛПР.

## Что внутри

- `FastAPI` API для ingest, топа тем, карточек тем и трендов
- `SQLite (WAL)` как локальная база событий
- `Streamlit`-дашборд с фильтрами, explainable score и экспортом
- `seeded dataset` по Ростову-на-Дону и Ростовской области
- live-адаптеры для `RSS`, HTML-новостей, публичных Telegram-каналов и `VK API`
- `source catalog` для data-команды и `monitoring agent` для авто-сводок
- `manual import` для `CSV/JSON/JSONL`, чтобы быстро докидывать выгрузки из внешних систем

## Быстрый старт

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\uvicorn madrigal_assistant.api.app:app --reload
```

Во втором терминале:

```powershell
.venv\Scripts\streamlit run madrigal_assistant/dashboard/app.py
```

## Первый запуск

1. Откройте API на `http://127.0.0.1:8000/docs`
2. Выполните `POST /api/import/seed`, чтобы загрузить demo snapshot
3. По желанию вызовите `POST /api/ingest/run` для подтягивания live-источников Ростовской области
4. Откройте Streamlit и работайте с вкладками `Top-10`, `Topic card`, `Trends`, `Source drill-down`, `Export`

## Data Kit

Основной live-конфиг:
- `config/demo_region.rostov.json`

Полный каталог источников для data-команды:
- `config/source_catalog.rostov.json`

Папка для ручных выгрузок:
- `datasets/rostov/manual/`

Собрать свежий датасет, source health и briefing:

```powershell
.venv\Scripts\python scripts/collect_rostov_dataset.py --reset-db
```

После этого артефакты появятся в:
- `datasets/rostov/raw/`
- `datasets/rostov/catalog/`
- `datasets/rostov/briefings/`

Чтобы вручную докинуть выгрузки перед сборкой:

```powershell
.venv\Scripts\python scripts/collect_rostov_dataset.py --manual-input D:\path\to\vk_dump.json --manual-input D:\path\to\appeals.csv
```

Все `json/jsonl/csv` из `datasets/rostov/manual/` тоже подхватываются автоматически.

Запустить только агент-сводчик поверх текущей БД:

```powershell
.venv\Scripts\python scripts/run_monitoring_agent.py
```

## Что делает агент

`MonitoringAgent` не зависит от внешних LLM и собирает:
- executive summary по текущему top-10
- срочные темы для показа
- список тем с противоречиями
- source health после ingest
- backlog следующих источников на подключение

## Дефолтный регион

По умолчанию проект настроен на `Ростовскую область`.
Регион можно заменить через `MADRIGAL_CONFIG_PATH` и `MADRIGAL_SEED_PATH`.

## VK и MAX

- `VK` теперь поддерживается как live-источник через `VK API`. Чтобы включить `stable` VK-источники из каталога, задайте `VK_API_TOKEN`.
- `MAX` в проекте пока оставлен как `manual import`-контур. Это безопаснее для хакатона, чем завязывать demo на внешний API, который ещё нужно отдельно проверять и стабилизировать.
