from typing import List
from collections import OrderedDict
from django.conf import settings
from . import CheckRunner, Blockchain, BlockHeightResult, Block
from ._utils import HttpBase


class EtherscanCheckRunner(CheckRunner, HttpBase):
    def __init__(self):
        self.token = settings.ETHERSCAN_TOKEN
        super().__init__()

    def get_supported_chains(self) -> List[Blockchain]:
        return [
            Blockchain(name='Ethereum Mainnet', slug='ethereum-mainnet', testnet=False),
            Blockchain(name='Ethereum Ropsten', slug='ethereum-ropsten', testnet=True)
        ]

    def get_supported_checks(self) -> List[str]:
        return ['height']

    def get_ping(self):
        raise NotImplementedError

    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        if chain_id == 'ethereum-mainnet':
            host = 'api.etherscan.io'
        elif chain_id == 'ethereum-ropsten':
            host = 'api-ropsten.etherscan.io'
        else:
            raise Exception(f'Unknown blockchain={chain_id}')
        # manually specifying headers here to ensure order because of something to do
        # with cloudflare: https://stackoverflow.com/questions/62684468/pythons-requests-triggers-cloudflares-security-while-urllib-does-not
        headers = OrderedDict({
            'Accept-Encoding': 'gzip, deflate, br',
            'Host': host,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0'
        })
        req = self.session.request('get', f'https://{host}/api', params={
            'module': 'proxy',
            'action': 'eth_blockNumber',
            'apikey': self.token
        }, headers=headers)
        req.raise_for_status()
        result = req.json()
        return BlockHeightResult(height=int(result['result'], 16))

    def get_all_block_heights(self, chain_ids: List[str]) -> List[BlockHeightResult]:
        raise NotImplementedError

    def get_block_at_height(self, chain_id: str, height: int) -> Block:
        raise NotImplementedError
