from abc import ABC, abstractmethod


class Mode(ABC):
    name: str = "base"

    @abstractmethod
    def run(self):
        ...

    def stop(self):
        pass