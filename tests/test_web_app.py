import pytest
from unittest.mock import patch, MagicMock
from web_app import app as flask_app  # Use a different name to avoid conflict

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # This is a good place to add any app configuration needed for testing
    flask_app.config.update({
        "TESTING": True,
    })
    yield flask_app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@patch('web_app.llm_engine')
def test_chat_examine_success(mock_llm_engine, client):
    """
    Tests a successful "examine" command where the entity is resolved
    and new facts are generated.
    """
    # Arrange: Configure the mock LLM engine
    mock_llm_engine.resolve_entity.return_value = "polishing_rag_01"
    mock_llm_engine.generate_facts.return_value = [
        "It's a soft, well-used rag.",
        "You notice a small, embroidered 'B' in the corner."
    ]

    # Act: Send a POST request to the /chat endpoint
    response = client.post('/chat', json={'prompt': 'examine the rag'})

    # Assert: Check the response and the state
    assert response.status_code == 200
    json_data = response.get_json()
    assert "It's a soft, well-used rag." in json_data['response']
    assert "You notice a small, embroidered 'B' in the corner." in json_data['response']

    # Verify that the mock methods were called correctly
    mock_llm_engine.resolve_entity.assert_called_once()
    mock_llm_engine.generate_facts.assert_called_once()


@patch('web_app.llm_engine')
def test_chat_examine_unresolved(mock_llm_engine, client):
    """
    Tests the case where the entity cannot be resolved.
    """
    # Arrange: Configure the mock to simulate failure
    mock_llm_engine.resolve_entity.return_value = None

    # Act
    response = client.post('/chat', json={'prompt': 'examine the weird doodad'})

    # Assert
    assert response.status_code == 200
    json_data = response.get_json()
    assert "You don't see any" in json_data['response']
    assert "weird doodad" in json_data['response']

    # Verify that resolve_entity was called, but generate_facts was not
    mock_llm_engine.resolve_entity.assert_called_once()
    mock_llm_engine.generate_facts.assert_not_called() 