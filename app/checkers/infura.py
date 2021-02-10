from typing import List
from django.conf import settings
from . import CheckRunner, Blockchain, BlockHeightResult
from ._utils import HttpBase


class InfuraCheckRunner(CheckRunner, HttpBase):
    def __init__(self):
        self.project_id = settings.INFURA_PROJECT_ID
        super().__init__()

    def get_supported_chains(self) -> List[Blockchain]:
        return [Blockchain('Ethereum Mainnet', 'ethereum-mainnet', False),
                Blockchain('Ethereum Ropsten', 'ethereum-ropsten', True)]

    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        if chain_id == 'ethereum-mainnet':
            url = 'https://mainnet.infura.io/v3'
        elif chain_id == 'ethereum-ropsten':
            url = 'https://ropsten.infura.io/v3'
        else:
            raise Exception(f'Unsupported blockchain={chain_id}')

        resp = self.session.request('post', f'{url}/{self.project_id}', json={
            'jsonrpc': '2.0', 'id': 1, 'method': 'eth_blockNumber', 'params': []
        })
        resp.raise_for_status()
        result = resp.json()
        return BlockHeightResult(height=int(result['result'], 16))
