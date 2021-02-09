from typing import List
import requests
from django.conf import settings
from . import CheckRunner, BlockHeightResult, Blockchain


class BlocksetCheckRunner(CheckRunner):
    def __init__(self):
        self.token = settings.BLOCKSET_TOKEN
        self.session = requests.session()

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
        return BlockHeightResult(chain['block_height'])

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
