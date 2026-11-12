from dataclasses import dataclass
from datetime import datetime, time
import re
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


AWS_REGION = "us-east-1"
SCHEDULE_NAME = "ai-editorial-team-daily"
ECS_CLUSTER = "ai-editorial-team-cluster"
ECS_TASK_DEFINITION = "ai-editorial-team"
ECS_SUBNET = "subnet-0514a0cdd50ac324d"
ECS_SECURITY_GROUP = "sg-0bb91c80c3aa746c9"

_UPDATABLE_SCHEDULE_FIELDS = (
    "ActionAfterCompletion",
    "Description",
    "EndDate",
    "FlexibleTimeWindow",
    "GroupName",
    "KmsKeyArn",
    "Name",
    "ScheduleExpression",
    "ScheduleExpressionTimezone",
    "StartDate",
    "State",
    "Target",
)


class AwsDashboardControlError(RuntimeError):
    """Raised when an AWS dashboard control operation fails."""


@dataclass(frozen=True)
class ScheduleDetails:
    expression: str
    timezone: str
    posting_time: time
    state: str


@dataclass(frozen=True)
class EcsTaskStatus:
    task_arn: str
    last_status: str
    desired_status: str | None
    created_at: datetime | None
    started_at: datetime | None
    stopped_at: datetime | None
    stop_code: str | None
    stopped_reason: str | None
    container_exit_code: int | None
    container_reason: str | None

    @property
    def completed_successfully(self) -> bool | None:
        if self.last_status != "STOPPED":
            return None
        return self.container_exit_code == 0

    @property
    def failure_reason(self) -> str | None:
        if self.completed_successfully is not False:
            return None

        details = []
        if self.container_exit_code is not None:
            details.append(f"Container exited with code {self.container_exit_code}.")
        reason = self.container_reason or self.stopped_reason or self.stop_code
        if reason:
            details.append(reason)
        if not details:
            details.append("The task stopped without a successful container exit code.")
        return " ".join(details)


@dataclass(frozen=True)
class AwsDashboardControl:
    """Reads and controls the scheduler and ECS workflow used by the dashboard."""

    scheduler_client: Any
    ecs_client: Any
    schedule_name: str = SCHEDULE_NAME

    @classmethod
    def from_default_credentials(cls) -> "AwsDashboardControl":
        try:
            return cls(
                scheduler_client=boto3.client("scheduler", region_name=AWS_REGION),
                ecs_client=boto3.client("ecs", region_name=AWS_REGION),
            )
        except BotoCoreError as exc:
            raise AwsDashboardControlError(
                "Could not initialize AWS controls. Check local AWS credentials."
            ) from exc

    def get_schedule(self) -> ScheduleDetails:
        schedule = self._get_schedule_response()
        expression = schedule["ScheduleExpression"]
        try:
            posting_time = parse_daily_cron_time(expression)
        except (TypeError, ValueError) as exc:
            raise AwsDashboardControlError(
                "The configured schedule is not a supported daily cron expression."
            ) from exc

        return ScheduleDetails(
            expression=expression,
            timezone=schedule.get("ScheduleExpressionTimezone", "UTC"),
            posting_time=posting_time,
            state=schedule.get("State", "ENABLED"),
        )

    def update_schedule_time(self, posting_time: time) -> ScheduleDetails:
        schedule = self._get_schedule_response()
        current_expression = schedule["ScheduleExpression"]
        try:
            updated_expression = rebuild_daily_cron_expression(
                current_expression,
                posting_time,
            )
        except (TypeError, ValueError) as exc:
            raise AwsDashboardControlError(
                "The configured schedule is not a supported daily cron expression."
            ) from exc

        update_request = self._build_schedule_update_request(schedule)
        update_request["ScheduleExpression"] = updated_expression
        self._update_schedule(update_request)

        return ScheduleDetails(
            expression=updated_expression,
            timezone=schedule.get("ScheduleExpressionTimezone", "UTC"),
            posting_time=posting_time.replace(second=0, microsecond=0),
            state=schedule.get("State", "ENABLED"),
        )

    def set_schedule_enabled(self, enabled: bool) -> ScheduleDetails:
        schedule = self._get_schedule_response()
        state = "ENABLED" if enabled else "DISABLED"
        update_request = self._build_schedule_update_request(schedule)
        update_request["State"] = state
        self._update_schedule(update_request)

        return ScheduleDetails(
            expression=schedule["ScheduleExpression"],
            timezone=schedule.get("ScheduleExpressionTimezone", "UTC"),
            posting_time=parse_daily_cron_time(schedule["ScheduleExpression"]),
            state=state,
        )

    def run_now(self) -> str | None:
        try:
            response = self.ecs_client.run_task(
                cluster=ECS_CLUSTER,
                taskDefinition=ECS_TASK_DEFINITION,
                launchType="FARGATE",
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": [ECS_SUBNET],
                        "securityGroups": [ECS_SECURITY_GROUP],
                        "assignPublicIp": "ENABLED",
                    }
                },
                count=1,
            )
        except ClientError as exc:
            raise AwsDashboardControlError(_ecs_run_error_message(exc)) from exc
        except BotoCoreError as exc:
            raise AwsDashboardControlError(
                "Could not start the ECS workflow. Check credentials and IAM permissions."
            ) from exc

        failures = response.get("failures", [])
        if failures:
            reason = failures[0].get("reason") or "AWS rejected the task request."
            raise AwsDashboardControlError(
                f"Could not start the ECS workflow: {reason}"
            )

        tasks = response.get("tasks", [])
        if not tasks:
            raise AwsDashboardControlError(
                "AWS accepted the request but did not return a started ECS task."
            )
        return tasks[0].get("taskArn")

    def get_task_status(self, task_arn: str) -> EcsTaskStatus:
        try:
            response = self.ecs_client.describe_tasks(
                cluster=ECS_CLUSTER,
                tasks=[task_arn],
            )
        except ClientError as exc:
            raise AwsDashboardControlError(_ecs_describe_error_message(exc)) from exc
        except BotoCoreError as exc:
            raise AwsDashboardControlError(
                "Could not refresh the ECS task status. Check credentials and IAM "
                "permissions."
            ) from exc

        tasks = response.get("tasks", [])
        if not tasks:
            raise AwsDashboardControlError(
                "No ECS task was found for the stored Task ARN."
            )

        task = tasks[0]
        container = _task_container(task.get("containers", []))
        return EcsTaskStatus(
            task_arn=task.get("taskArn", task_arn),
            last_status=task.get("lastStatus", "UNKNOWN"),
            desired_status=task.get("desiredStatus"),
            created_at=task.get("createdAt"),
            started_at=task.get("startedAt"),
            stopped_at=task.get("stoppedAt"),
            stop_code=task.get("stopCode"),
            stopped_reason=task.get("stoppedReason"),
            container_exit_code=container.get("exitCode") if container else None,
            container_reason=container.get("reason") if container else None,
        )

    def _get_schedule_response(self) -> dict[str, Any]:
        try:
            return self.scheduler_client.get_schedule(Name=self.schedule_name)
        except (BotoCoreError, ClientError) as exc:
            raise AwsDashboardControlError(
                "Could not read the AWS schedule. Check credentials and IAM permissions."
            ) from exc

    def _build_schedule_update_request(
        self,
        schedule: dict[str, Any],
    ) -> dict[str, Any]:
        update_request = {
            field: schedule[field]
            for field in _UPDATABLE_SCHEDULE_FIELDS
            if field in schedule
        }
        update_request["Name"] = schedule.get("Name", self.schedule_name)
        return update_request

    def _update_schedule(self, update_request: dict[str, Any]) -> None:
        try:
            self.scheduler_client.update_schedule(**update_request)
        except ClientError as exc:
            raise AwsDashboardControlError(_schedule_update_error_message(exc)) from exc
        except BotoCoreError as exc:
            raise AwsDashboardControlError(
                "Could not update the AWS schedule. Check credentials and IAM permissions."
            ) from exc


def parse_daily_cron_time(expression: str) -> time:
    parts = _daily_cron_parts(expression)
    minute = _parse_cron_number(parts[0], maximum=59)
    hour = _parse_cron_number(parts[1], maximum=23)
    return time(hour=hour, minute=minute)


def rebuild_daily_cron_expression(expression: str, posting_time: time) -> str:
    parts = _daily_cron_parts(expression)
    parts[0] = str(posting_time.minute)
    parts[1] = str(posting_time.hour)
    return f"cron({' '.join(parts)})"


def _daily_cron_parts(expression: str) -> list[str]:
    match = re.fullmatch(r"cron\(([^)]+)\)", expression.strip())
    if match is None:
        raise ValueError("Expected an AWS cron expression.")

    parts = match.group(1).split()
    if len(parts) != 6:
        raise ValueError("Expected six AWS cron fields.")

    day_of_month, month, day_of_week, year = parts[2:]
    is_daily = (
        month == "*"
        and year == "*"
        and (
            (day_of_month == "*" and day_of_week == "?")
            or (day_of_month == "?" and day_of_week == "*")
        )
    )
    if not is_daily:
        raise ValueError("Expected a daily AWS cron expression.")
    return parts


def _parse_cron_number(value: str, *, maximum: int) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError("Expected a numeric cron time.") from exc
    if not 0 <= number <= maximum:
        raise ValueError("Cron time is outside the supported range.")
    return number


def _schedule_update_error_message(exc: ClientError) -> str:
    error = exc.response.get("Error", {})
    code = error.get("Code")
    message = error.get("Message", "")
    if code in {"AccessDenied", "AccessDeniedException"}:
        if "iam:PassRole" in message:
            return (
                "Could not update the AWS schedule: the current AWS identity is "
                "missing iam:PassRole for the scheduler's ECS target role."
            )
        return (
            "Could not update the AWS schedule: access was denied. The current AWS "
            "identity needs scheduler:UpdateSchedule and iam:PassRole permissions."
        )
    if code:
        return f"Could not update the AWS schedule. AWS returned {code}."
    return "Could not update the AWS schedule. Check credentials and IAM permissions."


def _ecs_run_error_message(exc: ClientError) -> str:
    error = exc.response.get("Error", {})
    code = error.get("Code")
    message = error.get("Message", "")
    if code in {"AccessDenied", "AccessDeniedException"}:
        if "iam:PassRole" in message:
            return (
                "Could not start the ECS workflow: the current AWS identity is "
                "missing iam:PassRole for an ECS task role."
            )
        if "ecs:RunTask" in message:
            return (
                "Could not start the ECS workflow: the current AWS identity is "
                "missing ecs:RunTask for the AI Editorial Team task definition."
            )
        return (
            "Could not start the ECS workflow: access was denied. The current AWS "
            "identity needs ecs:RunTask and iam:PassRole permissions."
        )
    if code:
        return f"Could not start the ECS workflow. AWS returned {code}."
    return "Could not start the ECS workflow. Check credentials and IAM permissions."


def _ecs_describe_error_message(exc: ClientError) -> str:
    error = exc.response.get("Error", {})
    code = error.get("Code")
    if code in {"AccessDenied", "AccessDeniedException"}:
        return (
            "Could not refresh the ECS task status: the current AWS identity needs "
            "ecs:DescribeTasks permission."
        )
    if code:
        return f"Could not refresh the ECS task status. AWS returned {code}."
    return (
        "Could not refresh the ECS task status. Check credentials and IAM permissions."
    )


def _task_container(containers: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not containers:
        return None
    return next(
        (
            container
            for container in containers
            if container.get("exitCode") is not None or container.get("reason")
        ),
        containers[0],
    )
