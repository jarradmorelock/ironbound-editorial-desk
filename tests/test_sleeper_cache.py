from editorial_desk.sleeper import SleeperClient


class Response:
    def __init__(self):
        self.calls = 0

    def raise_for_status(self):
        return None

    def json(self):
        return {"1": {"full_name": "Player One"}}


class Session:
    def __init__(self):
        self.calls = 0

    def get(self, url, headers, timeout):
        self.calls += 1
        return Response()


def test_player_directory_is_cached_within_collection_run():
    session = Session()
    client = SleeperClient(session=session)

    first = client.players()
    second = client.players()

    assert first == second
    assert session.calls == 1
