from typing import List

from . import CheckRunner, Blockchain, BlockHeightResult
from ._utils import HttpBase


class XrplCheckRunner(CheckRunner, HttpBase):
    def __init__(self):
        super().__init__()

    def get_supported_chains(self) -> List[Blockchain]:
        return [Blockchain('Ripple Mainnet', 'ripple-mainnet', False)]

    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        if chain_id != 'ripple-mainnet':
            raise Exception(f'Unsupported blockchain={chain_id}')
        resp = self.session.request('get', 'https://data.ripple.com/v2/ledgers/')
        resp.raise_for_status()
        result = resp.json()
        return BlockHeightResult(height=result['ledger']['ledger_index'])
