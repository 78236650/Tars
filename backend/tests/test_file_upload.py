"""TARS 文件上传与多模态功能测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime


class TestFileModels:
    def test_file_record(self):
        from tars.files.models import FileRecord
        rec = FileRecord(
            file_id="f_test123",
            name="photo.png",
            type="image",
            mime_type="image/png",
            size=1024,
            path="/tmp/photo.png",
            created_at=datetime.now(),
        )
        assert rec.file_id == "f_test123"
        assert rec.type == "image"
        d = rec.to_dict()
        assert d["name"] == "photo.png"

    def test_parsed_content(self):
        from tars.files.models import ParsedContent
        pc = ParsedContent(type="text", text="hello world")
        assert pc.text == "hello world"
        assert pc.truncated is False
        assert pc.image_base64 is None


class TestFileStorage:
    @pytest.mark.asyncio
    async def test_save_and_get(self, tmp_path):
        from tars.files.storage import FileStorage
        storage = FileStorage(upload_dir=str(tmp_path))

        record = await storage.save("test.txt", b"hello world")
        assert record.file_id.startswith("f_")
        assert record.name == "test.txt"
        assert record.type == "document"
        assert record.size == 11

        retrieved = storage.get(record.file_id)
        assert retrieved is not None
        assert retrieved.file_id == record.file_id

    @pytest.mark.asyncio
    async def test_save_image(self, tmp_path):
        from tars.files.storage import FileStorage
        storage = FileStorage(upload_dir=str(tmp_path))

        record = await storage.save("photo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        assert record.type == "image"
        assert record.mime_type == "image/png"

    @pytest.mark.asyncio
    async def test_delete(self, tmp_path):
        from tars.files.storage import FileStorage
        storage = FileStorage(upload_dir=str(tmp_path))

        record = await storage.save("temp.txt", b"temp")
        assert storage.delete(record.file_id) is True
        assert storage.get(record.file_id) is None

    def test_delete_nonexistent(self, tmp_path):
        from tars.files.storage import FileStorage
        storage = FileStorage(upload_dir=str(tmp_path))
        assert storage.delete("f_nonexistent") is False

    @pytest.mark.asyncio
    async def test_detect_types(self, tmp_path):
        from tars.files.storage import FileStorage
        storage = FileStorage(upload_dir=str(tmp_path))

        for name, expected_type in [
            ("doc.pdf", "document"),
            ("code.py", "document"),
            ("data.csv", "document"),
            ("img.jpg", "image"),
            ("img.webp", "image"),
        ]:
            rec = await storage.save(name, b"x")
            assert rec.type == expected_type, f"{name} should be {expected_type}"


class TestFileParser:
    @pytest.mark.asyncio
    async def test_parse_text_file(self, tmp_path):
        from tars.files.parser import FileParser
        from tars.files.models import FileRecord

        test_file = tmp_path / "hello.txt"
        test_file.write_text("Hello World\nLine 2")

        parser = FileParser()
        record = FileRecord(
            file_id="f_1", name="hello.txt", type="document",
            mime_type="text/plain", size=100, path=str(test_file),
            created_at=datetime.now(),
        )
        result = await parser.parse(record)
        assert result.type == "text"
        assert "Hello World" in result.text
        assert result.truncated is False

    @pytest.mark.asyncio
    async def test_parse_text_truncation(self, tmp_path):
        from tars.files.parser import FileParser, MAX_TEXT_LENGTH
        from tars.files.models import FileRecord

        big_file = tmp_path / "big.txt"
        big_file.write_text("x" * (MAX_TEXT_LENGTH + 1000))

        parser = FileParser()
        record = FileRecord(
            file_id="f_2", name="big.txt", type="document",
            mime_type="text/plain", size=MAX_TEXT_LENGTH + 1000, path=str(big_file),
            created_at=datetime.now(),
        )
        result = await parser.parse(record)
        assert result.truncated is True
        assert len(result.text) == MAX_TEXT_LENGTH

    @pytest.mark.asyncio
    async def test_parse_image(self, tmp_path):
        from tars.files.parser import FileParser
        from tars.files.models import FileRecord
        from PIL import Image

        img_path = tmp_path / "test.png"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(img_path)

        parser = FileParser()
        record = FileRecord(
            file_id="f_3", name="test.png", type="image",
            mime_type="image/png", size=100, path=str(img_path),
            created_at=datetime.now(),
        )
        result = await parser.parse(record)
        assert result.type == "image"
        assert result.image_base64 is not None
        assert len(result.image_base64) > 0

    @pytest.mark.asyncio
    async def test_parse_csv(self, tmp_path):
        from tars.files.parser import FileParser
        from tars.files.models import FileRecord

        csv_file = tmp_path / "data.csv"
        csv_file.write_text("name,age\nAlice,30\nBob,25")

        parser = FileParser()
        record = FileRecord(
            file_id="f_4", name="data.csv", type="document",
            mime_type="text/csv", size=100, path=str(csv_file),
            created_at=datetime.now(),
        )
        result = await parser.parse(record)
        assert result.type == "text"
        assert "Alice" in result.text


class TestFileUploadAPI:
    @pytest.fixture
    def client(self, tmp_path):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from tars.api.files import router, init_file_storage
        from tars.files.storage import FileStorage

        app = FastAPI()
        app.include_router(router)

        storage = FileStorage(upload_dir=str(tmp_path))
        init_file_storage(storage)

        return TestClient(app)

    def test_upload_text_file(self, client):
        resp = client.post(
            "/api/files/upload",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["file"]["name"] == "test.txt"
        assert data["file"]["type"] == "document"
        assert data["file"]["file_id"].startswith("f_")

    def test_upload_image(self, client):
        from PIL import Image
        import io
        buf = io.BytesIO()
        Image.new("RGB", (50, 50), "blue").save(buf, format="PNG")
        buf.seek(0)

        resp = client.post(
            "/api/files/upload",
            files={"file": ("photo.png", buf.getvalue(), "image/png")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["file"]["type"] == "image"
        assert data["file"]["preview"].startswith("data:image/")

    def test_upload_too_large(self, client):
        big_content = b"x" * (51 * 1024 * 1024)
        resp = client.post(
            "/api/files/upload",
            files={"file": ("big.bin", big_content, "application/octet-stream")},
        )
        assert resp.status_code == 413

    def test_get_file_info(self, client):
        # 先上传
        resp = client.post(
            "/api/files/upload",
            files={"file": ("info.txt", b"content", "text/plain")},
        )
        file_id = resp.json()["file"]["file_id"]

        # 获取信息
        resp2 = client.get(f"/api/files/{file_id}")
        assert resp2.status_code == 200
        assert resp2.json()["file"]["name"] == "info.txt"

    def test_get_file_not_found(self, client):
        resp = client.get("/api/files/f_nonexistent")
        assert resp.status_code == 404

    def test_delete_file(self, client):
        resp = client.post(
            "/api/files/upload",
            files={"file": ("del.txt", b"delete me", "text/plain")},
        )
        file_id = resp.json()["file"]["file_id"]

        resp2 = client.delete(f"/api/files/{file_id}")
        assert resp2.status_code == 200
        assert resp2.json()["success"] is True

        resp3 = client.get(f"/api/files/{file_id}")
        assert resp3.status_code == 404


class TestAgentMultimodal:
    def test_is_multimodal(self):
        from tars.agent.agent import AgentV2
        agent = AgentV2.__new__(AgentV2)
        agent.current_model = "llava:latest"
        assert agent._is_multimodal() is True

        agent.current_model = "qwen3:4b"
        assert agent._is_multimodal() is False

        agent.current_model = "minicpm-v:latest"
        assert agent._is_multimodal() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
