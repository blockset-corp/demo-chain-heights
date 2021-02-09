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
