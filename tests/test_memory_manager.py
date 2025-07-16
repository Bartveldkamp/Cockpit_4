import pytest
from unittest.mock import patch, MagicMock
from backend.memory import MemoryManager

@pytest.fixture
def mock_memory_manager():
    with patch('backend.memory.SentenceTransformer') as MockSentenceTransformer:
        with patch('backend.memory.chromadb.PersistentClient') as MockPersistentClient:
            with patch('backend.memory.settings') as MockSettings:
                MockSettings.embedding_model = 'test-model'
                MockSettings.chroma_path = 'test-path'
                MockSettings.collection_name = 'test-collection'

                mock_model = MockSentenceTransformer.return_value
                mock_model.encode.return_value = [0.1, 0.2, 0.3]

                mock_client = MockPersistentClient.return_value
                mock_collection = MagicMock()
                mock_client.get_or_create_collection.return_value = mock_collection

                memory_manager = MemoryManager()
                memory_manager.model = mock_model
                memory_manager.collection = mock_collection

                yield memory_manager

def test_memory_manager_initialization(mock_memory_manager):
    assert mock_memory_manager.model is not None
    assert mock_memory_manager.collection is not None

def test_add_to_memory(mock_memory_manager):
    mock_memory_manager.add_to_memory("test content", "test_file.txt", "session123")
    mock_memory_manager.collection.upsert.assert_called_once_with(
        ids=["session123:test_file.txt"],
        embeddings=[[0.1, 0.2, 0.3]],
        documents=["test content"],
        metadatas=[{"filename": "test_file.txt", "session_id": "session123"}]
    )

def test_add_to_memory_failure(mock_memory_manager):
    mock_memory_manager.model = None
    with patch('backend.memory.logger.error') as mock_logger_error:
        mock_memory_manager.add_to_memory("test content", "test_file.txt", "session123")
        mock_logger_error.assert_called_once_with("Cannot add to memory, MemoryManager not initialized.")

def test_retrieve_from_memory(mock_memory_manager):
    mock_memory_manager.collection.query.return_value = {'documents': [["doc1", "doc2"]]}
    results = mock_memory_manager.retrieve_from_memory("query text")
    assert results == ["doc1", "doc2"]
    mock_memory_manager.collection.query.assert_called_once_with(
        query_embeddings=[[0.1, 0.2, 0.3]],
        n_results=3
    )

def test_retrieve_from_memory_empty_query(mock_memory_manager):
    results = mock_memory_manager.retrieve_from_memory("")
    assert results == []

def test_retrieve_from_memory_failure(mock_memory_manager):
    mock_memory_manager.collection.query.side_effect = Exception("Query failed")
    with patch('backend.memory.logger.error') as mock_logger_error:
        results = mock_memory_manager.retrieve_from_memory("query text")
        assert results == []
        mock_logger_error.assert_called_once_with("Failed to retrieve from memory: Query failed")

def test_memory_manager_initialization_failure():
    with patch('backend.memory.SentenceTransformer', side_effect=Exception("Initialization failed")):
        with patch('backend.memory.logger.error') as mock_logger_error:
            memory_manager = MemoryManager()
            assert memory_manager.model is None
            assert memory_manager.collection is None
            mock_logger_error.assert_called_once_with("Failed to initialize MemoryManager: Initialization failed", exc_info=True)

