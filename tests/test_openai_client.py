import unittest
from unittest.mock import patch

from pydantic import BaseModel

from ai_editorial_team.infrastructure.openai import client as client_module
from ai_editorial_team.infrastructure.openai.config import OpenAIConfig
from ai_editorial_team.infrastructure.openai.structured_agent import (
    OpenAIStructuredAgent,
)


class OpenAIClientBundleTests(unittest.TestCase):
    def test_create_bundle_wraps_structured_client_once(self):
        constructed_clients = []
        wrapped_client = object()
        wrapped_inputs = []

        class FakeOpenAI:
            def __init__(self, api_key: str) -> None:
                self.api_key = api_key
                constructed_clients.append(self)

        def fake_wrap_openai(client):
            wrapped_inputs.append(client)
            return wrapped_client

        with patch.object(client_module, "OpenAI", FakeOpenAI), patch.object(
            client_module, "wrap_openai", side_effect=fake_wrap_openai
        ):
            bundle = client_module.create_openai_client_bundle(
                OpenAIConfig(
                    api_key="test-key",
                    model="gpt-test",
                    image_model="gpt-image-test",
                )
            )

        self.assertEqual(len(constructed_clients), 2)
        self.assertEqual(wrapped_inputs, [constructed_clients[0]])
        self.assertIs(bundle.client, wrapped_client)
        self.assertIs(bundle.image_client, constructed_clients[1])
        self.assertEqual(bundle.model, "gpt-test")
        self.assertEqual(bundle.image_model, "gpt-image-test")


class ExampleResponse(BaseModel):
    value: str


class ExampleStructuredAgent(
    OpenAIStructuredAgent[ExampleResponse, dict, str]
):
    def instructions(self) -> str:
        return "Return a value."

    def response_model(self) -> type[ExampleResponse]:
        return ExampleResponse

    def to_domain_result(self, response: ExampleResponse, context: dict) -> str:
        return response.value

    def error_message(self, exc) -> str:
        return f"request failed: {exc}"

    def validation_error_message(self, exc) -> str:
        return f"validation failed: {exc}"

    def empty_output_message(self) -> str:
        return "empty output"


class StructuredAgentResponsesParseTests(unittest.TestCase):
    def test_structured_agent_uses_responses_parse(self):
        class FakeParsedResponse:
            output_parsed = ExampleResponse(value="ok")

        class FakeResponses:
            def __init__(self) -> None:
                self.parse_calls = []

            def parse(self, **kwargs):
                self.parse_calls.append(kwargs)
                return FakeParsedResponse()

        class FakeClient:
            def __init__(self) -> None:
                self.responses = FakeResponses()

        client = FakeClient()
        agent = ExampleStructuredAgent(client=client, model="gpt-test")

        result = agent.run(input_payload="hello", context={})

        self.assertEqual(result, "ok")
        self.assertEqual(len(client.responses.parse_calls), 1)
        call = client.responses.parse_calls[0]
        self.assertEqual(call["model"], "gpt-test")
        self.assertEqual(call["instructions"], "Return a value.")
        self.assertEqual(call["input"], "hello")
        self.assertIs(call["text_format"], ExampleResponse)
        self.assertFalse(call["store"])


if __name__ == "__main__":
    unittest.main()
