from typing import List
from . import CheckRunner, BlockHeightResult, Blockchain
from ._utils import HttpBase


class BlockchainCheckRunner(CheckRunner, HttpBase):
    def get_supported_chains(self) -> List[Blockchain]:
        return [
            Blockchain(name='Bitcoin Mainnet', slug='bitcoin-mainnet', testnet=False)
        ]

    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        if chain_id == 'bitcoin-mainnet':
            res = self.session.request('get', 'https://blockchain.info/latestblock')
            res.raise_for_status()
            result = res.json()
            return BlockHeightResult(height=result['height'])
        raise Exception(f'Unsupported blockchain={chain_id}')
