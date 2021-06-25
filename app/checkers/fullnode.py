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
        self.project_id = settings.INFURA_PROJECT_ID
        self.supported_chains = [
            Blockchain('Bitcoin', 'bitcoin-testnet', True),
            Blockchain('Bitcoin', 'bitcoin-mainnet', False),
            Blockchain('Bitcoin Cash', 'bitcoincash-mainnet', False),
            Blockchain('Bitcoin Cash', 'bitcoincash-testnet', True),
            Blockchain('Bitcoin SV', 'bitcoinsv-mainnet', False),
            Blockchain('Litecoin', 'litecoin-mainnet', False),
            Blockchain('Dogecoin', 'dogecoin-mainnet', False),
            Blockchain('Ethereum', 'ethereum-mainnet', False),
            Blockchain('Ethereum', 'ethereum-ropsten', False),
            Blockchain('Tezos', 'tezos-mainnet', False),
            Blockchain('Ripple', 'ripple-mainnet', False)
        ]
        self.endpoint_map = {
            'bitcoin-testnet': 'https://btc.getblock.io/testnet/',
            'bitcoin-mainnet': 'https://btc.getblock.io/mainnet/',
            'bitcoincash-mainnet': 'https://bch.getblock.io/mainnet/',
            'litecoin-mainnet': 'https://ltc.getblock.io/mainnet/',
            'dogecoin-mainnet': 'https://doge.getblock.io/mainnet/',
            'ethereum-mainnet': 'https://mainnet.infura.io/v3',
            'ethereum-ropsten': 'https://ropsten.infura.io/v3',
            'tezos-mainnet': 'https://mainnet-tezos.giganode.io',
            'ripple-mainnet': 'https://s1.ripple.com:51234/'
        }
        self.bitcoiners = {
            'bitcoin-testnet', 'bitcoin-mainnet', 'bitcoincash-mainnet',
            'litecoin-mainnet', 'dogecoin-mainnet'
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
            res = self.getnode_jsonrpc(chain_id, 'getblockcount')
            return BlockHeightResult(height=res)
        elif chain_id in self.ethereums:
            res = self.infura_jsonrpc(chain_id, 'eth_blockNumber')
            return BlockHeightResult(height=int(res, 16))
        elif chain_id == 'tezos-mainnet':
            res = self.session.request(
                method='get',
                url=f'{self.endpoint_map["tezos-mainnet"]}/chains/main/blocks/head'
            )
            res.raise_for_status()
            return BlockHeightResult(height=res.json().get('header', {}).get('level'))
        elif chain_id == 'ripple-mainnet':
            res = self.ripple_jsonrpc(
                chain_id, 'ledger', [{'ledger_index': 'validated'}]
            )
            return BlockHeightResult(height=res.get('ledger_index'))
        elif chain_id == 'bitcoincash-testnet':
            res = self.session.get('https://trest.bitcoin.com/v2/blockchain/getBlockCount')
            res.raise_for_status()
            return BlockHeightResult(res.json())
        elif chain_id == 'bitcoinsv-mainnet':
            res = self.session.get('https://api.whatsonchain.com/v1/bsv/main/chain/info')
            res.raise_for_status()
            return BlockHeightResult(res.json().get('blocks'))

        raise NotImplementedError

    def get_all_block_heights(self, chain_ids: List[str]) -> List[BlockHeightResult]:
        raise NotImplementedError

    def get_block_at_height(self, chain_id: str, height: int) -> Block:
        if chain_id in self.bitcoiners:
            block_hash = self.getnode_jsonrpc(chain_id, 'getblockhash', [height])
            block = self.getnode_jsonrpc(chain_id, 'getblock', [block_hash])
            return Block(height, block_hash, block.get('tx', []))
        elif chain_id in self.ethereums:
            block = self.infura_jsonrpc(chain_id, 'eth_getBlockByNumber',
                                        [hex(height), False])
            return Block(height, block['hash'], block.get('transactions', []))
        elif chain_id == 'tezos-mainnet':
            res = self.session.request(
                method='get',
                url=f'{self.endpoint_map["tezos-mainnet"]}/chains/main/blocks/{height}'
            )
            res.raise_for_status()
            block = res.json()
            txids = []
            for op in itertools.chain(*block.get('operations', [])):
                txids.append(op['hash'])
            return Block(height, block.get('hash', ''), txids)
        elif chain_id == 'ripple-mainnet':
            res = self.ripple_jsonrpc(
                chain_id, 'ledger', [{'ledger_index': height, 'transactions': True}]
            )
            txids = res.get('ledger', {}).get('transactions', [])
            return Block(height, res.get('ledger_hash', ''), txids)
        elif chain_id == 'bitcoincash-testnet':
            resp = self.session.get(
                url=f'https://trest.bitcoin.com/v2/block/detailsByHeight/{height}'
            )
            resp.raise_for_status()
            block = resp.json()
            return Block(height, block.get('hash', ''), block.get('tx', []))
        elif chain_id == 'bitcoinsv-mainnet':
            resp = self.session.get(
                url=f'https://api.whatsonchain.com/v1/bsv/main/block/height/{height}'
            )
            resp.raise_for_status()
            block = resp.json()
            return Block(height, block.get('hash', ''), block.get('tx', []))
        raise NotImplementedError

    def get_ping(self):
        raise NotImplementedError

    def getnode_jsonrpc(self, chain_id, method, params=None):
        resp = self.session.request(
            method='post',
            url=self.endpoint_map[chain_id],
            headers={'x-api-key': self.key},
            json={
                'jsonrpc': '1.0',
                'id': '',
                'method': method,
                'params': params if params else []
            }
        )
        resp.raise_for_status()
        res = resp.json()
        if res.get('error', None):
            raise FullNodeException(f'JSONRPC Error: {res["error"]}')
        return res.get('result')

    def infura_jsonrpc(self, chain_id, method, params=None):
        resp = self.session.request(
            method='post',
            url=f'{self.endpoint_map[chain_id]}/{self.project_id}',
            json={
                'jsonrpc': '2.0',
                'id': 1,
                'method': method,
                'params': params or []
            }
        )
        resp.raise_for_status()
        res = resp.json()
        if res.get('error', None):
            raise FullNodeException(f'JSONRPC Error: {res["error"]}')
        return res.get('result')

    def ripple_jsonrpc(self, chain_id, method, params=None):
        resp = self.session.request(
            method='post',
            url=self.endpoint_map[chain_id],
            json={
                'method': method,
                'params': params or []
            }
        )
        resp.raise_for_status()
        res = resp.json()
        if res.get('error', None):
            raise FullNodeException(f'JSONRPC Error: {res["error"]}')
        return res.get('result')
