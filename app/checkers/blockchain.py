from typing import List
from . import CheckRunner, BlockHeightResult, Blockchain, Block
from ._utils import HttpBase


class BlockchainCheckRunner(CheckRunner, HttpBase):
    def get_supported_chains(self) -> List[Blockchain]:
        return [
            Blockchain(name='Bitcoin Mainnet', slug='bitcoin-mainnet', testnet=False)
        ]

    def get_supported_checks(self) -> List[str]:
        return ['height']

    def get_ping(self):
        raise NotImplementedError

    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        if chain_id != 'bitcoin-mainnet':
            raise Exception(f'Unsupported blockchain={chain_id}')
        res = self.session.request('get', 'https://blockchain.info/latestblock')
        res.raise_for_status()
        result = res.json()
        return BlockHeightResult(height=result['height'])

    def get_all_block_heights(self, chain_ids: List[str]) -> List[BlockHeightResult]:
        raise NotImplementedError

    def get_block_at_height(self, chain_id: str, height: int) -> Block:
        raise NotImplementedError
