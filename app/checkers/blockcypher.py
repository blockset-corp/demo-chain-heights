from typing import List
from django.conf import settings
from . import CheckRunner, Blockchain, BlockHeightResult, Block
from ._utils import HttpBase


class BlockCypherCheckRunner(CheckRunner, HttpBase):
    chain_map = {
        'bitcoin-mainnet': ('Bitcoin Mainnet', 'btc/main', False),
        'bitcoin-testnet': ('Bitcoin Testnet', 'btc/test3', True),
        'dash-mainnet': ('Dash Mainnet', 'dash/main', False),
        'dogecoin-mainnet': ('Dogecoin Mainnet', 'doge/main', False),
        'litecoin-mainnet': ('Litecoin Mainnet', 'ltc/main', False),
        'ethereum-mainnet': ('Ethereum Mainnet', 'eth/main', False)
    }

    def __init__(self):
        self.token = settings.BLOCKCYPHER_TOKEN
        super().__init__()

    def get_supported_chains(self) -> List[Blockchain]:
        return [Blockchain(v[0], k, v[2]) for k, v in self.chain_map.items()]

    def get_supported_checks(self) -> List[str]:
        return ['height']

    def get_ping(self):
        raise NotImplementedError

    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        if chain_id not in self.chain_map:
            raise Exception(f'Unsupported blockchain={chain_id}')
        params = {
            'token': self.token
        }
        url = f'https://api.blockcypher.com/v1/{self.chain_map[chain_id][1]}'
        resp = self.session.request('get', url, params=params)
        resp.raise_for_status()
        result = resp.json()
        return BlockHeightResult(height=result['height'])

    def get_all_block_heights(self, chain_ids: List[str]) -> List[BlockHeightResult]:
        raise NotImplementedError

    def get_block_at_height(self, chain_id: str, height: int) -> Block:
        raise NotImplementedError
