import itertools
from typing import List
from requests.exceptions import HTTPError
from django.conf import settings

from . import CheckRunner, Block, BlockHeightResult, Blockchain, \
    CHECK_BLOCK_HEIGHT, CHECK_BLOCK_VALIDATION
from ._utils import HttpBase


class FullNodeException(HTTPError):
    pass


class FullNodeRunner(CheckRunner, HttpBase):
    def __init__(self):
        self.key = settings.GETBLOCK_API_KEY
        self.supported_chains = [
            Blockchain('Bitcoin', 'bitcoin-testnet', True),
            Blockchain('Bitcoin', 'bitcoin-mainnet', False),
            Blockchain('Bitcoin Cash', 'bitcoincash-mainnet', False),
            Blockchain('Bitcoin SV', 'bitcoinsv-mainnet', False),
            Blockchain('Litecoin', 'litecoin-mainnet', False),
            Blockchain('Dogecoin', 'dogecoin-mainnet', False),
            Blockchain('Ethereum', 'ethereum-mainnet', False),
            Blockchain('Ethereum', 'ethereum-ropsten', True),
            Blockchain('Tezos', 'tezos-mainnet', False)
        ]
        self.endpoint_map = {
            'bitcoin-testnet': 'https://btc.getblock.io/testnet/',
            'bitcoin-mainnet': 'https://btc.getblock.io/mainnet/',
            'bitcoincash-mainnet': 'https://bch.getblock.io/mainnet/',
            'bitcoinsv-mainnet': 'https://bsv.getblock.io/mainnet/',
            'litecoin-mainnet': 'https://ltc.getblock.io/mainnet/',
            'dogecoin-mainnet': 'https://doge.getblock.io/mainnet/',
            'ethereum-mainnet': 'https://eth.getblock.io/mainnet/',
            'ethereum-ropsten': 'https://eth.getblock.io/testnet/',
            'tezos-mainnet': 'https://mainnet-tezos.giganode.io'
        }
        self.bitcoiners = {
            'bitcoin-testnet', 'bitcoin-mainnet', 'bitcoincash-mainnet',
            'bitcoinsv-mainnet', 'litecoin-mainnet', 'dogecoin-mainnet'
        }
        self.ethereums = {
            'ethereum-mainnet', 'ethereum-ropsten'
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
        elif chain_id in self.ethereums:
            res = self.jsonrpc(chain_id, 'eth_blockNumber')
            return BlockHeightResult(height=int(res, 16))
        elif chain_id == 'tezos-mainnet':
            res = self.session.request('get', f'{self.endpoint_map["tezos-mainnet"]}/chains/main/blocks/head')
            res.raise_for_status()
            return BlockHeightResult(height=res.json().get('header', {}).get('level'))
        raise NotImplementedError

    def get_all_block_heights(self, chain_ids: List[str]) -> List[BlockHeightResult]:
        raise NotImplementedError

    def get_block_at_height(self, chain_id: str, height: int) -> Block:
        if chain_id in self.bitcoiners:
            block_hash = self.jsonrpc(chain_id, 'getblockhash', [height])
            block = self.jsonrpc(chain_id, 'getblock', [block_hash])
            return Block(height, block_hash, block.get('tx', []))
        elif chain_id in self.ethereums:
            block = self.jsonrpc(chain_id, 'eth_getBlockByNumber', [hex(height), False])
            return Block(height, block['hash'], block.get('transactions', []))
        elif chain_id == 'tezos-mainnet':
            res = self.session.request('get', f'{self.endpoint_map["tezos-mainnet"]}/chains/main/blocks/{height}')
            res.raise_for_status()
            block = res.json()
            txids = []
            for op in itertools.chain(*block.get('operations', [])):
                txids.append(op['hash'])
            return Block(height, block.get('hash', ''), txids)

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
