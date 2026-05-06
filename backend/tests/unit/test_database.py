import pytest
import sqlite3
from datetime import datetime
from tars.database.base import Database, Session, Message, Memory
from tars.database.memory import MemoryExtractor, MemoryManager


class TestDatabase:
    def test_create_session(self, test_db):
        session = test_db.create_session(user_id="user1", title="Test Session")
        
        assert session.id is not None
        assert session.user_id == "user1"
        assert session.title == "Test Session"
        assert session.agent_id == "default"
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.updated_at, datetime)
        assert session.summary is None

    def test_get_session(self, test_db):
        session = test_db.create_session(user_id="user1")
        retrieved = test_db.get_session(session.id)
        
        assert retrieved is not None
        assert retrieved.id == session.id
        assert retrieved.user_id == "user1"

    def test_get_session_not_found(self, test_db):
        retrieved = test_db.get_session("nonexistent_id")
        assert retrieved is None

    def test_add_message(self, test_db):
        session = test_db.create_session()
        message = test_db.add_message(session.id, "user", "Hello TARS")
        
        assert message.id is not None
        assert message.session_id == session.id
        assert message.role == "user"
        assert message.content == "Hello TARS"
        assert isinstance(message.timestamp, datetime)

    def test_get_messages(self, test_db):
        session = test_db.create_session()
        test_db.add_message(session.id, "user", "Hello")
        test_db.add_message(session.id, "assistant", "Hi there!")
        
        messages = test_db.get_messages(session.id)
        
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert messages[0].content == "Hello"
        assert messages[1].content == "Hi there!"

    def test_add_memory(self, test_db):
        memory = test_db.add_memory(
            content="Test memory content",
            category="user_preference",
            importance=0.8
        )
        
        assert memory.id is not None
        assert memory.content == "Test memory content"
        assert memory.category == "user_preference"
        assert memory.importance == 0.8
        assert isinstance(memory.created_at, datetime)
        assert isinstance(memory.updated_at, datetime)

    def test_search_memories(self, test_db):
        test_db.add_memory(content="I like Python programming", category="user_preference")
        test_db.add_memory(content="I prefer dark mode", category="user_preference")
        test_db.add_memory(content="Project started on Monday", category="project_record")
        
        results = test_db.search_memories("Python")
        
        assert len(results) >= 1
        assert any("Python" in m.content for m in results)

    def test_get_memories_by_category(self, test_db):
        test_db.add_memory(content="Pref dark mode", category="user_preference", importance=0.7)
        test_db.add_memory(content="Pref Python", category="user_preference", importance=0.9)
        test_db.add_memory(content="Project X started", category="project_record")
        
        prefs = test_db.get_memories_by_category("user_preference")
        
        assert len(prefs) == 2
        assert prefs[0].importance == 0.9  # 按重要性降序

    def test_get_recent_memories(self, test_db):
        test_db.add_memory(content="Old memory", category="general")
        import time
        time.sleep(0.01)
        test_db.add_memory(content="New memory", category="general")
        
        recent = test_db.get_recent_memories(limit=1)
        
        assert len(recent) == 1
        assert recent[0].content == "New memory"

    def test_update_memory(self, test_db):
        memory = test_db.add_memory(content="Original content", category="general")
        original_time = memory.updated_at
        
        test_db.update_memory(memory.id, "Updated content", importance=0.9)
        
        updated = test_db.search_memories("Updated")
        assert len(updated) > 0
        assert updated[0].content == "Updated content"
        assert updated[0].importance == 0.9

    def test_delete_memory(self, test_db):
        memory = test_db.add_memory(content="To be deleted", category="general")
        memory_id = memory.id
        
        test_db.delete_memory(memory_id)
        
        results = test_db.search_memories("deleted")
        assert len(results) == 0


class TestMemoryExtractor:
    def test_extract_user_preference(self):
        extractor = MemoryExtractor()
        text = "我喜欢使用深色模式。我偏好简洁的界面。"
        
        memories = extractor.extract(text)
        
        assert len(memories) >= 2
        preferences = [m for m in memories if m['category'] == 'user_preference']
        assert len(preferences) >= 2

    def test_extract_important_decision(self):
        extractor = MemoryExtractor()
        text = "我们决定采用微服务架构。选择 Python 作为主要语言。"
        
        memories = extractor.extract(text)
        
        decisions = [m for m in memories if m['category'] == 'important_decision']
        assert len(decisions) >= 2

    def test_extract_project_record(self):
        extractor = MemoryExtractor()
        text = "完成了用户登录功能。启动了新的项目。"
        
        memories = extractor.extract(text)
        
        records = [m for m in memories if m['category'] == 'project_record']
        assert len(records) >= 2

    def test_calculate_importance(self):
        extractor = MemoryExtractor()
        
        assert extractor._calculate_importance("short", "general") == 0.5
        assert extractor._calculate_importance("short", "user_preference") == 0.7
        assert extractor._calculate_importance("short", "important_decision") == 0.8


class TestMemoryManager:
    def test_extract_and_save(self, test_db):
        manager = MemoryManager(test_db)
        conversation = "我喜欢 Python 编程。决定采用微服务架构。"
        
        memories = manager.extract_and_save(conversation)
        
        assert len(memories) > 0
        assert len(test_db.get_recent_memories()) == len(memories)

    def test_search_related(self, test_db):
        manager = MemoryManager(test_db)
        manager.add_manual_memory("Python is great", category="user_preference")
        manager.add_manual_memory("Java is OK", category="user_preference")
        
        results = manager.search_related("Python")
        
        assert len(results) >= 1
        assert any("Python" in m.content for m in results)

    def test_get_context_for_query(self, test_db):
        manager = MemoryManager(test_db)
        manager.add_manual_memory("User prefers dark mode", category="user_preference")
        
        context = manager.get_context_for_query("dark mode")
        
        assert "dark mode" in context
        assert "User prefers" in context

    def test_get_context_empty(self, test_db):
        manager = MemoryManager(test_db)
        
        context = manager.get_context_for_query("nonexistent")
        
        assert context == ""

    def test_get_user_preferences(self, test_db):
        manager = MemoryManager(test_db)
        manager.add_manual_memory("Pref dark", category="user_preference")
        manager.add_manual_memory("Project X", category="project_record")
        
        prefs = manager.get_user_preferences()
        
        assert len(prefs) == 1
        assert prefs[0].category == "user_preference"
