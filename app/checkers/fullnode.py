from typing import List
from requests.exceptions import HTTPError
from django.conf import settings

from . import CheckRunner, Block, BlockHeightResult, Blockchain, \
    CHECK_BLOCK_HEIGHT, CHECK_BLOCK_VALIDATION
from ._utils import HttpBase


class FullNodeException(HTTPError):
    pass


class FullNode(CheckRunner, HttpBase):
    def __init__(self):
        self.key = settings.GETBLOCK_API_KEY
        self.supported_chains = [
            Blockchain('Bitcoin', 'bitcoin-testnet', True),
            Blockchain('Bitcoin', 'bitcoin-mainnet', False),
            Blockchain('Bitcoin Cash', 'bitcoincash-mainnet', False),
            Blockchain('Bitcoin SV', 'bitcoinsv-mainnet', False),
            Blockchain('Litecoin', 'litecoin-mainnet', False),
            Blockchain('Dogecoin', 'dogecoin-mainnet', False)
        ]
        self.endpoint_map = {
            'bitcoin-testnet': 'https://btc.getblock.io/testnet/',
            'bitcoin-mainnet': 'https://btc.getblock.io/mainnet/',
            'bitcoincash-mainnet': 'https://bch.getblock.io/mainnet/',
            'bitcoinsv-mainnet': 'https://bsv.getblock.io/mainnet/',
            'litecoin-mainnet': 'https://ltc.getblock.io/mainnet/',
            'dogecoin-mainnet': 'https://doge.getblock.io/mainnet/'
        }
        self.bitcoiners = {
            'bitcoin-testnet', 'bitcoin-mainnet', 'bitcoincash-mainnet',
            'bitcoinsv-mainnet', 'litecoin-mainnet', 'dogecoin-mainnet'
        }
        super().__init__()

    def get_supported_chains(self) -> List[Blockchain]:
        return self.supported_chains

    def get_supported_checks(self) -> List[str]:
        return [CHECK_BLOCK_HEIGHT, CHECK_BLOCK_VALIDATION]

    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        if chain_id in self.bitcoiners:
            res = self.jsonrpc(chain_id, 'getblockcount')
            return BlockHeightResult(height=res)
        raise NotImplementedError

    def get_all_block_heights(self, chain_ids: List[str]) -> List[BlockHeightResult]:
        raise NotImplementedError

    def get_block_at_height(self, chain_id: str, height: int) -> Block:
        if chain_id in self.bitcoiners:
            block_hash = self.jsonrpc(chain_id, 'getblockhash', [height])
            block = self.jsonrpc(chain_id, 'getblock', [block_hash])
            return Block(height, block_hash, block['tx'])

    def get_ping(self):
        raise NotImplementedError

    def fetch(self, chain_id, method, **params):
        headers = {'x-api-key': self.key}
        if 'headers' in params:
            params['headers'].update(headers)
        else:
            params['headers'] = headers
        resp = self.session.request(method, f'{self.endpoint_map[chain_id]}', **params)
        resp.raise_for_status()
        if len(resp.content) > 0:
            return resp.json()
        return None

    def jsonrpc(self, chain_id, method, params=None):
        res = self.fetch(chain_id, 'POST', json={
            'jsonrpc': '1.0',
            'id': '',
            'method': method,
            'params': params if params else []
        })
        if res.get('error', None):
            raise FullNodeException(f'JSONRPC Error: {res["error"]}')
        return res.get('result')

    def get_all_bitcoiner_most_recent_blocks(self):
        for c in self.bitcoiners:
            try:
                h = self.get_block_height(c)
                b = self.get_block_at_height(c, h.height)
                print(c, h, 'txns =', len(b.txids))
            except Exception as e:
                print(c, e)
