from typing import List
from django.conf import settings
from . import CheckRunner, Blockchain, BlockHeightResult
from ._utils import HttpBase


class BlockChairCheckRunner(CheckRunner, HttpBase):
    chain_map = {
        'bitcoin-mainnet': ('Bitcoin Mainnet', 'bitcoin', False),
        'bitcoin-testnet': ('Bitcoin Testnet', 'bitcoin/testnet', True),
        'bitcoincash-mainnet': ('Bitcoin Cash Mainnet', 'bitcoin-cash', False),
        'ethereum-mainnet': ('Ethereum Mainnet', 'ethereum', False),
        'litecoin-mainnet': ('Litecoin Mainnet', 'litecoin', False),
        'bitcoinsv-mainnet': ('Bitcoin SV Mainnet', 'bitcoin-sv', False),
        'dogecoin-mainnet': ('Dogecoin Mainnet', 'dogecoin', False),
        'dash-mainnet': ('Dash Mainnet', 'dash', False),
        'ripple-mainnet': ('Ripple Mainnet', 'ripple', False),
        'stellar-mainnet': ('Stellar Mainnet', 'stellar', False),
        'monero-mainnet': ('Monero Mainnet', 'monero', False),
        # 'cardano-mainnet': ('Cardano Mainnet', 'cardano', False),  # cardano times out every time
        'zcash-mainnet': ('Zcash Mainnet', 'zcash', False),
        'tezos-mainnet': ('Tezos Mainnet', 'tezos', False),
        'eos-mainnet': ('EOS Mainnet', 'eos', False),
    }

    def __init__(self):
        self.token = settings.BLOCKCHAIR_TOKEN
        super().__init__()

    def get_supported_chains(self) -> List[Blockchain]:
        return [Blockchain(v[0], k, v[2]) for k, v in self.chain_map.items()]

    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        if chain_id not in self.chain_map:
            raise Exception(f'Unsupported blockchain={chain_id}')
        params = {
            'key': self.token
        }
        url = f'https://api.blockchair.com/{self.chain_map[chain_id][1]}/stats'
        resp = self.session.request('get', url, params=params)
        resp.raise_for_status()
        result = resp.json()
        key = 'best_block_height'
        if chain_id in ('ripple-mainnet', 'stellar-mainnet'):
            key = 'best_ledger_height'
        return BlockHeightResult(result['data'][key])

    def get_all_block_heights(self, chain_ids: List[str]) -> List[BlockHeightResult]:
        params = {
            'key': self.token
        }
        resp = self.session.request('get', f'https://api.blockchair.com/stats', params)
        resp.raise_for_status()
        results = []
        data = resp.json()
        for chain_id in chain_ids:
            bc_chain_id = self.chain_map[chain_id][1]
            if bc_chain_id not in data['data']:  # chain wasn't fetched, get it manually
                results.append(self.get_block_height(chain_id))
            else:
                key = 'best_block_height'
                if chain_id in ('ripple-mainnet', 'stellar-mainnet'):
                    key = 'best_ledger_height'
                results.append(BlockHeightResult(height=data['data'][bc_chain_id]['data'][key]))
        return results
