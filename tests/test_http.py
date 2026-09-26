"""Fetcher against httpx's mock transport: a challenge stops at once, server errors retry with backoff up to a bound, and requests to one host are paced."""

import httpx
import pytest

from local_laws import GITHUB
from local_laws.http import USER_AGENT, Blocked, Fetcher, Unavailable

URL = "https://www2.census.gov/programs-surveys/gus/datasets/2022/govt_units_2022.ZIP"


def fetcher(handler, **kwargs):
    slept = []
    return Fetcher(transport=httpx.MockTransport(handler), sleep=slept.append, **kwargs), slept


def test_a_body_is_returned_and_the_pipeline_names_itself():
    agents = []

    def handler(request):
        agents.append(request.headers["User-Agent"])
        return httpx.Response(200, content=b"zip bytes")

    client, slept = fetcher(handler)
    assert client.get(URL) == b"zip bytes"
    assert agents == [USER_AGENT] and USER_AGENT.endswith(f"(+{GITHUB})") and client.requests == 1 and slept == []


@pytest.mark.parametrize("headers, content", [({"cf-mitigated": "challenge"}, b""), ({}, b"<html><title>Just a moment...</title>")])
def test_a_bot_challenge_is_a_stop_not_something_to_retry(headers, content):
    client, slept = fetcher(lambda request: httpx.Response(403, headers=headers, content=content))
    with pytest.raises(Blocked, match="bot challenge at ecode360.com/"):
        client.get("https://ecode360.com/")
    assert client.requests == 1 and slept == []


@pytest.mark.parametrize("status", [403, 404])
def test_client_errors_raise_without_a_retry(status):
    client, slept = fetcher(lambda request: httpx.Response(status))
    with pytest.raises(httpx.HTTPStatusError):
        client.get(URL)
    assert client.requests == 1 and slept == []


def test_server_errors_and_rate_limits_are_retried_with_backoff():
    responses = [httpx.Response(503), httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, content=b"ok")]
    client, slept = fetcher(lambda request: responses.pop(0), interval=0)
    assert client.get(URL) == b"ok"
    assert slept == [4, 7], "exponential backoff, and Retry-After when the server gives one"


def test_retries_are_bounded_and_the_last_failure_is_not_slept_on():
    client, slept = fetcher(lambda request: httpx.Response(503), interval=0, max_retries=2)
    with pytest.raises(Unavailable, match="HTTP 503 from www2.census.gov"):
        client.get(URL)
    assert client.requests == 3 and slept == [4, 8]


def test_network_errors_become_unavailable():
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    client, slept = fetcher(handler, interval=0, max_retries=1)
    with pytest.raises(Unavailable, match="ConnectError from www2.census.gov"):
        client.get(URL)
    assert client.requests == 2 and slept == [4]


def test_requests_to_one_host_are_paced_and_other_hosts_are_not_held_up():
    client, slept = fetcher(lambda request: httpx.Response(200), interval=5)
    client.get("https://a.example/1")
    client.get("https://b.example/1")
    assert slept == []
    client.get("https://a.example/2")
    assert len(slept) == 1 and 4.5 < slept[0] <= 5


def test_a_host_whose_robots_txt_asks_for_a_longer_crawl_delay_gets_it():
    client, slept = fetcher(lambda request: httpx.Response(200), interval=1)
    client.get("https://www.fema.gov/cis/nation.csv")
    client.get("https://www.fema.gov/api/open/v1/NfipCommunityStatusBook.parquet")
    client.get("https://a.example/1")
    client.get("https://a.example/2")
    assert len(slept) == 2 and 14.5 < slept[0] <= 15 and slept[1] <= 1
