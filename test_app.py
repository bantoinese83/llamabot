import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock
from app import (
    save_message, load_chat_history, clear_chat_history, transcribe_audio,
    initialize_db, get_groq_models, load_configuration, save_feedback
)


class TestAppFunctions(unittest.TestCase):

    @patch('app.sessionmaker')
    def test_save_message(self, mock_sessionmaker):
        mock_session = MagicMock()
        mock_sessionmaker.return_value = mock_session
        mock_session.return_value = mock_session

        save_message("user", "Hello", "2024-08-12T21:54:44", {"id": "model-id"})

        mock_session.return_value.add.assert_called()
        mock_session.return_value.commit.assert_called()

    @patch('app.sessionmaker')
    def test_load_chat_history(self, mock_sessionmaker):
        mock_session = MagicMock()
        mock_sessionmaker.return_value = mock_session
        mock_session.return_value = mock_session

        mock_session.return_value.query.return_value.order_by.return_value.all.return_value = [
            MagicMock(role="user", content="Hello", timestamp=datetime(2024, 8, 12, 21, 54, 44), model_id="model-id")
        ]

        history = load_chat_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "Hello")

    @patch('app.sessionmaker')
    def test_clear_chat_history(self, mock_sessionmaker):
        mock_session = MagicMock()
        mock_sessionmaker.return_value = mock_session
        mock_session.return_value = mock_session

        clear_chat_history()

        mock_session.return_value.query.return_value.delete.assert_called()
        mock_session.return_value.commit.assert_called()

    @patch('app.Groq')
    def test_transcribe_audio(self, mock_groq):
        mock_client = mock_groq.return_value
        mock_client.audio.transcriptions.create.return_value.text = "Transcribed text"

        transcript = transcribe_audio(mock_client, "uploads/test_audio.mp3")
        self.assertEqual(transcript, "Transcribed text")

    @patch('app.create_engine')
    def test_initialize_db(self, mock_create_engine):
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        initialize_db()

        mock_engine.execute.assert_called()
        mock_engine.create_all.assert_called()

    @patch('app.requests.get')
    @patch('app.os.getenv')
    def test_get_groq_models(self, mock_getenv, mock_requests_get):
        mock_getenv.return_value = "fake_api_key"
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "data": [
                {"id": "model-1", "description": "Model 1 description"},
                {"id": "model-2", "description": "Model 2 description"}
            ]
        }
        mock_requests_get.return_value = mock_response

        models = get_groq_models()
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0]["name"], "model-1")
        self.assertEqual(models[1]["name"], "model-2")

    @patch('app.open', new_callable=unittest.mock.mock_open, read_data='{"GROQ_API_KEY": "fake_api_key"}')
    @patch('app.os.path.join')
    @patch('app.os.path.dirname')
    @patch('app.os.path.abspath')
    def test_load_configuration(self, mock_abspath, mock_dirname, mock_join, mock_open):
        mock_abspath.return_value = "/fake/path"
        mock_dirname.return_value = "/fake"
        mock_join.return_value = "/fake/path/config.json"

        config = load_configuration()
        self.assertEqual(config["GROQ_API_KEY"], "fake_api_key")

    @patch('app.sessionmaker')
    def test_save_feedback(self, mock_sessionmaker):
        mock_session = MagicMock()
        mock_sessionmaker.return_value = mock_session
        mock_session.return_value = mock_session

        save_feedback(1, True, "Great response!")

        mock_session.return_value.add.assert_called()
        mock_session.return_value.commit.assert_called()


if __name__ == '__main__':
    unittest.main()