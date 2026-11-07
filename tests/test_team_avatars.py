from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from pytest import raises

from editorial_desk.team_avatars import collect_team_avatars, attach_team_avatars, import_commissioner_team_avatars, choose_avatar


def image_bytes():
    buff = BytesIO()
    Image.new("RGB", (512, 400), (12, 22, 32)).save(buff, format="PNG")
    return buff.getvalue()


class Client:
    def league(self, league_id):
        return {"league_id": league_id, "season": "2026", "name": "Ironbound Sixteen"}

    def users(self, league_id):
        return [{"user_id": "u1", "display_name": "Manager",
                 "avatar": "account-avatar",
                 "metadata": {"team_name": "The Buckaneers", "avatar": "https://sleepercdn.com/uploads/team-original.png"}}]

    def rosters(self, league_id):
        return [{"roster_id": 9, "owner_id": "u1"}]


class Response:
    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield image_bytes()

    def close(self):
        pass


class Session:
    def get(self, url, **kwargs):
        assert url == "https://sleepercdn.com/uploads/team-original.png"
        return Response()


def league():
    return SimpleNamespace(key="ironbound_sixteen",
                           sleeper_league_id="1314016187998294016",
                           name="Ironbound Sixteen")


def test_team_avatar_precedes_account_avatar():
    assert choose_avatar(
        {"metadata": {"avatar": "https://sleepercdn.com/uploads/team-original.png"}, "avatar": "account-avatar"}, {}
    ) == ("https://sleepercdn.com/uploads/team-original.png", "user.metadata.avatar")


def test_collect_and_attach(tmp_path: Path):
    obj = league()
    root = tmp_path / "assets"
    manifest = collect_team_avatars(obj, root, client=Client(), session=Session())
    assert manifest["downloaded"] == 1
    assert manifest["teams"][0]["width"] == 512
    source = root / obj.key / "2026"
    assert (source / "roster-9-original.png").read_bytes() == image_bytes()
    assert (source / "roster-9.png").exists()
    issue = tmp_path / "week-09"
    issue.mkdir()
    packet = issue / "publication_packet.json"
    packet.write_text(json.dumps({"publication": "The Ironbound Weekly"}))
    attachment = attach_team_avatars(obj, root, issue, season="2026")
    assert attachment["attached"] == 1
    assert (issue / "publication-assets/team-avatars/roster-9.png").exists()
    assert json.loads(packet.read_text())["media_assets"]["team_avatars"]["teams"][0]["roster_id"] == 9


def test_attach_rejects_wrong_league(tmp_path: Path):
    obj = league()
    root = tmp_path / "assets"
    collect_team_avatars(obj, root, client=Client(), session=Session())
    wrong = SimpleNamespace(key=obj.key, sleeper_league_id="999", name="other")
    with raises(Exception, match="mismatch"):
        attach_team_avatars(wrong, root, tmp_path / "issue", season="2026")


def test_account_avatar_alone_is_not_team_artwork():
    assert choose_avatar({"avatar": "account-avatar", "metadata": {}}, {}) == (None, None)


def test_rejects_non_sleeper_urls():
    assert choose_avatar({"metadata": {"avatar": "https://evil.example/uploads/team.png"}}, {}) == (None, None)


def test_commissioner_images_survive_refresh(tmp_path: Path):
    obj = league()
    root = tmp_path / "assets"
    collect_team_avatars(obj, root, client=Client(), session=Session())
    override_dir = tmp_path / "overrides"
    override_dir.mkdir()
    (override_dir / "roster-9-original.jpg").write_bytes(_jpeg_bytes())
    result = import_commissioner_team_avatars(obj, root, override_dir, season="2026")
    assert result["imported_roster_ids"] == [9]
    assert result["manifest"]["teams"][0]["avatar_source"] == "commissioner_supplied"
    again = collect_team_avatars(obj, root, client=Client(), session=Session())
    assert again["teams"][0]["avatar_source"] == "commissioner_supplied"
    assert (root / obj.key / "2026" / "roster-9-original.jpg").read_bytes() == _jpeg_bytes()


def _jpeg_bytes():
    buf = BytesIO()
    Image.new("RGB", (400, 400), (240, 220, 2)).save(buf, format="JPEG")
    return buf.getvalue()
