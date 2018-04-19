import json
import sys
from tornado import ioloop, httpclient, escape

import logging

logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
logger = logging.getLogger(__name__)

httpclient.AsyncHTTPClient.configure(
    None, defaults=dict(
        user_agent="Python-HTTP-Request-Aggregator"
    )
)


class HttpRequestAggregator:

    def __init__(self, uris=list(), auth_username=None, auth_password=None, http_method="GET"):
        self.counter = 0
        self.auth_username = auth_username
        self.auth_password = auth_password
        self.http_method = http_method

        self.reset_master_uris(uris)
        self._uris_to_process = uris
        self.total_uris = None
        self._uris_processed = 0
        self.last_return = None

        self.process()

    def reset_master_uris(self, uris=list()):
        """Set the list of URIs to a new list."""
        self._master_uris = uris

    def process(self):
        """Fetch responses for all URIs in the stack"""
        self.responses = {}
        self.last_return = None
        self.fetch_requests()

    def fetch_requests(self):
        http_client = httpclient.AsyncHTTPClient()
        for uri in self._uris_to_process:
            self.counter += 1
            if self.http_method == 'GET':
                request = httpclient.HTTPRequest(url=uri.strip(), method=self.http_method,
                                                 auth_username=self.auth_username, auth_password=self.auth_password,
                                                 connect_timeout=10, request_timeout=200)
            else:
                request = None
            http_client.fetch(request, self.handle_request)
        ioloop.IOLoop.instance().start()

    def handle_request(self, response):
        if response.code not in self.responses:
            self.responses[response.code] = []
        if response.code != 200:
            self.responses[response.code].append(response.effective_url)
        else:
            self.responses[response.code].append(response)
        self.counter -= 1
        self._uris_processed += 1
        if self.counter == 0:
            ioloop.IOLoop.instance().stop()

    def responses_summary(self):
        """Return summary of response codes"""
        s = ''
        for code, responses in self.responses.items():
            s += f"{code}: {len(responses)}\n"
        return s

    def aggregated_responses_json(self):
        """Return JSON array of JSON responses"""
        return json.dumps(self.return_data())

    def return_data_as_json(self):
        if self.last_return is not None:
            return self.last_return
        try:
            responses = [r for r in self.responses[200]]
        except KeyError:
            logger.error("No successful responses")
            logger.info(self.responses)
            pass
        except:
            raise

        try:
            logger.info("returning JSON")
            self.last_return = "[%s]" % ",".join([resp.buffer.read().decode("utf-8") for resp in responses])
            return self.last_return
        except UnicodeDecodeError:
            logger.info("unicode error in return data set")
            l = []
            for resp in responses:
                try:
                    l.append("[%s]" % resp.buffer.read().decode("utf-8"))
                except:
                    logger.error(resp)
                    raise
        except:
            raise

    def return_data(self, JSON=True):
        if JSON:
            logger.info("returning data")
            x = self.return_data_as_json()
            return json.loads(x)
        else:
            return [f"{r}" for r in self.return_data_as_json()[1:-1].split(',')]


    def failed_requests(self):
        r = []
        for code in sorted(self.responses):
            if str(code).startswith('2'):
                pass
            else:
                r.append((code, self.responses[code]))
        return r