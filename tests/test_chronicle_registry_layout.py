import json

from editorial_desk.chronicle_identity import IdentityRegistry
from editorial_desk.chronicle_store import ChronicleStore


def test_identity_registry_writes_human_readable_projection_files(tmp_path):
    store = ChronicleStore(tmp_path)
    registry = IdentityRegistry.empty()
    registry.register_dynasty_season(
        league_key="dynasty",
        season="2025",
        roster_id=1,
        owner_id="owner-a",
        team_name="Old Forge",
        manager_name="Alice",
    )
    registry.register_redraft_season(
        league_key="redraft",
        season="2025",
        roster_id=2,
        owner_id="owner-b",
        team_name="Saturday Team",
        manager_name="Bob",
    )

    store.write_identity_registry(registry)

    registry_root = tmp_path / "registry"
    assert (registry_root / "identity.json").exists()
    assert (registry_root / "franchises.json").exists()
    assert (registry_root / "managers.json").exists()
    assert (registry_root / "ambiguities.json").exists()

    franchises = json.loads((registry_root / "franchises.json").read_text())
    managers = json.loads((registry_root / "managers.json").read_text())
    ambiguities = json.loads((registry_root / "ambiguities.json").read_text())
    assert franchises["dynasty_mappings"]
    assert managers["redraft_mappings"]
    assert ambiguities == {"ambiguities": []}
