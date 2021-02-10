from typing import List
from django.conf import settings
from . import CheckRunner, BlockHeightResult, Blockchain
from ._utils import HttpBase


class BlocksetCheckRunner(CheckRunner, HttpBase):
    def __init__(self):
        self.token = settings.BLOCKSET_TOKEN
        super().__init__()

    def get_supported_chains(self) -> List[Blockchain]:
        mainnets = self.fetch('get', 'blockchains')['_embedded']['blockchains']
        testnets = self.fetch('get', 'blockchains', params={'testnet': 'true'})['_embedded']['blockchains']
        result = []
        for chain in mainnets:
            result.append(Blockchain(chain['name'], chain['id'], False))
        for chain in testnets:
            result.append(Blockchain(chain['name'], chain['id'], True))
        return result

    def get_block_height(self, chain_id: str) -> BlockHeightResult:
        chain = self.fetch('get', 'blockchains/' + chain_id)
        return BlockHeightResult(chain['verified_height'])

    def get_all_block_heights(self, chain_ids: List[str]) -> List[BlockHeightResult]:
        mainnets = self.fetch('get', 'blockchains')['_embedded']['blockchains']
        testnets = self.fetch('get', 'blockchains', params={'testnet': 'true'})['_embedded']['blockchains']
        all_chains = {b['id']: b for b in mainnets + testnets}
        result = []
        for chain_id in chain_ids:
            if chain_id not in all_chains or 'verified_height' not in all_chains[chain_id]:
                print(f'verified_height not found for {chain_id}')
                result.append(BlockHeightResult(0))
            else:
                result.append(BlockHeightResult(height=all_chains[chain_id]['verified_height']))
        return result

    def fetch(self, method, resource, **params):
        headers = {'authorization': 'Bearer ' + self.token}
        if 'headers' in params:
            params['headers'].update(headers)
        else:
            params['headers'] = headers
        resp = self.session.request(method, 'https://api.blockset.com/' + resource, **params)
        resp.raise_for_status()
        if len(resp.content) > 0:
            return resp.json()
        return None
