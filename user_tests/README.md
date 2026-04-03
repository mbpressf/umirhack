# User Tests

Эта папка нужна для наглядной ручной проверки проекта.

Здесь лежат скрипты, которые:
- читают свежие артефакты аналитики
- строят графики
- собирают простой HTML-отчёт
- помогают быстро глазами проверить, что пайплайн живой

## Что запускать

Сначала обновить датасет:

```powershell
.venv\Scripts\python scripts\collect_rostov_dataset.py --reset-db --max-per-source 4
```

Потом собрать визуальный отчёт:

```powershell
.venv\Scripts\python user_tests\build_visual_report.py
```

Если хотите открыть его как локальную страницу:

```powershell
.venv\Scripts\python user_tests\serve_visual_report.py --port 8765
```

Потом открыть:
- `http://127.0.0.1:8765/index.html`

Или одной командой:

```powershell
powershell -ExecutionPolicy Bypass -File .\user_tests\open_visual_report.ps1
```

Если нужно сначала заново пересобрать отчёт:

```powershell
powershell -ExecutionPolicy Bypass -File .\user_tests\open_visual_report.ps1 -Rebuild
```

Если нужно сразу открыть страницу с объяснением пайплайна:

```powershell
powershell -ExecutionPolicy Bypass -File .\user_tests\open_visual_report.ps1 -Page how_it_works
```

## Что получится

После запуска появится папка:
- `user_tests/output/latest/`

Там будут:
- `index.html` — главная страница визуального отчёта
- `summary.md` — короткая текстовая сводка
- `top_scores.png`
- `sector_distribution.png`
- `source_mix.png`
- `bot_vs_score.png`
- `source_health.png`

## Зачем это нужно

Это полезно для трёх вещей:
- быстро показать команде, что аналитика реально считает
- проверить глазами, не поехал ли ranking или source health
- использовать как mini-demo до полной готовности фронта
