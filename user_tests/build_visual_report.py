from __future__ import annotations

import base64
import json
import shutil
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "datasets" / "rostov" / "raw"
OUTPUT_ROOT = ROOT_DIR / "user_tests" / "output"
SHAREABLE_ROOT = ROOT_DIR / "user_tests" / "shareable"

TOP_ISSUES_PATH = RAW_DIR / "latest_top_issues.json"
PROBLEM_CARDS_PATH = RAW_DIR / "latest_problem_cards.json"
SOURCE_STATS_PATH = RAW_DIR / "latest_source_stats.json"
RAW_EVENTS_PATH = RAW_DIR / "latest_raw_events.jsonl"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def ensure_paths() -> None:
    missing = [path for path in (TOP_ISSUES_PATH, PROBLEM_CARDS_PATH, SOURCE_STATS_PATH, RAW_EVENTS_PATH) if not path.exists()]
    if missing:
        joined = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(
            "Не найдены артефакты аналитики: "
            f"{joined}. Сначала запустите scripts/collect_rostov_dataset.py."
        )


def prepare_output_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = OUTPUT_ROOT / timestamp
    latest_dir = OUTPUT_ROOT / "latest"
    run_dir.mkdir(parents=True, exist_ok=True)
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    latest_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def copy_to_latest(run_dir: Path) -> Path:
    latest_dir = OUTPUT_ROOT / "latest"
    for item in run_dir.iterdir():
        shutil.copy2(item, latest_dir / item.name)
    return latest_dir


def publish_shareable(run_dir: Path) -> Path:
    if SHAREABLE_ROOT.exists():
        shutil.rmtree(SHAREABLE_ROOT)
    SHAREABLE_ROOT.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "how_it_works.html", "summary.md", "visual_report_bundle.zip"):
        shutil.copy2(run_dir / name, SHAREABLE_ROOT / name)
    return SHAREABLE_ROOT


def embed_png(path: Path) -> str:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{payload}"


def setup_matplotlib() -> None:
    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "#f7fafc"
    plt.rcParams["axes.facecolor"] = "#ffffff"
    plt.rcParams["axes.edgecolor"] = "#d0d7de"
    plt.rcParams["grid.color"] = "#e5e7eb"
    plt.rcParams["axes.titleweight"] = "bold"


def detect_analysis_window(raw_events: list[dict]) -> tuple[str, str]:
    if not raw_events:
        return ("n/a", "n/a")
    timestamps = sorted(item["published_at"] for item in raw_events if item.get("published_at"))
    return (_format_timestamp(timestamps[0]), _format_timestamp(timestamps[-1]))


def save_top_scores(cards: list[dict], output_dir: Path) -> None:
    labels = [f"#{item['rank']} {item['title'][:34]}" for item in cards[:10]]
    scores = [item.get("score") or 0 for item in cards[:10]]
    sectors = [item["sector"] for item in cards[:10]]
    palette = {
        "ЖКХ": "#0f766e",
        "Дороги и транспорт": "#2563eb",
        "Здравоохранение": "#dc2626",
        "Экология и ЧС": "#f59e0b",
        "Образование": "#7c3aed",
        "Экономика и промышленность": "#4b5563",
        "Госуслуги и сервисы": "#0891b2",
        "Прочее": "#64748b",
    }
    colors = [palette.get(sector, "#64748b") for sector in sectors]

    fig, ax = plt.subplots(figsize=(14, 7))
    bars = ax.barh(labels, scores, color=colors)
    ax.invert_yaxis()
    ax.set_title("Top проблем по score")
    ax.set_xlabel("Score")
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    for bar, score in zip(bars, scores):
        ax.text(bar.get_width() + 0.8, bar.get_y() + bar.get_height() / 2, f"{score:.1f}", va="center", fontsize=10)
    fig.tight_layout()
    fig.savefig(output_dir / "top_scores.png", dpi=180)
    plt.close(fig)


def save_sector_distribution(cards: list[dict], output_dir: Path) -> None:
    counts = Counter(item["sector"] for item in cards)
    labels = list(counts.keys())
    values = list(counts.values())

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(labels, values, color="#0f766e")
    ax.set_title("Распределение top-тем по секторам")
    ax.set_ylabel("Количество тем")
    ax.tick_params(axis="x", rotation=20)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.05, str(value), ha="center", fontsize=10)
    fig.tight_layout()
    fig.savefig(output_dir / "sector_distribution.png", dpi=180)
    plt.close(fig)


def save_source_mix(cards: list[dict], output_dir: Path) -> None:
    labels = [f"#{item['rank']}" for item in cards[:10]]
    official = [item["source_mix"]["official"] for item in cards[:10]]
    media = [item["source_mix"]["media"] for item in cards[:10]]
    social = [item["source_mix"]["social"] for item in cards[:10]]
    other = [item["source_mix"]["other"] for item in cards[:10]]

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(labels, social, label="social", color="#2563eb")
    ax.bar(labels, media, bottom=social, label="media", color="#0f766e")
    media_bottom = [a + b for a, b in zip(social, media)]
    ax.bar(labels, official, bottom=media_bottom, label="official", color="#f59e0b")
    official_bottom = [a + b + c for a, b, c in zip(social, media, official)]
    ax.bar(labels, other, bottom=official_bottom, label="other", color="#64748b")
    ax.set_title("Состав источников по top-темам")
    ax.set_xlabel("Ранг темы")
    ax.set_ylabel("Количество сигналов")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "source_mix.png", dpi=180)
    plt.close(fig)


def save_bot_vs_score(cards: list[dict], output_dir: Path) -> None:
    x = [item.get("score") or 0 for item in cards]
    y = [item.get("bot_score") or 0 for item in cards]
    sizes = [120 + len(item.get("evidence", [])) * 35 for item in cards]
    colors = ["#dc2626" if item.get("contradiction_flag") else "#0f766e" for item in cards]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.scatter(x, y, s=sizes, c=colors, alpha=0.75, edgecolors="#1f2937", linewidths=0.8)
    for item, score, bot_score in zip(cards, x, y):
        ax.text(score + 0.25, bot_score + 0.01, f"#{item['rank']}", fontsize=9)
    ax.set_title("Score vs Bot score")
    ax.set_xlabel("Score")
    ax.set_ylabel("Bot score")
    ax.grid(True, linestyle="--", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "bot_vs_score.png", dpi=180)
    plt.close(fig)


def save_source_health(source_stats: list[dict], output_dir: Path) -> None:
    rows = source_stats[:12]
    labels = [item["source_name"][:38] for item in rows]
    scanned = [item.get("scanned", 0) for item in rows]
    inserted = [item.get("inserted", 0) for item in rows]
    colors = ["#0f766e" if item.get("status") == "ok" else "#dc2626" for item in rows]

    fig, ax = plt.subplots(figsize=(14, 7))
    y_pos = list(range(len(rows)))
    ax.barh(y_pos, scanned, color="#cbd5e1", label="scanned")
    ax.barh(y_pos, inserted, color=colors, label="inserted")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_title("Состояние live-источников")
    ax.set_xlabel("Количество материалов")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "source_health.png", dpi=180)
    plt.close(fig)


def write_summary(cards_payload: dict, source_stats_payload: dict, raw_events: list[dict], output_dir: Path) -> None:
    cards = cards_payload["items"]
    window_start, window_end = detect_analysis_window(raw_events)
    top = cards[0] if cards else None
    contradictions = sum(1 for item in cards if item.get("contradiction_flag"))
    high_urgency = sum(1 for item in cards if item.get("urgency") == "high")
    average_confidence = round(sum(item.get("confidence", 0) for item in cards) / len(cards), 3) if cards else 0
    trend_distribution = Counter(item.get("trend", "stable") for item in cards)
    ok_sources = sum(1 for item in source_stats_payload["source_stats"] if item.get("status") == "ok")
    summary = [
        "# Visual Analytics Summary",
        "",
        f"- Регион: {cards_payload['region']}",
        f"- Сгенерировано: {cards_payload['generated_at']}",
        f"- Окно анализа: {window_start} -> {window_end}",
        f"- Карточек проблем: {cards_payload['total_cards']}",
        f"- High urgency: {high_urgency}",
        f"- Тем с противоречием: {contradictions}",
        f"- Средняя confidence: {average_confidence}",
        f"- Trend distribution: {dict(trend_distribution)}",
        f"- Источников со статусом ok: {ok_sources}",
    ]
    if top:
        summary.extend(
            [
                "",
                "## Топ-1 тема",
                f"- {top['title']}",
                f"- Score: {top['score']}",
                f"- Confidence: {top.get('confidence')}",
                f"- Sector: {top['sector']}",
                f"- Status: {top['status']}",
                f"- Trend: {top.get('trend')}",
                f"- Verification: {top.get('verification_state')}",
                f"- Why now: {'; '.join(top['why_now'])}",
            ]
        )
    (output_dir / "summary.md").write_text("\n".join(summary), encoding="utf-8")


def write_html_report(cards_payload: dict, top_payload: dict, source_stats_payload: dict, raw_events: list[dict], output_dir: Path) -> None:
    cards = cards_payload["items"]
    window_start, window_end = detect_analysis_window(raw_events)
    image_sources = {
        "top_scores": embed_png(output_dir / "top_scores.png"),
        "sector_distribution": embed_png(output_dir / "sector_distribution.png"),
        "source_mix": embed_png(output_dir / "source_mix.png"),
        "bot_vs_score": embed_png(output_dir / "bot_vs_score.png"),
        "source_health": embed_png(output_dir / "source_health.png"),
    }
    top_3_html = []
    for item in cards[:3]:
        evidence_html = "".join(
            f"<li><a href=\"{evidence['url']}\">{evidence['source_name']}</a>: {evidence['snippet']}</li>"
            for evidence in item.get("evidence", [])[:3]
        )
        timeline_html = "".join(
            f"<li>{_format_timestamp(point['published_at'])} · {point['signal_kind']} · {point['source_name']}</li>"
            for point in item.get("timeline", [])[:4]
        )
        top_3_html.append(
            f"""
            <section class="card">
              <div class="badge">#{item['rank']} · {item['urgency']}</div>
              <h3>{item['title']}</h3>
              <p><strong>Сектор:</strong> {item['sector']}</p>
              <p><strong>Статус:</strong> {item['status']}</p>
              <p><strong>Trend:</strong> {item.get('trend')} · <strong>Confidence:</strong> {item.get('confidence')} · <strong>Verification:</strong> {item.get('verification_state')}</p>
              <p><strong>Муниципалитеты:</strong> {', '.join(item['municipalities'])}</p>
              <p>{item['summary']}</p>
              <p><strong>Почему сейчас:</strong> {'; '.join(item['why_now'])}</p>
              <p><strong>Timeline:</strong></p>
              <ul>{timeline_html}</ul>
              <ul>{evidence_html}</ul>
            </section>
            """
        )

    html = f"""
    <html lang="ru">
    <head>
      <meta charset="utf-8" />
      <title>User Tests · Visual Analytics</title>
      <style>
        body {{
          font-family: "Segoe UI", "Trebuchet MS", sans-serif;
          margin: 0;
          background: linear-gradient(180deg, #f4fafb 0%, #ffffff 100%);
          color: #10212b;
        }}
        .wrap {{
          max-width: 1200px;
          margin: 0 auto;
          padding: 32px 24px 48px;
        }}
        .hero {{
          background: white;
          border: 1px solid #d8e5e8;
          border-radius: 20px;
          padding: 24px;
          box-shadow: 0 18px 45px rgba(15, 23, 32, 0.08);
          margin-bottom: 24px;
        }}
        .grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
          gap: 18px;
          margin-bottom: 24px;
        }}
        .panel {{
          background: white;
          border: 1px solid #d8e5e8;
          border-radius: 18px;
          padding: 18px;
          box-shadow: 0 12px 28px rgba(15, 23, 32, 0.06);
        }}
        .panel img {{
          width: 100%;
          border-radius: 12px;
        }}
        .cards {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
          gap: 18px;
        }}
        .card {{
          background: white;
          border: 1px solid #d8e5e8;
          border-radius: 18px;
          padding: 18px;
          box-shadow: 0 12px 28px rgba(15, 23, 32, 0.06);
        }}
        .badge {{
          display: inline-block;
          padding: 6px 10px;
          border-radius: 999px;
          background: #0f766e;
          color: white;
          font-weight: 700;
          margin-bottom: 10px;
        }}
        code {{
          background: #eef6f8;
          padding: 2px 6px;
          border-radius: 6px;
        }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <section class="hero">
          <h1>Visual Analytics Check</h1>
          <p><strong>Регион:</strong> {cards_payload['region']}</p>
          <p><strong>Сгенерировано:</strong> {cards_payload['generated_at']}</p>
          <p><strong>Окно анализа:</strong> {window_start} -> {window_end}</p>
          <p><strong>Карточек:</strong> {cards_payload['total_cards']} · <strong>Тем в top issues:</strong> {top_payload['total_topics']} · <strong>Источников в отчёте:</strong> {len(source_stats_payload['source_stats'])}</p>
          <p>Это визуальная ручная проверка. Здесь можно быстро увидеть, что аналитика реально работает: как ранжируются темы, как распределяются сектора, где есть риск аномалий и как отработали источники.</p>
          <p><strong>Как читать:</strong> сначала посмотрите <code>Top проблем по score</code>, потом <code>Source mix</code>, потом <code>Score vs Bot score</code>, а ниже уже откройте карточки первых тем.</p>
          <p><a href="how_it_works.html"><strong>Открыть страницу “Как это работает”</strong></a></p>
        </section>

        <section class="grid">
          <div class="panel"><h2>Top проблем по score</h2><img src="{image_sources['top_scores']}" alt="top scores" /></div>
          <div class="panel"><h2>Распределение по секторам</h2><img src="{image_sources['sector_distribution']}" alt="sector distribution" /></div>
          <div class="panel"><h2>Состав источников</h2><img src="{image_sources['source_mix']}" alt="source mix" /></div>
          <div class="panel"><h2>Score vs Bot score</h2><img src="{image_sources['bot_vs_score']}" alt="bot vs score" /></div>
          <div class="panel"><h2>Состояние live-источников</h2><img src="{image_sources['source_health']}" alt="source health" /></div>
        </section>

        <h2>Первые карточки проблем</h2>
        <section class="cards">
          {''.join(top_3_html)}
        </section>
      </div>
    </body>
    </html>
    """
    (output_dir / "index.html").write_text(html, encoding="utf-8")


def _format_timestamp(raw_value: str) -> str:
    try:
        return datetime.fromisoformat(raw_value).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return raw_value


def _format_source_mix(source_mix: dict) -> str:
    parts = []
    for key in ("social", "media", "official", "other"):
        value = source_mix.get(key, 0)
        if value:
            parts.append(f"{key}: {value}")
    return ", ".join(parts) if parts else "нет данных"


def _render_raw_event_card(event: dict, fallback_source: str, fallback_snippet: str, fallback_url: str, fallback_time: str) -> str:
    title = event.get("title") or fallback_snippet
    text = event.get("text") or fallback_snippet
    municipality = event.get("municipality") or "unknown"
    return f"""
    <article class="raw-card">
      <div class="mini-badge">{escape(event.get('source_type', 'raw'))}</div>
      <h4>{escape(title)}</h4>
      <p><strong>Источник:</strong> {escape(event.get('source_name', fallback_source))}</p>
      <p><strong>Время:</strong> {escape(_format_timestamp(event.get('published_at', fallback_time)))}</p>
      <p><strong>Муниципалитет:</strong> {escape(municipality)}</p>
      <p>{escape(text[:320])}</p>
      <p><a href="{escape(event.get('url', fallback_url))}">Открыть первоисточник</a></p>
    </article>
    """


def write_how_it_works(cards_payload: dict, top_payload: dict, raw_events: list[dict], output_dir: Path) -> None:
    raw_lookup = {item.get("event_id"): item for item in raw_events}
    cards_by_id = {item["topic_id"]: item for item in cards_payload["items"]}

    flows_html = []
    for issue in top_payload["items"][:3]:
        topic = issue["topic"]
        card = cards_by_id.get(topic["topic_id"])
        if not card:
            continue

        raw_cards = []
        for evidence in topic.get("evidence", [])[:4]:
            raw_event = raw_lookup.get(evidence.get("event_id"), {})
            raw_cards.append(
                _render_raw_event_card(
                    raw_event,
                    evidence.get("source_name", "unknown"),
                    evidence.get("snippet", ""),
                    evidence.get("url", "#"),
                    evidence.get("published_at", ""),
                )
            )

        score_rows = "".join(
            f"<tr><td>{escape(metric)}</td><td>{value}</td></tr>"
            for metric, value in topic.get("score_breakdown", {}).items()
        )
        why_now = "".join(f"<li>{escape(reason)}</li>" for reason in topic.get("why_in_top", []))
        facts = "".join(f"<li>{escape(fact)}</li>" for fact in card.get("key_facts", []))

        flows_html.append(
            f"""
            <section class="flow-card">
              <div class="flow-head">
                <div class="badge">#{issue['rank']}</div>
                <div>
                  <h2>{escape(topic['label'])}</h2>
                  <p><strong>Сектор:</strong> {escape(topic['sector'])} · <strong>Муниципалитеты:</strong> {escape(', '.join(topic['municipalities']))}</p>
                </div>
              </div>

              <div class="pipeline">
                <div class="stage">
                  <h3>1. Raw events</h3>
                  <p>Сырые сигналы из разных источников. Здесь видно, что тема не выдумана, а собрана из реальных сообщений.</p>
                  <div class="raw-grid">
                    {''.join(raw_cards)}
                  </div>
                </div>

                <div class="arrow">↓</div>

                <div class="stage">
                  <h3>2. Cluster / тема</h3>
                  <p>На этом шаге система склеивает похожие сообщения в одну проблему.</p>
                  <div class="info-grid">
                    <div class="info-box">
                      <h4>Что получилось</h4>
                      <p><strong>Label:</strong> {escape(topic['label'])}</p>
                      <p><strong>Event count:</strong> {topic['event_count']}</p>
                      <p><strong>Source count:</strong> {topic['source_count']}</p>
                      <p><strong>Confidence:</strong> {topic.get('confidence')}</p>
                      <p><strong>Trend:</strong> {escape(topic.get('trend', 'stable'))}</p>
                      <p><strong>Verification:</strong> {escape(topic.get('verification_state', 'single_source'))}</p>
                      <p><strong>Source mix:</strong> {escape(_format_source_mix(topic.get('source_mix', {})))}</p>
                      <p><strong>Contradiction:</strong> {topic['contradiction_flag']}</p>
                      <p><strong>Bot score:</strong> {topic['bot_score']}</p>
                    </div>
                    <div class="info-box">
                      <h4>Score breakdown</h4>
                      <table>
                        <tbody>
                          {score_rows}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                <div class="arrow">↓</div>

                <div class="stage">
                  <h3>3. Problem card</h3>
                  <p>Фронтовая карточка, которую удобно показывать пользователю или жюри.</p>
                  <div class="info-grid">
                    <div class="info-box">
                      <h4>Карточка</h4>
                      <p><strong>Urgency:</strong> {escape(card['urgency'])}</p>
                      <p><strong>Status:</strong> {escape(card['status'])}</p>
                      <p><strong>Trend:</strong> {escape(card.get('trend', 'stable'))}</p>
                      <p><strong>Confidence:</strong> {card.get('confidence')}</p>
                      <p><strong>Verification:</strong> {escape(card.get('verification_state', 'single_source'))}</p>
                      <p><strong>Summary:</strong> {escape(card['summary'])}</p>
                    </div>
                    <div class="info-box">
                      <h4>Key facts</h4>
                      <ul>{facts}</ul>
                    </div>
                  </div>
                </div>

                <div class="arrow">↓</div>

                <div class="stage">
                  <h3>4. Top issue</h3>
                  <p>Итоговый объект ранжирования, который попадает в общий top региона.</p>
                  <div class="info-grid">
                    <div class="info-box">
                      <h4>Итог</h4>
                      <p><strong>Rank:</strong> #{issue['rank']}</p>
                      <p><strong>Score:</strong> {topic['score']}</p>
                      <p><strong>Issue relevance:</strong> {topic['issue_relevance']}</p>
                    </div>
                    <div class="info-box">
                      <h4>Почему в топе</h4>
                      <ul>{why_now}</ul>
                    </div>
                  </div>
                </div>
              </div>
            </section>
            """
        )

    html = f"""
    <html lang="ru">
    <head>
      <meta charset="utf-8" />
      <title>How It Works · Visual Analytics</title>
      <style>
        body {{
          font-family: "Segoe UI", "Trebuchet MS", sans-serif;
          margin: 0;
          background: linear-gradient(180deg, #eef7f9 0%, #ffffff 100%);
          color: #10212b;
        }}
        .wrap {{
          max-width: 1280px;
          margin: 0 auto;
          padding: 32px 24px 64px;
        }}
        .hero, .flow-card {{
          background: white;
          border: 1px solid #d8e5e8;
          border-radius: 22px;
          padding: 24px;
          box-shadow: 0 18px 45px rgba(15, 23, 32, 0.08);
          margin-bottom: 24px;
        }}
        .badge, .mini-badge {{
          display: inline-block;
          padding: 6px 10px;
          border-radius: 999px;
          background: #0f766e;
          color: white;
          font-weight: 700;
        }}
        .mini-badge {{
          background: #1d4ed8;
          font-size: 12px;
        }}
        .flow-head {{
          display: flex;
          gap: 16px;
          align-items: flex-start;
          margin-bottom: 14px;
        }}
        .stage {{
          background: #f8fbfc;
          border: 1px solid #deeaee;
          border-radius: 18px;
          padding: 18px;
        }}
        .arrow {{
          text-align: center;
          font-size: 30px;
          color: #0f766e;
          margin: 10px 0;
        }}
        .raw-grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 14px;
        }}
        .raw-card, .info-box {{
          background: white;
          border: 1px solid #d8e5e8;
          border-radius: 14px;
          padding: 14px;
        }}
        .info-grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 14px;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
        }}
        td {{
          border-bottom: 1px solid #eef2f7;
          padding: 6px 4px;
          vertical-align: top;
        }}
        code {{
          background: #eef6f8;
          padding: 2px 6px;
          border-radius: 6px;
        }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <section class="hero">
          <h1>Как это работает</h1>
          <p>Эта страница показывает путь конкретной темы: <code>raw events → cluster → problem card → top issue</code>.</p>
          <p>Смысл страницы: можно быстро понять, что аналитика не “магия”, а прозрачная цепочка преобразований.</p>
          <p><a href="index.html"><strong>Вернуться к главному visual report</strong></a></p>
        </section>
        {''.join(flows_html)}
      </div>
    </body>
    </html>
    """
    (output_dir / "how_it_works.html").write_text(html, encoding="utf-8")


def create_share_bundle(output_dir: Path) -> Path:
    bundle_path = output_dir / "visual_report_bundle.zip"
    with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as archive:
        for name in ("index.html", "how_it_works.html", "summary.md"):
            archive.write(output_dir / name, arcname=name)
    return bundle_path


def main() -> None:
    ensure_paths()
    setup_matplotlib()

    top_payload = load_json(TOP_ISSUES_PATH)
    cards_payload = load_json(PROBLEM_CARDS_PATH)
    source_stats_payload = load_json(SOURCE_STATS_PATH)
    raw_events = load_jsonl(RAW_EVENTS_PATH)

    run_dir = prepare_output_dir()
    cards = cards_payload["items"]
    source_stats = source_stats_payload["source_stats"]

    save_top_scores(cards, run_dir)
    save_sector_distribution(cards, run_dir)
    save_source_mix(cards, run_dir)
    save_bot_vs_score(cards, run_dir)
    save_source_health(source_stats, run_dir)
    write_summary(cards_payload, source_stats_payload, raw_events, run_dir)
    write_html_report(cards_payload, top_payload, source_stats_payload, raw_events, run_dir)
    write_how_it_works(cards_payload, top_payload, raw_events, run_dir)
    bundle_path = create_share_bundle(run_dir)
    shareable_dir = publish_shareable(run_dir)
    latest_dir = copy_to_latest(run_dir)

    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "latest_dir": str(latest_dir),
                "html_report": str(latest_dir / "index.html"),
                "how_it_works": str(latest_dir / "how_it_works.html"),
                "summary": str(latest_dir / "summary.md"),
                "bundle_zip": str(latest_dir / bundle_path.name),
                "shareable_dir": str(shareable_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
