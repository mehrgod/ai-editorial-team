from datetime import date, datetime, time
from decimal import Decimal

import streamlit as st

from ai_editorial_team.infrastructure.aws.dashboard_control import (
    AwsDashboardControl,
    AwsDashboardControlError,
)
from ai_editorial_team.infrastructure.persistence.postgres_dashboard_repository import (
    DASHBOARD_TIMEZONE,
    PostgresDashboardRepository,
    PostgresDashboardRepositoryError,
)


def main() -> None:
    st.set_page_config(page_title="AI Editorial Team Dashboard", layout="wide")
    st.title("AI Editorial Team Dashboard")
    _initialize_session_state()
    _render_editorial_data()
    _render_workflow_controls()


def _render_editorial_data() -> None:
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
        publication["platform"].lower(): publication for publication in publications
    }

    _render_last_run(latest_run, stories, publications_by_platform)
    _render_latest_stories(stories)
    _render_publishing_status(publications_by_platform)
    _render_previous_posts(repository)
    _render_recent_runs(recent_runs)


def _render_workflow_controls() -> None:
    st.header("Workflow Controls")
    try:
        control = AwsDashboardControl.from_default_credentials()
    except AwsDashboardControlError as exc:
        st.error(str(exc))
        return

    schedule_column, run_column = st.columns(2)
    with schedule_column:
        _render_schedule_control(control)
    with run_column:
        _render_run_now_control(control)


def _render_schedule_control(control: AwsDashboardControl) -> None:
    with st.container(border=True):
        st.subheader("Schedule")
        try:
            schedule = control.get_schedule()
        except AwsDashboardControlError as exc:
            st.error(str(exc))
            return

        st.caption("Current schedule expression")
        st.code(schedule.expression)
        st.caption(f"Timezone: {schedule.timezone}")
        st.text(
            "Current posting time: "
            f"{_format_posting_time(schedule.posting_time)} ({schedule.timezone})"
        )

        with st.form("schedule_time_form", border=False):
            posting_time = st.time_input(
                "Posting time",
                value=schedule.posting_time,
                step=60,
            )
            save_schedule = st.form_submit_button(
                "Save Schedule",
                type="primary",
            )

        if save_schedule and posting_time is not None:
            try:
                updated = control.update_schedule_time(posting_time)
            except AwsDashboardControlError as exc:
                st.error(str(exc))
            else:
                st.success(
                    "Schedule updated to "
                    f"{_format_posting_time(updated.posting_time)} "
                    f"({updated.timezone})."
                )


def _render_run_now_control(control: AwsDashboardControl) -> None:
    with st.container(border=True):
        st.subheader("Run Now")
        st.caption("Start one Fargate task without waiting for it to finish.")
        st.button(
            "Run Now",
            key="run_now_button",
            type="primary",
            on_click=_queue_run_now_request,
        )

        request_id = st.session_state.get("run_now_request_id", 0)
        processed_id = st.session_state.get("run_now_processed_id", 0)
        if not _has_pending_run_now_request(request_id, processed_id):
            return
        st.session_state["run_now_processed_id"] = request_id

        try:
            task_arn = control.run_now()
        except AwsDashboardControlError as exc:
            st.error(str(exc))
        else:
            st.success("AWS accepted the ECS task request.")
            if task_arn:
                st.caption("Task ARN")
                st.code(task_arn)


def _initialize_session_state() -> None:
    st.session_state.setdefault("run_now_request_id", 0)
    st.session_state.setdefault("run_now_processed_id", 0)


def _queue_run_now_request() -> None:
    st.session_state["run_now_request_id"] += 1


def _has_pending_run_now_request(request_id: int, processed_id: int) -> bool:
    return request_id > processed_id


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
    _render_stories(
        stories,
        heading="Latest Stories",
        empty_message="No stories were stored for the latest run.",
    )


def _render_stories(stories, *, heading: str, empty_message: str) -> None:
    st.header(heading)
    if not stories:
        st.info(empty_message)
        return

    for story in stories:
        with st.container(border=True):
            st.caption(f"Rank {story['rank']} · {story['domain']}")
            st.subheader(story["headline"])
            st.write(story["summary"])
            with st.expander("Editorial reason"):
                st.write(story["editorial_reason"])


def _render_publishing_status(
    publications_by_platform,
    *,
    heading: str = "Publishing Status",
) -> None:
    st.header(heading)
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


def _render_previous_posts(repository: PostgresDashboardRepository) -> None:
    st.header("Previous Posts")
    selected_date = st.date_input(
        "Select date",
        value=datetime.now(DASHBOARD_TIMEZONE).date(),
        max_value=datetime.now(DASHBOARD_TIMEZONE).date(),
        key="previous_posts_date",
    )
    if not isinstance(selected_date, date):
        return

    try:
        runs = repository.get_runs_for_date(selected_date)
    except PostgresDashboardRepositoryError as exc:
        st.error(str(exc))
        return

    if not runs:
        st.info("No posts found for this date.")
        return

    selected_run = runs[0]
    if len(runs) > 1:
        selected_index = st.selectbox(
            "Select run time",
            options=range(len(runs)),
            format_func=lambda index: _format_run_option(runs[index]),
            key="previous_posts_run",
        )
        if selected_index is not None:
            selected_run = runs[selected_index]

    try:
        stories = repository.get_stories(selected_run["id"])
        publications = repository.get_publications(selected_run["id"])
    except PostgresDashboardRepositoryError as exc:
        st.error(str(exc))
        return

    publications_by_platform = {
        publication["platform"].lower(): publication for publication in publications
    }
    st.caption(f"Run started: {_format_datetime(selected_run['started_at'])}")
    _render_stories(
        stories,
        heading="Selected Day's Stories",
        empty_message="No stories were stored for this run.",
    )
    _render_publishing_status(
        publications_by_platform,
        heading="Selected Day's Publishing Status",
    )


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
    st.dataframe(table_rows, hide_index=True)


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
    return value.astimezone(DASHBOARD_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S %Z")


def _format_duration(value: Decimal | float | None) -> str:
    if value is None:
        return "—"
    return f"{float(value):.2f} s"


def _format_posting_time(value: time) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def _format_run_option(run) -> str:
    started_at = run["started_at"].astimezone(DASHBOARD_TIMEZONE)
    return (
        f"{started_at.strftime('%I:%M %p').lstrip('0')} "
        f"{started_at.strftime('%Z')} · {_display_status(run['status'])}"
    )


if __name__ == "__main__":
    main()
