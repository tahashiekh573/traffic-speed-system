from abc import ABC, abstractmethod
from typing import Generic, TypeVar

InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType")


class BaseAgent(ABC, Generic[InputType, OutputType]):
    """Base class for all CV agents."""

    @abstractmethod
    def run(self, data: InputType) -> OutputType:
        """Run the agent."""
        raise NotImplementedError
