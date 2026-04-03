# Manual Import

Сюда можно складывать дополнительные выгрузки для data-layer без отдельного парсера.

Поддерживаемые форматы:
- `*.csv`
- `*.json`
- `*.jsonl`

Минимально полезные поля:
- `published_at` или `date`
- `text` или `message`
- `source_name`
- `url` или `external_id`

Дополнительные поля, которые тоже понимаются:
- `title`
- `municipality`
- `author`
- `source_type`
- `source_id`
- `engagement`
- `is_official`

Примеры имён колонок-алиасов:
- `message`, `content`, `body` вместо `text`
- `source`, `group_name`, `channel` вместо `source_name`
- `link`, `post_url`, `permalink` вместо `url`
- `published`, `created_at`, `timestamp` вместо `published_at`

Коллектор автоматически подхватит все `json/jsonl/csv` файлы из этой папки, если не передан `--skip-manual`.
