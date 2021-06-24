from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Mapping


CHECK_BLOCK_HEIGHT = 'height'
CHECK_BLOCK_HEIGHT_BULK = 'height_bulk'
CHECK_PING = 'ping'
CHECK_BLOCK_VALIDATION = 'block_validation'


@dataclass
class BlockHeightResult:
    height: int


@dataclass
class Blockchain:
    name: str
    slug: str
    testnet: bool


@dataclass
class Block:
    height: int
    hash: str
    txids: List[str]


class CheckRunner(ABC):
    @abstractmethod
    def get_supported_chains(self) -> List[Blockchain]:
        pass

    @abstractmethod
    def get_supported_checks(self) -> List[str]:
        pass

    @abstractmethod
    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        pass

    @abstractmethod
    def get_all_block_heights(self, chain_ids: List[str]) -> List[BlockHeightResult]:
        pass

    @abstractmethod
    def get_block_at_height(self, chain_id: str, height: int) -> Block:
        pass

    @abstractmethod
    def get_ping(self):
        pass


def get_all_check_runners() -> Mapping[str, CheckRunner]:
    from .blockset import BlocksetCheckRunner
    from .blockchain import BlockchainCheckRunner
    from .etherscan import EtherscanCheckRunner
    from .blockcypher import BlockCypherCheckRunner
    from .blockchair import BlockChairCheckRunner
    from .blockstream import BlockstreamCheckRunner
    from .dragonglass import DragonGlassCheckRunner
    from .infura import InfuraCheckRunner
    from .amberdata import AmberdataCheckRunner
    from .alchemy import AlchemyCheckRunner
    from .xrpl import XrplCheckRunner

    return {
        'blockset': BlocksetCheckRunner(),
        'blocksetnode': BlocksetCheckRunner(node=True),
        'blockchain': BlockchainCheckRunner(),
        'etherscan': EtherscanCheckRunner(),
        'blockcypher': BlockCypherCheckRunner(),
        'blockchair': BlockChairCheckRunner(),
        'blockstream': BlockstreamCheckRunner(),
        'dragonglass': DragonGlassCheckRunner(),
        'infura': InfuraCheckRunner(),
        'amberdata': AmberdataCheckRunner(),
        'alchemy': AlchemyCheckRunner(),
        'xrpl': XrplCheckRunner(),
    }
