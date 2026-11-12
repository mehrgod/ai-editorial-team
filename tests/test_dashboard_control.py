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


class AwsDashboardControlTests(unittest.TestCase):
    def test_scheduler_read_returns_daily_time_and_timezone(self):
        scheduler = Mock()
        scheduler.get_schedule.return_value = SCHEDULE_RESPONSE
        control = AwsDashboardControl(scheduler_client=scheduler, ecs_client=Mock())

        actual = control.get_schedule()

        self.assertEqual(actual.expression, "cron(15 9 * * ? *)")
        self.assertEqual(actual.timezone, "America/New_York")
        self.assertEqual(actual.posting_time, time(9, 15))
        scheduler.get_schedule.assert_called_once_with(Name=SCHEDULE_NAME)

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

    def test_run_now_uses_expected_ecs_configuration(self):
        ecs = Mock()
        task_arn = "arn:aws:ecs:us-east-1:123456789012:task/example"
        ecs.run_task.return_value = {"tasks": [{"taskArn": task_arn}], "failures": []}
        control = AwsDashboardControl(scheduler_client=Mock(), ecs_client=ecs)

        actual = control.run_now()

        self.assertEqual(actual, task_arn)
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
        )
        control.run_now.return_value = "arn:aws:ecs:us-east-1:123456789012:task/example"

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


if __name__ == "__main__":
    unittest.main()
