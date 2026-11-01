"""数据目录备份端点集成测试（复用 conftest 的 client 夹具，数据目录指向临时目录）。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_backup_copies_data_dir(client: TestClient, tmp_path: Path) -> None:
    # conftest 把 BILIRAG_DATA_DIR 指向 tmp_path / "data"，且 lifespan 已建表（app.db 存在）
    data_dir = tmp_path / "data"

    resp = client.post("/api/backup")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"

    backup_dir = Path(data["backup_dir"])
    assert backup_dir.is_dir()
    assert backup_dir.parent.name == "backups"
    # 备份目录里应包含数据目录结构（至少 app.db）
    assert (backup_dir / "app.db").exists()
    assert (backup_dir / "chroma").is_dir()
    assert (backup_dir / "logs").is_dir()
    # 备份目标应位于数据目录同级，而不是数据目录内部（避免递归复制自身）
    assert data_dir not in backup_dir.parents
