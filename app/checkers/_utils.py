from uuid import uuid4
import requests
from requests.adapters import HTTPAdapter
from django.conf import settings


class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.timeout = settings.HTTP_TIMEOUT
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
            del kwargs["timeout"]
        super().__init__(*args, **kwargs)

    def add_headers(self, request, **kwargs):
        # add a unique identifier to the user agent to help isolate connection resets
        super().add_headers(request, **kwargs)
        request.headers['User-Agent'] = f'chain-heights/{uuid4()}'

    def send(self, request, **kwargs):
        timeout = kwargs.get("timeout")
        if timeout is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)


class HttpBase:
    def __init__(self):
        self.session = requests.session()
        adapter = TimeoutHTTPAdapter()
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
