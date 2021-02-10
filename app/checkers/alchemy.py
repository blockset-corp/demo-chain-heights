from typing import List
from django.conf import settings
from . import CheckRunner, Blockchain, BlockHeightResult
from ._utils import HttpBase


class AlchemyCheckRunner(CheckRunner, HttpBase):
    def __init__(self):
        super().__init__()
        self.mainnet_key = settings.ALCHEMY_MAINNET_KEY
        self.ropsten_key = settings.ALCHEMY_ROPSTEN_KEY

    def get_supported_chains(self) -> List[Blockchain]:
        return [Blockchain('Ethereum Mainnet', 'ethereum-mainnet', False),
                Blockchain('Ethereum Ropsten', 'ethereum-ropsten', True)]

    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        if chain_id == 'ethereum-mainnet':
            url = 'https://eth-mainnet.alchemyapi.io/v2'
            key = self.mainnet_key
        elif chain_id == 'ethereum-ropsten':
            url = 'https://eth-ropsten.alchemyapi.io/v2'
            key = self.ropsten_key
        else:
            raise Exception(f'Unsupported blockchain={chain_id}')

        resp = self.session.request('post', f'{url}/{key}', json={
            'jsonrpc': '2.0', 'id': 1, 'method': 'eth_blockNumber', 'params': []
        })
        resp.raise_for_status()
        result = resp.json()
        return BlockHeightResult(height=int(result['result'], 16))

    def get_all_block_heights(self, chain_ids: List[str]) -> List[BlockHeightResult]:
        raise NotImplementedError
