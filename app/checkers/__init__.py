from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Mapping


@dataclass
class BlockHeightResult:
    height: int


@dataclass
class Blockchain:
    name: str
    slug: str
    testnet: bool


class CheckRunner(ABC):
    @abstractmethod
    def get_supported_chains(self) -> List[Blockchain]:
        pass

    @abstractmethod
    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        pass


def get_all_check_runners() -> Mapping[str, CheckRunner]:
    from .blockset import BlocksetCheckRunner
    return {
        'blockset': BlocksetCheckRunner()
    }
