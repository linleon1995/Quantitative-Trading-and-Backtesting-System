import unittest
from unittest.mock import MagicMock, patch

# Assuming src is on the PYTHONPATH or tests are run in a way that src is discoverable
# For example, running `python -m unittest discover -s tests` from the root directory
try:
    from src.event.telegram_bot import TOKEN, send_msg
    # If CHAT_ID were a module global used by send_msg, it would be imported here too.
except ImportError:
    # Fallback for environments where src might not be directly in PYTHONPATH
    # This might happen in some CI or execution environments.
    # Adjust as necessary based on actual project structure and test execution.
    import os
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
    from src.event.telegram_bot import send_msg

from requests.exceptions import RequestException  # Import RequestException

# Disable logging for most tests to keep output clean, can be enabled for debugging
# logging.disable(logging.CRITICAL)

class TestSendMsgRetry(unittest.TestCase):

    @patch('src.event.telegram_bot.TOKEN', 'test_token_value') # Mock module-level TOKEN
    @patch('src.event.telegram_bot.requests.post')
    def test_send_msg_success_on_first_attempt(self, mock_post):
        # Configure the mock to return a successful response
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None # Simulate successful status
        mock_response.text = 'Success'
        mock_post.return_value = mock_response

        # Call send_msg
        # The chat_id is hardcoded in send_msg, so we don't need to pass/mock it here
        # If it were a parameter or global, we'd handle it.
        send_msg("test message")

        # Assert that mock_post was called once
        self.assertEqual(mock_post.call_count, 1)
        # Assert call arguments (optional, but good for verification)
        expected_url = "https://api.telegram.org/bottest_token_value/sendMessage"
        expected_payload = {'chat_id': '1745246461', 'text': "test message"} # chat_id is hardcoded in send_msg
        mock_post.assert_called_once_with(expected_url, data=expected_payload)

        # Optionally, check for a success log message (requires log capturing setup)
        # For example, using self.assertLogs from unittest if Python 3.4+
        # with self.assertLogs(logger='src.event.telegram_bot', level='INFO') as cm:
        #     send_msg("test message") # Call again or integrate into above call
        #     self.assertIn("Message sent successfully", cm.output[0])

    @patch('src.event.telegram_bot.TOKEN', 'test_token_value')
    @patch('src.event.telegram_bot.time.sleep') # Mock time.sleep
    @patch('src.event.telegram_bot.requests.post') # Mock requests.post
    def test_send_msg_success_after_retries(self, mock_post, mock_sleep):
        # Configure mock_post to raise exceptions first, then succeed
        mock_response_success = MagicMock()
        mock_response_success.raise_for_status.return_value = None
        mock_response_success.text = 'Success'

        mock_post.side_effect = [
            RequestException("Network error"),
            RequestException("Timeout"),
            mock_response_success
        ]

        send_msg("test message for retry success")

        # Assert mock_post was called three times
        self.assertEqual(mock_post.call_count, 3)

        # Assert mock_sleep was called twice
        self.assertEqual(mock_sleep.call_count, 2)
        # Optionally check sleep durations if important, e.g.
        # self.assertTrue(mock_sleep.call_args_list[0][0][0] >= 1) # First delay >= base_delay
        # self.assertTrue(mock_sleep.call_args_list[1][0][0] >= 2) # Second delay >= base_delay * 2

        # Verify arguments for the successful call
        expected_url = "https://api.telegram.org/bottest_token_value/sendMessage"
        expected_payload = {'chat_id': '1745246461', 'text': "test message for retry success"}
        mock_post.assert_called_with(expected_url, data=expected_payload) # assert_called_with checks the last call

    @patch('src.event.telegram_bot.TOKEN', 'test_token_value')
    @patch('src.event.telegram_bot.time.sleep') # Mock time.sleep
    @patch('src.event.telegram_bot.requests.post') # Mock requests.post
    def test_send_msg_failure_after_max_retries(self, mock_post, mock_sleep):
        # Configure mock_post to always raise an exception
        mock_post.side_effect = RequestException("Persistent error")

        send_msg("test message for max retries failure")

        # Assert mock_post was called 5 times (max_retries)
        self.assertEqual(mock_post.call_count, 5)

        # Assert mock_sleep was called 4 times (max_retries - 1)
        self.assertEqual(mock_sleep.call_count, 4)

        # Optionally, check for log messages indicating max retries reached.
        # This would require setting up log capturing.
        # Example using self.assertLogs:
        # with self.assertLogs(logger='src.event.telegram_bot', level='ERROR') as cm:
        #     send_msg("test message for max retries failure") # Call again or integrate
        #     # Check for the specific log message related to max retries
        #     self.assertTrue(any("Max retries reached for send_msg" in log_msg for log_msg in cm.output))
        #     self.assertTrue(any("Failed to send message after all retries" in log_msg for log_msg in cm.output))


# Placeholder for main function resilience tests
class TestMainResilience(unittest.TestCase):
    @unittest.skip("Integration test for main loop resilience is complex to automate here")
    def test_main_restarts_updater_on_network_error(self):
        '''
        This test would ideally verify that the main() function in telegram_bot.py
        restarts the Updater if it encounters a NetworkError.

        Approach:
        1. Mock telegram.ext.Updater.
        2. Mock updater_instance.start_polling to raise NetworkError after some calls,
           or mock updater_instance.idle to raise it.
        3. Run main() in a separate thread for a short duration or until a few restarts occur.
        4. Use mock.patch on logging to capture log messages.
        5. Assert that "Updater crashed with NetworkError/TimedOut" and
           "Reconnection attempt successful" messages are logged.
        6. Assert that Updater is instantiated multiple times.
        '''
        pass

if __name__ == '__main__':
    unittest.main()
