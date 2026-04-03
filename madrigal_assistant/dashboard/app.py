from __future__ import annotations

from datetime import date, datetime, time

import pandas as pd
import plotly.express as px
import streamlit as st

from madrigal_assistant.services import RegionalPulseService

service = RegionalPulseService()

st.set_page_config(page_title="Madrigal Regional Pulse", page_icon="🛰️", layout="wide")

st.markdown(
    """
    <style>
        html, body, [class*="css"] { font-family: "Bahnschrift", "Trebuchet MS", "Segoe UI", sans-serif; }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(15,118,110,0.18), transparent 24%),
                radial-gradient(circle at top right, rgba(245,158,11,0.14), transparent 22%),
                linear-gradient(180deg, #f5fbfb 0%, #ffffff 100%);
        }
        .topic-card {
            border: 1px solid rgba(15, 118, 110, 0.18);
            border-radius: 18px;
            padding: 18px 18px 14px;
            background: rgba(255, 255, 255, 0.92);
            box-shadow: 0 16px 40px rgba(15, 23, 32, 0.08);
            min-height: 230px;
        }
        .topic-rank {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            background: #0f766e;
            color: white;
            font-weight: 800;
            margin-bottom: 10px;
        }
        .topic-meta { color: #45616b; font-size: 0.92rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _selected_range() -> tuple[datetime | None, datetime | None]:
    start_date = st.sidebar.date_input("Период от", value=date(2026, 3, 28))
    end_date = st.sidebar.date_input("Период до", value=date.today())
    start = datetime.combine(start_date, time.min).astimezone() if start_date else None
    end = datetime.combine(end_date, time.max).astimezone() if end_date else None
    return start, end


st.title("Madrigal Regional Pulse")
st.caption("Объяснимый top-10 проблем региона с дедупликацией, evidence и экспортом.")

with st.sidebar:
    st.subheader("Режим данных")
    if st.button("Загрузить demo seed", use_container_width=True):
        result = service.import_seed()
        st.success(f"Импортировано: {result.imported}, обновлено: {result.updated}")
    if st.button("Обновить live-источники", use_container_width=True):
        result = service.run_ingest(max_per_source=8)
        st.success(f"Сканировано: {result.scanned}, новых: {result.inserted}, обновлено: {result.updated}")
    uploaded = st.file_uploader("Импорт JSON/CSV", type=["json", "csv"])
    if uploaded is not None and st.button("Загрузить файл", use_container_width=True):
        result = service.import_seed(upload_bytes=uploaded.read(), filename=uploaded.name)
        st.success(f"Импортировано: {result.imported}, обновлено: {result.updated}")

    options = service.filter_options()
    start, end = _selected_range()
    selected_sector = st.selectbox("Сфера", ["Все"] + options["sectors"])
    selected_municipality = st.selectbox("Муниципалитет", ["Все"] + options["municipalities"])
    selected_source_type = st.selectbox("Тип источника", ["Все"] + options["source_types"])

sector_filter = None if selected_sector == "Все" else selected_sector
municipality_filter = None if selected_municipality == "Все" else selected_municipality
source_type_filter = None if selected_source_type == "Все" else selected_source_type

snapshot = service.get_top_issues(start=start, end=end, sector=sector_filter, municipality=municipality_filter, source_type=source_type_filter)
raw_events = service.get_raw_events(start=start, end=end, source_type=source_type_filter)
trends = service.get_trends(start=start, end=end, sector=sector_filter, municipality=municipality_filter)

col1, col2, col3, col4 = st.columns(4)
col1.metric("События", raw_events.total_events)
col2.metric("Темы", snapshot.total_topics)
col3.metric("С official signal", sum(1 for item in snapshot.items if item.topic.score_breakdown and item.topic.score_breakdown.official_signal > 0))
col4.metric("Средний bot score", round(sum(item.topic.bot_score for item in snapshot.items) / len(snapshot.items), 2) if snapshot.items else 0)

tabs = st.tabs(["Top-10", "Topic card", "Trends", "Source drill-down", "Export"])

with tabs[0]:
    if not snapshot.items:
        st.info("Данных пока нет. Загрузите demo seed или выполните live-ingest.")
    else:
        for index in range(0, len(snapshot.items), 2):
            cols = st.columns(2)
            batch = snapshot.items[index : index + 2]
            for col, issue in zip(cols, batch):
                with col:
                    st.markdown(
                        f"""
                        <div class="topic-card">
                            <div class="topic-rank">#{issue.rank}</div>
                            <h3>{issue.topic.label}</h3>
                            <div class="topic-meta">{issue.topic.sector} • {", ".join(issue.topic.municipalities)}</div>
                            <p><strong>Score:</strong> {issue.topic.score}</p>
                            <p>{issue.topic.neutral_summary}</p>
                            <p><strong>Почему в топе:</strong> {"; ".join(issue.topic.why_in_top) or "Общий вклад нескольких сигналов."}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

with tabs[1]:
    if not snapshot.items:
        st.info("Карточка темы появится после загрузки данных.")
    else:
        topic_labels = {f"#{issue.rank} {issue.topic.label}": issue.topic.topic_id for issue in snapshot.items}
        selected_topic_label = st.selectbox("Выберите тему", list(topic_labels))
        topic = service.get_topic(topic_labels[selected_topic_label], start=start, end=end, sector=sector_filter, municipality=municipality_filter, source_type=source_type_filter)
        if topic:
            left, right = st.columns([2, 1])
            with left:
                st.subheader(topic.label)
                st.write(topic.neutral_summary)
                st.write(f"Сфера: **{topic.sector}**")
                st.write(f"Муниципалитеты: **{', '.join(topic.municipalities)}**")
                st.write(f"Источники: **{', '.join(topic.sources)}**")
                st.write(f"Флаги: `contradiction={topic.contradiction_flag}`, `bot_score={topic.bot_score}`")
            with right:
                score_df = pd.DataFrame([{"metric": key, "value": value} for key, value in topic.score_breakdown.model_dump().items()])
                fig = px.bar(
                    score_df,
                    x="value",
                    y="metric",
                    orientation="h",
                    color="metric",
                    color_discrete_sequence=["#0f766e", "#1d4ed8", "#f59e0b", "#ef4444", "#0ea5e9", "#22c55e", "#94a3b8"],
                )
                fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=8, b=0), height=320)
                st.plotly_chart(fig, use_container_width=True)
            st.dataframe(pd.DataFrame([item.model_dump() for item in topic.evidence]), use_container_width=True, hide_index=True)

with tabs[2]:
    if not trends.series:
        st.info("Недостаточно данных для построения трендов.")
    else:
        trend_rows = []
        for series in trends.series:
            for point in series.points:
                trend_rows.append({"topic": series.label, "sector": series.sector, "bucket_start": point.bucket_start, "value": point.value})
        fig = px.line(
            pd.DataFrame(trend_rows),
            x="bucket_start",
            y="value",
            color="topic",
            markers=True,
            color_discrete_sequence=["#0f766e", "#1d4ed8", "#f59e0b", "#ef4444", "#14b8a6"],
        )
        fig.update_layout(margin=dict(l=0, r=0, t=24, b=0), height=420)
        st.plotly_chart(fig, use_container_width=True)

with tabs[3]:
    if not raw_events.items:
        st.info("Нет событий для drill-down.")
    else:
        events_df = pd.DataFrame([item.model_dump() for item in raw_events.items])
        columns = ["published_at", "source_name", "source_type", "municipality", "title", "url", "is_official", "engagement"]
        st.dataframe(events_df[columns], use_container_width=True, hide_index=True)

with tabs[4]:
    csv_payload = service.export_csv(start, end, sector_filter, municipality_filter, source_type_filter)
    html_payload = service.export_html(start, end, sector_filter, municipality_filter, source_type_filter)
    st.download_button("Скачать CSV", csv_payload, file_name="madrigal-top-issues.csv", mime="text/csv")
    st.download_button("Скачать HTML", html_payload, file_name="madrigal-top-issues.html", mime="text/html")
    st.code(csv_payload[:1200], language="csv")
