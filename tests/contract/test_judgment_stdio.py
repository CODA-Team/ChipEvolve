"""Real pipe notifications, fragmented responses and startup failure."""

import sys

import pytest

from query_agent.adapters.judgment.stdio import (
    JudgmentTransportError,
    StdioJudgmentClient,
)

SERVER = """
import json,sys,time
for line in sys.stdin:
    request=json.loads(line)
    if 'id' not in request: continue
    result={'answer':'L2'}
    if request['method']=='initialize': result={'protocolVersion':'2025-11-25'}
    # A buffered text reader would consume both lines and then wait on an empty pipe.
    packet=json.dumps({'jsonrpc':'2.0','method':'notifications/progress'})+'\\n'
    packet+=json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result})+'\\n'
    sys.stdout.write(packet[:15]);sys.stdout.flush()
    time.sleep(.005)
    sys.stdout.write(packet[15:]);sys.stdout.flush()
"""


def test_notifications_and_fragmented_json_do_not_lose_the_response() -> None:
    with StdioJudgmentClient([sys.executable, "-u", "-c", SERVER], timeout=1) as client:
        assert client.call("classify", {"item": "why worse?"}) == {"answer": "L2"}
        assert client.call("classify", {"item": "compare A/B"}) == {"answer": "L2"}


def test_startup_timeout_closes_the_process() -> None:
    client = StdioJudgmentClient(
        [sys.executable, "-c", "import time; time.sleep(60)"], timeout=0.05
    )
    with pytest.raises(JudgmentTransportError, match="timed out"), client:
        pytest.fail("startup must not succeed")
    with pytest.raises(JudgmentTransportError, match="not connected"):
        client.tools()


def test_closed_server_is_an_explicit_failure() -> None:
    with pytest.raises(JudgmentTransportError, match="closed"):
        with StdioJudgmentClient([sys.executable, "-c", "pass"], timeout=1):
            pytest.fail("empty server must not connect")
