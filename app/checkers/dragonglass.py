from typing import List

from . import CheckRunner, Blockchain, BlockHeightResult
from ._utils import HttpBase


class DragonGlassCheckRunner(CheckRunner, HttpBase):
    def __init__(self):
        super().__init__()

    def get_supported_chains(self) -> List[Blockchain]:
        return []

    def get_supported_checks(self) -> List[str]:
        return ['height']

    def get_ping(self):
        raise NotImplementedError

    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        pass

    def get_all_block_heights(self, chain_ids: List[str]) -> List[BlockHeightResult]:
        raise NotImplementedError
