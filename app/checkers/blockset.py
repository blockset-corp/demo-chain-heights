from typing import List
from django.conf import settings
from . import CheckRunner, BlockHeightResult, Blockchain, Block, \
    CHECK_BLOCK_HEIGHT, CHECK_BLOCK_HEIGHT_BULK, CHECK_BLOCK_VALIDATION, CHECK_PING
from ._utils import HttpBase


class BlocksetCheckRunner(CheckRunner, HttpBase):
    def __init__(self, node=False,
                 endpoint='https://api.blockset.com',
                 verify=True,
                 additional_headers=lambda: {}):
        self.node = node
        self.token = settings.BLOCKSET_TOKEN
        self.height_key = 'block_height' if node else 'verified_height'
        self.endpoint = endpoint
        self.verify = verify
        self.additional_headers = additional_headers()
        super().__init__()

    def get_supported_chains(self) -> List[Blockchain]:
        mainnets = self.fetch('get', 'blockchains', params={'testnet': 'false', 'include_experimental': 'true'})['_embedded']['blockchains']
        testnets = self.fetch('get', 'blockchains', params={'testnet': 'true',  'include_experimental': 'true'})['_embedded']['blockchains']
        result = []
        for chain in mainnets:
            result.append(Blockchain(chain['name'], chain['id'], False))
        for chain in testnets:
            result.append(Blockchain(chain['name'], chain['id'], True))
        return result

    def get_supported_checks(self) -> List[str]:
        if self.node:
            return [CHECK_BLOCK_HEIGHT, CHECK_BLOCK_HEIGHT_BULK, CHECK_PING]
        return [CHECK_BLOCK_HEIGHT, CHECK_BLOCK_HEIGHT_BULK, CHECK_BLOCK_VALIDATION, CHECK_PING]

    def get_ping(self):
        self.fetch('get', 'blockchains/bitcoin-testnet', timeout=2)

    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        chain = self.fetch('get', 'blockchains/' + chain_id)
        return BlockHeightResult(chain[self.height_key])

    def get_all_block_heights(self, chain_ids: List[str]) -> List[BlockHeightResult]:
        mainnets = self.fetch('get', 'blockchains', params={'testnet': 'false', 'include_experimental': 'true'})['_embedded']['blockchains']
        testnets = self.fetch('get', 'blockchains', params={'testnet': 'true',  'include_experimental': 'true'})['_embedded']['blockchains']
        all_chains = {b['id']: b for b in mainnets + testnets}
        result = []
        for chain_id in chain_ids:
            if chain_id not in all_chains or self.height_key not in all_chains[chain_id]:
                print(f'{self.height_key} not found for {chain_id}')
                result.append(BlockHeightResult(0))
            else:
                result.append(BlockHeightResult(height=all_chains[chain_id][self.height_key]))
        return result

    def get_block_at_height(self, chain_id: str, height: int) -> Block:
        block = self.fetch('get', f'blocks/{chain_id}:{height}')
        return Block(height, block.get('hash', ''), block.get('transaction_ids', []))

    def fetch(self, method, resource, **params):
        headers = {'authorization': 'Bearer ' + self.token}
        headers.update(self.additional_headers)
        if 'headers' in params:
            params['headers'].update(headers)
        else:
            params['headers'] = headers
        if 'verify' not in params:
            params['verify'] = self.verify
        resp = self.session.request(method, f'{self.endpoint}/{resource}', **params)
        resp.raise_for_status()
        if len(resp.content) > 0:
            return resp.json()
        return None
