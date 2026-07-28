from abc import ABC, abstractmethod
from typing import Generic, Type, TypeVar

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from ai_editorial_team.infrastructure.openai.config import OpenAIInfrastructureError


ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)
ContextT = TypeVar("ContextT")
DomainResultT = TypeVar("DomainResultT")


class OpenAIStructuredAgentError(OpenAIInfrastructureError):
    """Raised when a structured OpenAI agent cannot produce a result."""


class OpenAIStructuredAgent(ABC, Generic[ResponseModelT, ContextT, DomainResultT]):
    """Shared OpenAI Responses API workflow for structured-output agents."""

    def __init__(self, client: OpenAI, model: str) -> None:
        self._client = client
        self._model = model

    def run(self, *, input_payload: str, context: ContextT) -> DomainResultT:
        response_model = self.response_model()

        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=self.instructions(),
                input=input_payload,
                text_format=response_model,
                store=False,
            )
        except OpenAIError as exc:
            raise OpenAIStructuredAgentError(
                self.error_message(exc)
            ) from exc
        except ValidationError as exc:
            raise OpenAIStructuredAgentError(
                self.validation_error_message(exc)
            ) from exc

        parsed = response.output_parsed
        if parsed is None:
            raise OpenAIStructuredAgentError(
                self.empty_output_message()
            )

        return self.to_domain_result(parsed, context)

    @abstractmethod
    def instructions(self) -> str:
        """Return system instructions for the agent."""

    @abstractmethod
    def response_model(self) -> Type[ResponseModelT]:
        """Return the structured response schema."""

    @abstractmethod
    def to_domain_result(
        self, response: ResponseModelT, context: ContextT
    ) -> DomainResultT:
        """Map the structured response into the domain result."""

    @abstractmethod
    def error_message(self, exc: OpenAIError) -> str:
        """Return the infrastructure error message for OpenAI failures."""

    @abstractmethod
    def validation_error_message(self, exc: ValidationError) -> str:
        """Return the infrastructure error message for validation failures."""

    @abstractmethod
    def empty_output_message(self) -> str:
        """Return the infrastructure error message for empty structured output."""
