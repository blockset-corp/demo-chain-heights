from typing import List

from . import CheckRunner, Blockchain, BlockHeightResult, Block
from ._utils import HttpBase


class BlockstreamCheckRunner(CheckRunner, HttpBase):
    def __init__(self):
        super().__init__()

    def get_supported_chains(self) -> List[Blockchain]:
        return [Blockchain('Bitcoin Mainnet', 'bitcoin-mainnet', False),
                Blockchain('Bitcoin Testnet', 'bitcoin-testnet', True)]

    def get_supported_checks(self) -> List[str]:
        return ['height']

    def get_ping(self):
        raise NotImplementedError

    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        if chain_id == 'bitcoin-mainnet':
            url = 'https://blockstream.info'
        elif chain_id == 'bitcoin-testnet':
            url = 'https://blockstream.info/testnet'
        else:
            raise Exception(f'Unsupported blockchain={chain_id}')

        resp = self.session.request('get', f'{url}/api/blocks/tip/height')
        resp.raise_for_status()
        height = int(resp.text)
        return BlockHeightResult(height=height)

    def get_all_block_heights(self, chain_ids: List[str]) -> List[BlockHeightResult]:
        raise NotImplementedError

    def get_block_at_height(self, chain_id: str, height: int) -> Block:
        raise NotImplementedError
