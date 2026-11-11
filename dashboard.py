from datetime import datetime, timezone
from decimal import Decimal

import streamlit as st

from ai_editorial_team.infrastructure.persistence.postgres_dashboard_repository import (
    PostgresDashboardRepository,
    PostgresDashboardRepositoryError,
)


def main() -> None:
    st.set_page_config(page_title="AI Editorial Team Dashboard", layout="wide")
    st.title("AI Editorial Team Dashboard")

    try:
        repository = PostgresDashboardRepository.from_env()
        latest_run = repository.get_latest_run()
        if latest_run is None:
            st.info("No workflow runs found yet.")
            return

        run_id = latest_run["id"]
        stories = repository.get_stories(run_id)
        publications = repository.get_publications(run_id)
        recent_runs = repository.get_recent_runs()
    except PostgresDashboardRepositoryError as exc:
        st.error(str(exc))
        return

    publications_by_platform = {
        publication["platform"].lower(): publication
        for publication in publications
    }

    _render_last_run(latest_run, stories, publications_by_platform)
    _render_latest_stories(stories)
    _render_publishing_status(publications_by_platform)
    _render_recent_runs(recent_runs)


def _render_last_run(latest_run, stories, publications_by_platform) -> None:
    st.header("Last Run")
    columns = st.columns(6)
    columns[0].metric("Status", _display_status(latest_run["status"]))
    columns[1].metric("Started", _format_datetime(latest_run["started_at"]))
    columns[2].metric(
        "Duration",
        _format_duration(latest_run["duration_seconds"]),
    )
    columns[3].metric("Stories", len(stories))
    columns[4].metric(
        "Instagram",
        _publication_status(publications_by_platform.get("instagram")),
    )
    columns[5].metric(
        "X",
        _publication_status(publications_by_platform.get("x")),
    )


def _render_latest_stories(stories) -> None:
    st.header("Latest Stories")
    if not stories:
        st.info("No stories were stored for the latest run.")
        return

    for story in stories:
        with st.container(border=True):
            st.caption(f"Rank {story['rank']} · {story['domain']}")
            st.subheader(story["headline"])
            st.write(story["summary"])
            with st.expander("Editorial reason"):
                st.write(story["editorial_reason"])


def _render_publishing_status(publications_by_platform) -> None:
    st.header("Publishing Status")
    instagram_column, x_column = st.columns(2)
    with instagram_column:
        _render_publication("Instagram", publications_by_platform.get("instagram"))
    with x_column:
        _render_publication("X", publications_by_platform.get("x"))


def _render_publication(label, publication) -> None:
    with st.container(border=True):
        st.subheader(label)
        if publication is None:
            st.write("Status: Not available")
            return

        st.write(f"Status: {_display_status(publication['status'])}")
        if publication["url"]:
            st.link_button("Open publication", publication["url"])
        if publication["published_at"]:
            st.write(f"Published: {_format_datetime(publication['published_at'])}")


def _render_recent_runs(recent_runs) -> None:
    st.header("Recent Runs")
    table_rows = [
        {
            "Started": _format_datetime(run["started_at"]),
            "Status": _display_status(run["status"]),
            "Duration": _format_duration(run["duration_seconds"]),
            "Instagram": _display_status(run["instagram_status"]),
            "X": _display_status(run["x_status"]),
        }
        for run in recent_runs
    ]
    st.dataframe(table_rows, hide_index=True, use_container_width=True)


def _publication_status(publication) -> str:
    if publication is None:
        return "Not available"
    return _display_status(publication["status"])


def _display_status(status: str | None) -> str:
    if not status:
        return "Not available"
    return status.replace("_", " ").title()


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _format_duration(value: Decimal | float | None) -> str:
    if value is None:
        return "—"
    return f"{float(value):.2f} s"


if __name__ == "__main__":
    main()
