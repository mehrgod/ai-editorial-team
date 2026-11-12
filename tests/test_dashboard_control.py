import unittest
from datetime import datetime, time, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError
from streamlit.testing.v1 import AppTest

from ai_editorial_team.infrastructure.aws.dashboard_control import (
    ECS_CLUSTER,
    ECS_SECURITY_GROUP,
    ECS_SUBNET,
    ECS_TASK_DEFINITION,
    SCHEDULE_NAME,
    AwsDashboardControl,
    AwsDashboardControlError,
    EcsTaskStatus,
    ScheduleDetails,
    parse_daily_cron_time,
    rebuild_daily_cron_expression,
)
from dashboard import _has_pending_run_now_request


SCHEDULE_RESPONSE = {
    "ActionAfterCompletion": "NONE",
    "Arn": "arn:aws:scheduler:us-east-1:123456789012:schedule/default/example",
    "CreationDate": datetime(2026, 1, 1, tzinfo=timezone.utc),
    "Description": "Daily editorial workflow",
    "EndDate": datetime(2027, 1, 1, tzinfo=timezone.utc),
    "FlexibleTimeWindow": {"Mode": "OFF"},
    "GroupName": "default",
    "KmsKeyArn": "arn:aws:kms:us-east-1:123456789012:key/example",
    "LastModificationDate": datetime(2026, 6, 1, tzinfo=timezone.utc),
    "Name": SCHEDULE_NAME,
    "ScheduleExpression": "cron(15 9 * * ? *)",
    "ScheduleExpressionTimezone": "America/New_York",
    "StartDate": datetime(2026, 1, 2, tzinfo=timezone.utc),
    "State": "ENABLED",
    "Target": {
        "Arn": "arn:aws:ecs:us-east-1:123456789012:cluster/example",
        "RoleArn": "arn:aws:iam::123456789012:role/example",
        "DeadLetterConfig": {"Arn": "arn:aws:sqs:us-east-1:123456789012:example-dlq"},
        "RetryPolicy": {
            "MaximumEventAgeInSeconds": 3600,
            "MaximumRetryAttempts": 2,
        },
        "EcsParameters": {
            "TaskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/example:7",
            "LaunchType": "FARGATE",
            "NetworkConfiguration": {
                "awsvpcConfiguration": {
                    "Subnets": ["subnet-example"],
                    "SecurityGroups": ["sg-example"],
                    "AssignPublicIp": "ENABLED",
                }
            },
            "TaskCount": 1,
        },
        "Input": '{"source":"scheduler"}',
    },
}
DASHBOARD_PATH = Path(__file__).resolve().parents[1] / "dashboard.py"
TASK_ARN = "arn:aws:ecs:us-east-1:123456789012:task/example"


class AwsDashboardControlTests(unittest.TestCase):
    def test_scheduler_read_returns_daily_time_and_timezone(self):
        scheduler = Mock()
        scheduler.get_schedule.return_value = SCHEDULE_RESPONSE
        control = AwsDashboardControl(scheduler_client=scheduler, ecs_client=Mock())

        actual = control.get_schedule()

        self.assertEqual(actual.expression, "cron(15 9 * * ? *)")
        self.assertEqual(actual.timezone, "America/New_York")
        self.assertEqual(actual.posting_time, time(9, 15))
        self.assertEqual(actual.state, "ENABLED")
        scheduler.get_schedule.assert_called_once_with(Name=SCHEDULE_NAME)

    def test_scheduler_read_returns_disabled_state(self):
        scheduler = Mock()
        scheduler.get_schedule.return_value = {
            **SCHEDULE_RESPONSE,
            "State": "DISABLED",
        }
        control = AwsDashboardControl(scheduler_client=scheduler, ecs_client=Mock())

        actual = control.get_schedule()

        self.assertEqual(actual.state, "DISABLED")

    def test_daily_cron_time_parsing_and_rebuilding(self):
        self.assertEqual(parse_daily_cron_time("cron(5 18 * * ? *)"), time(18, 5))
        self.assertEqual(
            rebuild_daily_cron_expression(
                "cron(5 18 * * ? *)",
                time(7, 45),
            ),
            "cron(45 7 * * ? *)",
        )

    def test_schedule_update_preserves_existing_configuration(self):
        scheduler = Mock()
        scheduler.get_schedule.return_value = SCHEDULE_RESPONSE
        control = AwsDashboardControl(scheduler_client=scheduler, ecs_client=Mock())

        updated = control.update_schedule_time(time(14, 30))

        scheduler.update_schedule.assert_called_once_with(
            ActionAfterCompletion=SCHEDULE_RESPONSE["ActionAfterCompletion"],
            Description=SCHEDULE_RESPONSE["Description"],
            EndDate=SCHEDULE_RESPONSE["EndDate"],
            FlexibleTimeWindow=SCHEDULE_RESPONSE["FlexibleTimeWindow"],
            GroupName=SCHEDULE_RESPONSE["GroupName"],
            KmsKeyArn=SCHEDULE_RESPONSE["KmsKeyArn"],
            Name=SCHEDULE_RESPONSE["Name"],
            ScheduleExpression="cron(30 14 * * ? *)",
            ScheduleExpressionTimezone=SCHEDULE_RESPONSE["ScheduleExpressionTimezone"],
            StartDate=SCHEDULE_RESPONSE["StartDate"],
            State=SCHEDULE_RESPONSE["State"],
            Target=SCHEDULE_RESPONSE["Target"],
        )
        request = scheduler.update_schedule.call_args.kwargs
        self.assertNotIn("Arn", request)
        self.assertNotIn("CreationDate", request)
        self.assertNotIn("LastModificationDate", request)
        self.assertIs(request["Target"], SCHEDULE_RESPONSE["Target"])
        self.assertEqual(updated.expression, "cron(30 14 * * ? *)")
        self.assertEqual(updated.posting_time, time(14, 30))
        self.assertEqual(updated.state, "ENABLED")

    def test_disabling_schedule_changes_only_state(self):
        scheduler = Mock()
        scheduler.get_schedule.return_value = SCHEDULE_RESPONSE
        control = AwsDashboardControl(scheduler_client=scheduler, ecs_client=Mock())

        updated = control.set_schedule_enabled(False)

        request = scheduler.update_schedule.call_args.kwargs
        self.assertEqual(request["State"], "DISABLED")
        self.assertEqual(
            request["ScheduleExpression"],
            SCHEDULE_RESPONSE["ScheduleExpression"],
        )
        self.assertIs(request["Target"], SCHEDULE_RESPONSE["Target"])
        self.assertEqual(
            {**request, "State": SCHEDULE_RESPONSE["State"]},
            _expected_schedule_update_request(),
        )
        self.assertEqual(updated.state, "DISABLED")
        self.assertEqual(updated.posting_time, time(9, 15))

    def test_enabling_schedule_changes_only_state(self):
        scheduler = Mock()
        disabled_schedule = {**SCHEDULE_RESPONSE, "State": "DISABLED"}
        scheduler.get_schedule.return_value = disabled_schedule
        control = AwsDashboardControl(scheduler_client=scheduler, ecs_client=Mock())

        updated = control.set_schedule_enabled(True)

        request = scheduler.update_schedule.call_args.kwargs
        self.assertEqual(request["State"], "ENABLED")
        self.assertEqual(
            request["ScheduleExpression"],
            SCHEDULE_RESPONSE["ScheduleExpression"],
        )
        self.assertIs(request["Target"], SCHEDULE_RESPONSE["Target"])
        self.assertEqual(
            {**request, "State": SCHEDULE_RESPONSE["State"]},
            _expected_schedule_update_request(),
        )
        self.assertEqual(updated.state, "ENABLED")
        self.assertEqual(updated.posting_time, time(9, 15))

    def test_schedule_state_update_surfaces_aws_failure(self):
        scheduler = Mock()
        scheduler.get_schedule.return_value = SCHEDULE_RESPONSE
        scheduler.update_schedule.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ServiceUnavailableException",
                    "Message": "sensitive AWS response",
                }
            },
            "UpdateSchedule",
        )
        control = AwsDashboardControl(scheduler_client=scheduler, ecs_client=Mock())

        with self.assertRaises(AwsDashboardControlError) as context:
            control.set_schedule_enabled(False)

        self.assertEqual(
            str(context.exception),
            "Could not update the AWS schedule. AWS returned "
            "ServiceUnavailableException.",
        )
        self.assertNotIn("sensitive", str(context.exception))

    def test_run_now_uses_expected_ecs_configuration(self):
        ecs = Mock()
        ecs.run_task.return_value = {"tasks": [{"taskArn": TASK_ARN}], "failures": []}
        control = AwsDashboardControl(scheduler_client=Mock(), ecs_client=ecs)

        actual = control.run_now()

        self.assertEqual(actual, TASK_ARN)
        ecs.run_task.assert_called_once_with(
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

    def test_describe_task_maps_provisioning_status_and_fields(self):
        ecs = Mock()
        created_at = datetime(2026, 11, 12, 15, tzinfo=timezone.utc)
        ecs.describe_tasks.return_value = {
            "tasks": [
                {
                    "taskArn": TASK_ARN,
                    "lastStatus": "PROVISIONING",
                    "desiredStatus": "RUNNING",
                    "createdAt": created_at,
                    "containers": [{"name": "editorial-team"}],
                }
            ],
            "failures": [],
        }
        control = AwsDashboardControl(scheduler_client=Mock(), ecs_client=ecs)

        actual = control.get_task_status(TASK_ARN)

        ecs.describe_tasks.assert_called_once_with(
            cluster=ECS_CLUSTER,
            tasks=[TASK_ARN],
        )
        self.assertEqual(actual.task_arn, TASK_ARN)
        self.assertEqual(actual.last_status, "PROVISIONING")
        self.assertEqual(actual.desired_status, "RUNNING")
        self.assertEqual(actual.created_at, created_at)
        self.assertIsNone(actual.completed_successfully)

    def test_describe_task_maps_running_status(self):
        ecs = Mock()
        started_at = datetime(2026, 11, 12, 15, 1, tzinfo=timezone.utc)
        ecs.describe_tasks.return_value = {
            "tasks": [
                {
                    "taskArn": TASK_ARN,
                    "lastStatus": "RUNNING",
                    "desiredStatus": "RUNNING",
                    "startedAt": started_at,
                }
            ]
        }
        control = AwsDashboardControl(scheduler_client=Mock(), ecs_client=ecs)

        actual = control.get_task_status(TASK_ARN)

        self.assertEqual(actual.last_status, "RUNNING")
        self.assertEqual(actual.started_at, started_at)
        self.assertIsNone(actual.completed_successfully)

    def test_stopped_task_with_zero_exit_code_is_successful(self):
        ecs = Mock()
        stopped_at = datetime(2026, 11, 12, 15, 5, tzinfo=timezone.utc)
        ecs.describe_tasks.return_value = {
            "tasks": [
                {
                    "taskArn": TASK_ARN,
                    "lastStatus": "STOPPED",
                    "desiredStatus": "STOPPED",
                    "stoppedAt": stopped_at,
                    "stopCode": "EssentialContainerExited",
                    "containers": [{"exitCode": 0}],
                }
            ]
        }
        control = AwsDashboardControl(scheduler_client=Mock(), ecs_client=ecs)

        actual = control.get_task_status(TASK_ARN)

        self.assertEqual(actual.last_status, "STOPPED")
        self.assertEqual(actual.stopped_at, stopped_at)
        self.assertEqual(actual.stop_code, "EssentialContainerExited")
        self.assertEqual(actual.container_exit_code, 0)
        self.assertTrue(actual.completed_successfully)
        self.assertIsNone(actual.failure_reason)

    def test_stopped_task_with_nonzero_exit_code_surfaces_container_reason(self):
        ecs = Mock()
        ecs.describe_tasks.return_value = {
            "tasks": [
                {
                    "taskArn": TASK_ARN,
                    "lastStatus": "STOPPED",
                    "desiredStatus": "STOPPED",
                    "stoppedReason": "Essential container exited",
                    "containers": [
                        {
                            "exitCode": 1,
                            "reason": "Application process failed",
                        }
                    ],
                }
            ]
        }
        control = AwsDashboardControl(scheduler_client=Mock(), ecs_client=ecs)

        actual = control.get_task_status(TASK_ARN)

        self.assertFalse(actual.completed_successfully)
        self.assertEqual(actual.container_exit_code, 1)
        self.assertEqual(actual.container_reason, "Application process failed")
        self.assertIn("code 1", actual.failure_reason)
        self.assertIn("Application process failed", actual.failure_reason)

    def test_stopped_task_surfaces_task_reason_when_container_reason_is_missing(self):
        ecs = Mock()
        ecs.describe_tasks.return_value = {
            "tasks": [
                {
                    "taskArn": TASK_ARN,
                    "lastStatus": "STOPPED",
                    "desiredStatus": "STOPPED",
                    "stoppedReason": "Task failed to start",
                    "containers": [],
                }
            ]
        }
        control = AwsDashboardControl(scheduler_client=Mock(), ecs_client=ecs)

        actual = control.get_task_status(TASK_ARN)

        self.assertFalse(actual.completed_successfully)
        self.assertIn("Task failed to start", actual.failure_reason)

    def test_describe_task_surfaces_missing_task(self):
        ecs = Mock()
        ecs.describe_tasks.return_value = {
            "tasks": [],
            "failures": [{"arn": TASK_ARN, "reason": "MISSING"}],
        }
        control = AwsDashboardControl(scheduler_client=Mock(), ecs_client=ecs)

        with self.assertRaises(AwsDashboardControlError) as context:
            control.get_task_status(TASK_ARN)

        self.assertEqual(
            str(context.exception),
            "No ECS task was found for the stored Task ARN.",
        )

    def test_describe_task_surfaces_aws_errors_without_sensitive_details(self):
        ecs = Mock()
        ecs.describe_tasks.side_effect = ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "sensitive AWS response",
                }
            },
            "DescribeTasks",
        )
        control = AwsDashboardControl(scheduler_client=Mock(), ecs_client=ecs)

        with self.assertRaises(AwsDashboardControlError) as context:
            control.get_task_status(TASK_ARN)

        self.assertEqual(
            str(context.exception),
            "Could not refresh the ECS task status: the current AWS identity needs "
            "ecs:DescribeTasks permission.",
        )
        self.assertNotIn("sensitive", str(context.exception))

    def test_aws_client_errors_are_surfaced_without_sensitive_details(self):
        scheduler = Mock()
        scheduler.get_schedule.side_effect = ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "sensitive AWS response",
                }
            },
            "GetSchedule",
        )
        control = AwsDashboardControl(scheduler_client=scheduler, ecs_client=Mock())

        with self.assertRaises(AwsDashboardControlError) as context:
            control.get_schedule()

        self.assertEqual(
            str(context.exception),
            "Could not read the AWS schedule. Check credentials and IAM permissions.",
        )
        self.assertNotIn("sensitive", str(context.exception))

    def test_schedule_update_reports_missing_pass_role_permission(self):
        scheduler = Mock()
        scheduler.get_schedule.return_value = SCHEDULE_RESPONSE
        scheduler.update_schedule.side_effect = ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": (
                        "not authorized to perform: iam:PassRole on resource: "
                        "arn:aws:iam::123456789012:role/sensitive-role"
                    ),
                }
            },
            "UpdateSchedule",
        )
        control = AwsDashboardControl(scheduler_client=scheduler, ecs_client=Mock())

        with self.assertRaises(AwsDashboardControlError) as context:
            control.update_schedule_time(time(14, 30))

        self.assertEqual(
            str(context.exception),
            "Could not update the AWS schedule: the current AWS identity is "
            "missing iam:PassRole for the scheduler's ECS target role.",
        )
        self.assertNotIn("sensitive-role", str(context.exception))

    def test_ecs_response_failures_are_surfaced(self):
        ecs = Mock()
        ecs.run_task.return_value = {
            "tasks": [],
            "failures": [{"reason": "RESOURCE:MEMORY"}],
        }
        control = AwsDashboardControl(scheduler_client=Mock(), ecs_client=ecs)

        with self.assertRaises(AwsDashboardControlError) as context:
            control.run_now()

        self.assertIn("RESOURCE:MEMORY", str(context.exception))

    def test_run_now_reports_missing_ecs_run_task_permission(self):
        ecs = Mock()
        ecs.run_task.side_effect = ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": (
                        "not authorized to perform: ecs:RunTask on resource: "
                        "arn:aws:ecs:us-east-1:123456789012:task-definition/sensitive"
                    ),
                }
            },
            "RunTask",
        )
        control = AwsDashboardControl(scheduler_client=Mock(), ecs_client=ecs)

        with self.assertRaises(AwsDashboardControlError) as context:
            control.run_now()

        self.assertEqual(
            str(context.exception),
            "Could not start the ECS workflow: the current AWS identity is "
            "missing ecs:RunTask for the AI Editorial Team task definition.",
        )
        self.assertNotIn("sensitive", str(context.exception))

    def test_run_now_reports_missing_pass_role_permission(self):
        ecs = Mock()
        ecs.run_task.side_effect = ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": (
                        "not authorized to perform: iam:PassRole on resource: "
                        "arn:aws:iam::123456789012:role/sensitive-role"
                    ),
                }
            },
            "RunTask",
        )
        control = AwsDashboardControl(scheduler_client=Mock(), ecs_client=ecs)

        with self.assertRaises(AwsDashboardControlError) as context:
            control.run_now()

        self.assertEqual(
            str(context.exception),
            "Could not start the ECS workflow: the current AWS identity is "
            "missing iam:PassRole for an ECS task role.",
        )
        self.assertNotIn("sensitive-role", str(context.exception))

    def test_one_run_now_request_is_claimed_only_once_across_reruns(self):
        request_id = 1
        processed_id = 0
        run_now = Mock()

        for _ in range(2):
            if _has_pending_run_now_request(request_id, processed_id):
                processed_id = request_id
                run_now()

        run_now.assert_called_once_with()
        self.assertEqual(processed_id, 1)

    def test_one_button_action_calls_run_task_once_across_streamlit_reruns(self):
        repository = Mock()
        repository.get_latest_run.return_value = None
        control = Mock()
        control.get_schedule.return_value = ScheduleDetails(
            expression="cron(0 12 * * ? *)",
            timezone="America/New_York",
            posting_time=time(12),
            state="ENABLED",
        )
        control.run_now.return_value = TASK_ARN
        control.get_task_status.return_value = _task_status("PROVISIONING")

        with patch(
            "ai_editorial_team.infrastructure.persistence."
            "postgres_dashboard_repository.PostgresDashboardRepository.from_env",
            return_value=repository,
        ), patch(
            "ai_editorial_team.infrastructure.aws."
            "dashboard_control.AwsDashboardControl.from_default_credentials",
            return_value=control,
        ):
            app = AppTest.from_file(str(DASHBOARD_PATH)).run(timeout=10)
            app.button(key="run_now_button").click().run(timeout=10)
            app.run(timeout=10)

        self.assertFalse(app.exception)
        control.run_now.assert_called_once_with()
        control.get_task_status.assert_called_once_with(TASK_ARN)
        self.assertEqual(app.session_state["current_task_arn"], TASK_ARN)
        self.assertEqual(
            app.session_state["current_task_status"].last_status,
            "PROVISIONING",
        )
        self.assertTrue(
            any(text.value == "Task status: PROVISIONING" for text in app.text)
        )

    def test_refresh_status_keeps_task_arn_and_does_not_run_another_task(self):
        repository = Mock()
        repository.get_latest_run.return_value = None
        control = Mock()
        control.get_schedule.return_value = ScheduleDetails(
            expression="cron(0 12 * * ? *)",
            timezone="America/New_York",
            posting_time=time(12),
            state="ENABLED",
        )
        control.get_task_status.return_value = _task_status("RUNNING")

        with patch(
            "ai_editorial_team.infrastructure.persistence."
            "postgres_dashboard_repository.PostgresDashboardRepository.from_env",
            return_value=repository,
        ), patch(
            "ai_editorial_team.infrastructure.aws."
            "dashboard_control.AwsDashboardControl.from_default_credentials",
            return_value=control,
        ):
            app = AppTest.from_file(str(DASHBOARD_PATH))
            app.session_state["current_task_arn"] = TASK_ARN
            app.session_state["current_task_status"] = _task_status("PROVISIONING")
            app.run(timeout=10)
            app.button(key="refresh_task_status_button").click().run(timeout=10)
            app.run(timeout=10)

        self.assertFalse(app.exception)
        control.run_now.assert_not_called()
        control.get_task_status.assert_called_once_with(TASK_ARN)
        self.assertEqual(app.session_state["current_task_arn"], TASK_ARN)
        self.assertEqual(
            app.session_state["current_task_status"].last_status,
            "RUNNING",
        )
        self.assertTrue(any(text.value == "Task status: RUNNING" for text in app.text))

    def test_enabled_schedule_shows_disable_action_and_one_click_updates_once(self):
        repository = Mock()
        repository.get_latest_run.return_value = None
        enabled = ScheduleDetails(
            expression="cron(0 12 * * ? *)",
            timezone="America/New_York",
            posting_time=time(12),
            state="ENABLED",
        )
        disabled = ScheduleDetails(
            expression=enabled.expression,
            timezone=enabled.timezone,
            posting_time=enabled.posting_time,
            state="DISABLED",
        )
        control = Mock()
        control.get_schedule.side_effect = [enabled, enabled, disabled]
        control.set_schedule_enabled.return_value = disabled

        with patch(
            "ai_editorial_team.infrastructure.persistence."
            "postgres_dashboard_repository.PostgresDashboardRepository.from_env",
            return_value=repository,
        ), patch(
            "ai_editorial_team.infrastructure.aws."
            "dashboard_control.AwsDashboardControl.from_default_credentials",
            return_value=control,
        ):
            app = AppTest.from_file(str(DASHBOARD_PATH)).run(timeout=10)
            self.assertEqual(
                app.button(key="schedule_state_button").label,
                "Disable Schedule",
            )
            app.button(key="schedule_state_button").click().run(timeout=10)

        self.assertFalse(app.exception)
        control.set_schedule_enabled.assert_called_once_with(False)
        self.assertEqual(
            app.button(key="schedule_state_button").label,
            "Enable Schedule",
        )
        self.assertTrue(any(text.value == "Scheduler: Disabled" for text in app.text))
        self.assertTrue(
            any(
                success.value == "Schedule disabled successfully."
                for success in app.success
            )
        )

    def test_disabled_schedule_shows_enable_action(self):
        repository = Mock()
        repository.get_latest_run.return_value = None
        control = Mock()
        control.get_schedule.return_value = ScheduleDetails(
            expression="cron(0 12 * * ? *)",
            timezone="America/New_York",
            posting_time=time(12),
            state="DISABLED",
        )

        with patch(
            "ai_editorial_team.infrastructure.persistence."
            "postgres_dashboard_repository.PostgresDashboardRepository.from_env",
            return_value=repository,
        ), patch(
            "ai_editorial_team.infrastructure.aws."
            "dashboard_control.AwsDashboardControl.from_default_credentials",
            return_value=control,
        ):
            app = AppTest.from_file(str(DASHBOARD_PATH)).run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(
            app.button(key="schedule_state_button").label,
            "Enable Schedule",
        )
        self.assertTrue(any(text.value == "Scheduler: Disabled" for text in app.text))


def _expected_schedule_update_request():
    return {
        field: SCHEDULE_RESPONSE[field]
        for field in (
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
    }


def _task_status(last_status: str, *, exit_code: int | None = None) -> EcsTaskStatus:
    return EcsTaskStatus(
        task_arn=TASK_ARN,
        last_status=last_status,
        desired_status="STOPPED" if last_status == "STOPPED" else "RUNNING",
        created_at=datetime(2026, 11, 12, 15, tzinfo=timezone.utc),
        started_at=None,
        stopped_at=None,
        stop_code=None,
        stopped_reason=None,
        container_exit_code=exit_code,
        container_reason=None,
    )


if __name__ == "__main__":
    unittest.main()
