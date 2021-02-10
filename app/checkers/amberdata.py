from typing import List
from django.conf import settings
from . import CheckRunner, Blockchain, BlockHeightResult
from ._utils import HttpBase


class AmberdataCheckRunner(CheckRunner, HttpBase):
    chain_map = {
        'bitcoin-mainnet': ('Bitcoin Mainnet', 'bitcoin-mainnet', False),
        'bitcoincash-mainnet': ('Bitcoin Cash Mainnet', 'bitcoin-abc-mainnet', False),
        'bitcoinsv-mainnet': ('Bitcoin SV Mainnet', 'bitcoin-sv-mainnet', False),
        'ethereum-mainnet': ('Ethereum Mainnet', 'ethereum-mainnet', False),
        'litecoin-mainnet': ('Litecoin Mainnet', 'litecoin-mainnet', False),
        'zcash-mainnet': ('Zcash Mainnet', 'zcash-mainet', False)
    }

    def __init__(self):
        self.token = settings.AMBERDATA_TOKEN
        super().__init__()

    def get_supported_chains(self) -> List[Blockchain]:
        return [Blockchain(v[0], k, v[2]) for k, v in self.chain_map.items()]

    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        if chain_id not in self.chain_map:
            raise Exception(f'Unsupported blockchain={chain_id}')
        headers = {
            'x-api-key': self.token,
            'x-amberdata-blockchain-id': self.chain_map[chain_id][1]
        }
        resp = self.session.request('get', 'https://web3api.io/api/v2/blocks/latest', headers=headers)
        resp.raise_for_status()
        result = resp.json()
        return BlockHeightResult(height=int(result['payload']['number']))
