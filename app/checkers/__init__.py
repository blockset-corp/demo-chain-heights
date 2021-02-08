import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar, Callable, Optional, List, Mapping


@dataclass
class BlockHeightResult:
    height: int


@dataclass
class Blockchain:
    name: str
    slug: str
    testnet: bool


T = TypeVar('T')


@dataclass
class CheckResult(Generic[T]):
    duration: int
    error: Exception
    result: Optional[T]


class CheckRunner(ABC):
    @abstractmethod
    def get_supported_chains(self) -> List[Blockchain]:
        pass

    @abstractmethod
    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        pass


V = TypeVar('V')


def check(checker: Callable[[], V]) -> CheckResult[V]:
    start = time.time_ns()
    error = None
    result = None
    try:
        result = checker()
    except Exception as e:
        error = e
    end = time.time_ns()
    return CheckResult(end - start, error, result)


def get_all_check_runners() -> Mapping[str, CheckRunner]:
    from .blockset import BlocksetCheckRunner
    return {
        'blockset': BlocksetCheckRunner()
    }
