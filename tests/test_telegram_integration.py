import io
import json
import os
import sqlite3
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from app.admin_runtime import create_admin_lead
from app.lead import LeadReply
from app.providers.base import ModelReply
from app.telegram import AdminIdentity, TelegramAdminAdapter, TelegramError, TelegramHTTPClient, text_chunks
from app.telegram_store import TelegramUpdateStore
from app.telegram_lock import TelegramAlreadyRunning, telegram_process_lock
from telegram_main import discover_admin, main, positive_int


def update(index=10, text='/status', user=123, chat=123, kind='private'):
    return {'update_id': index, 'message': {'from': {'id': user}, 'chat': {'id': chat, 'type': kind}, 'text': text}}


class Client:
    def __init__(self):
        self.sent = []
        self.fail_at = None
        self.batches = []
        self.offsets = []

    def send_message(self, chat, text):
        if self.fail_at == len(self.sent):
            self.fail_at = None
            raise TelegramError('simulated timeout')
        self.sent.append((chat, text))

    def get_updates(self, *, offset=None, timeout=30):
        self.offsets.append(offset)
        if not self.batches:
            raise KeyboardInterrupt
        item = self.batches.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class TelegramDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'telegram.db'
        self.store = TelegramUpdateStore(self.db, 9)
        self.client = Client()
        self.handler = Mock(return_value=LeadReply('lead', 'berhasil', 'Selesai'))
        self.adapter = TelegramAdminAdapter(self.client, AdminIdentity(123), self.handler, store=self.store)

    def test_authorized_private_chat_only(self):
        for event in [update(user=999), update(chat=999), update(kind='group'), update(kind='supergroup'),
                      {'update_id': 10, 'message': {'from': None, 'chat': None}},
                      {'update_id': 10, 'edited_message': update()['message']}]:
            self.assertFalse(self.adapter.process_update(event))
        self.handler.assert_not_called()
        self.assertEqual(self.client.sent, [])

    def test_command_suffix_is_normalized(self):
        self.adapter.process_update(update(text='/makalah_baru@existing_bot'))
        self.handler.assert_called_once_with('/makalah_baru')

    def test_repeat_after_restart_does_not_repeat_action_or_reply(self):
        self.adapter.process_update(update())
        other = TelegramAdminAdapter(self.client, AdminIdentity(123), self.handler,
                                     store=TelegramUpdateStore(self.db, 9))
        other.process_update(update())
        self.handler.assert_called_once()
        self.assertEqual(len(self.client.sent), 1)

    def test_reply_failure_retries_reply_without_repeating_handler(self):
        self.client.fail_at = 0
        with self.assertRaises(TelegramError):
            self.adapter.process_update(update())
        self.assertEqual(self.store.get(10)['state'], 'ready')
        self.adapter.flush_pending()
        self.adapter.process_update(update())
        self.handler.assert_called_once()
        self.assertEqual(self.client.sent, [(123, 'Selesai')])

    def test_long_reply_is_delivered_in_full_and_resumes_at_failed_chunk(self):
        text = 'Kerangka makalah\n' + ('📝' * 2500) + '\n' + ('Pembahasan ' * 1200) + 'AKHIR'
        self.handler.return_value = LeadReply('document', 'berhasil', text)
        self.client.fail_at = 1
        with self.assertRaises(TelegramError):
            self.adapter.process_update(update())
        self.assertEqual(self.store.get(10)['sent_chunks'], 1)
        self.adapter.flush_pending()
        self.assertEqual(''.join(t for _, t in self.client.sent), text)
        self.assertTrue(all(len(t.encode('utf-16-le')) // 2 <= 3500 for _, t in self.client.sent))
        self.handler.assert_called_once()

    def test_splitter_handles_newline_followed_by_surrogate_boundary(self):
        text = '\n' + 'a' * 3499 + '📝'
        parts = text_chunks(text)
        self.assertEqual(''.join(parts), text)
        self.assertTrue(all(len(t.encode('utf-16-le')) // 2 <= 3500 for t in parts))

    def test_interrupted_processing_is_reported_without_replaying_business_action(self):
        self.store.reserve(10, 123)
        self.adapter.flush_pending()
        self.adapter.process_update(update())
        self.handler.assert_not_called()
        self.assertIn('terhenti', self.client.sent[0][1])
        self.assertEqual(len(self.client.sent), 1)

    def test_pending_messages_of_other_owner_are_not_sent(self):
        self.store.reserve(10, 999)
        self.store.complete(10, 'Data privat owner lama')
        self.adapter.flush_pending()
        self.assertFalse(self.adapter.process_update(update()))
        self.assertEqual(self.client.sent, [])
        self.handler.assert_not_called()

    def test_new_bot_has_separate_update_history(self):
        self.adapter.process_update(update())
        other = TelegramAdminAdapter(self.client, AdminIdentity(123), self.handler,
                                     store=TelegramUpdateStore(self.db, 22))
        other.process_update(update())
        self.assertEqual(self.handler.call_count, 2)

    def test_handler_failure_does_not_break_following_message(self):
        self.handler.side_effect = [RuntimeError('PRIVATE'), LeadReply('lead', 'berhasil', 'berikutnya')]
        with redirect_stdout(io.StringIO()) as out:
            self.adapter.process_update(update(10))
            self.adapter.process_update(update(11))
        self.assertNotIn('PRIVATE', out.getvalue())
        self.assertEqual(self.client.sent[-1][1], 'berikutnya')

    def test_polling_persists_offset_and_recovers_delivery(self):
        self.client.batches = [[update(10)], [update(10), update(11, user=999)]]
        self.client.fail_at = 0
        with patch('app.telegram.time.sleep'), redirect_stdout(io.StringIO()):
            self.adapter.run_forever()
        self.handler.assert_called_once()
        self.assertEqual(self.store.offset(), 12)
        self.assertEqual(len(self.client.sent), 1)
        restarted_client = Client()
        restarted = TelegramAdminAdapter(restarted_client, AdminIdentity(123), self.handler, store=self.store)
        restarted.run_forever()
        self.assertEqual(restarted_client.offsets, [12])

    def test_permanent_polling_error_stops_instead_of_retrying_forever(self):
        self.client.batches = [TelegramError('conflict', retryable=False)]
        with self.assertRaises(TelegramError), patch('app.telegram.time.sleep') as sleep:
            self.adapter.run_forever()
        sleep.assert_not_called()

    def test_unsupported_photo_never_enters_finance_or_document_handler(self):
        event = update()
        event['message'].pop('text')
        event['message']['photo'] = [{'file_id': 'fake'}]
        self.adapter.process_update(event)
        self.handler.assert_not_called()
        self.assertIn('pesan teks', self.client.sent[0][1])

    def test_store_failure_stops_before_handler(self):
        with patch.object(self.store, 'reserve', side_effect=sqlite3.OperationalError('disk')):
            with self.assertRaises(sqlite3.Error):
                self.adapter.process_update(update())
        self.handler.assert_not_called()


class TelegramHTTPTests(unittest.TestCase):
    def setUp(self):
        self.client = TelegramHTTPClient('123:SECRET_TOKEN')

    def response(self, data):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(data).encode()
        return response

    def test_api_errors_never_expose_token_or_raw_description(self):
        for code in [400, 401, 403, 404, 409, 429, 500]:
            with self.subTest(code=code):
                error = urllib.error.HTTPError('https://api.telegram.org/bot123:SECRET_TOKEN/sendMessage', code,
                    'SECRET_TOKEN', {}, io.BytesIO(json.dumps({'ok': False, 'description': 'SECRET_TOKEN',
                        'parameters': {'retry_after': 2}}).encode()))
                with patch('urllib.request.urlopen', side_effect=error):
                    with self.assertRaises(TelegramError) as raised:
                        self.client.send_message(123, 'hi')
                self.assertNotIn('SECRET_TOKEN', str(raised.exception))
                self.assertEqual(raised.exception.retryable, code == 429 or code >= 500)

    def test_network_error_is_redacted(self):
        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError('SECRET_TOKEN')):
            with self.assertRaises(TelegramError) as raised:
                self.client.get_me()
        self.assertNotIn('SECRET_TOKEN', str(raised.exception))

    def test_message_is_not_silently_truncated(self):
        with patch('urllib.request.urlopen') as network:
            with self.assertRaises(ValueError):
                self.client.send_message(123, 'a' * 4097)
        network.assert_not_called()

    def test_false_ok_response_is_rejected(self):
        with patch('urllib.request.urlopen', return_value=self.response({'ok': False, 'error_code': 401})):
            with self.assertRaises(TelegramError) as raised:
                self.client.get_me()
        self.assertFalse(raised.exception.retryable)

    def test_send_message_preserves_text_and_does_not_enable_markdown_parsing(self):
        from urllib.parse import parse_qs
        with patch('urllib.request.urlopen', return_value=self.response({'ok': True, 'result': {}})) as call:
            self.client.send_message(123, '*Judul* [contoh] _nama_')
        body = parse_qs(call.call_args.args[0].data.decode())
        self.assertEqual(body['text'], ['*Judul* [contoh] _nama_'])
        self.assertNotIn('parse_mode', body)


class TelegramStartupTests(unittest.TestCase):
    def test_ids_must_be_positive_private_chat_ids(self):
        for value in ('abc', '0', '-100123'):
            with self.assertRaises(ValueError):
                positive_int('ID', value)
        self.assertEqual(positive_int('ID', '123'), 123)
        self.assertIsNone(positive_int('ID', '', required=False))
        self.assertEqual(AdminIdentity(123).effective_chat_id, 123)

    def test_pairing_requires_exact_one_time_message_in_private_chat(self):
        client = Client()
        client.batches = [[update(1, '/start', user=999), update(2, '/hubungkan CODE', kind='group'),
                           update(3, '/hubungkan WRONG'), update(4, '/hubungkan CODE')]]
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(discover_admin(client, challenge='CODE'), 0)
        self.assertIn('TELEGRAM_ADMIN_USER_ID=123', out.getvalue())
        self.assertNotIn('TELEGRAM_ADMIN_USER_ID=999', out.getvalue())
        self.assertEqual(client.sent, [])

    def test_check_is_read_only_and_does_not_build_services(self):
        client = Mock()
        client.get_me.return_value = {'id': 9, 'is_bot': True, 'username': 'existing_bot'}
        client.get_webhook_info.return_value = {'url': ''}
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'dummy', 'TELEGRAM_ADMIN_USER_ID': '123',
                                    'TELEGRAM_ADMIN_CHAT_ID': ''}), patch('telegram_main.load_env'), \
             patch('telegram_main.TelegramHTTPClient', return_value=client), \
             patch('telegram_main.create_admin_lead') as runtime, redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--check']), 0)
        runtime.assert_not_called()
        client.send_message.assert_not_called()
        client.delete_webhook.assert_not_called()

    def test_existing_webhook_is_not_removed_without_explicit_flag(self):
        client = Mock()
        client.get_me.return_value = {'id': 9, 'is_bot': True}
        client.get_webhook_info.return_value = {'url': 'https://existing.example/secret'}
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'dummy'}), patch('telegram_main.load_env'), \
             patch('telegram_main.TelegramHTTPClient', return_value=client), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(['--check']), 2)
        client.delete_webhook.assert_not_called()
        self.assertNotIn('existing.example', out.getvalue())


class TelegramRuntimeTests(unittest.TestCase):
    def test_second_local_runtime_is_blocked_and_lock_is_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bot.lock'
            with telegram_process_lock(path):
                with self.assertRaises(TelegramAlreadyRunning):
                    with telegram_process_lock(path):
                        self.fail('Second runtime acquired the same lock')
            with telegram_process_lock(path):
                pass

    def test_real_services_shared_ledger_but_isolated_document_sessions(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
            'DATABASE_PATH': str(Path(tmp) / 'assistant.db'), 'DOCUMENT_WORKSPACE': str(Path(tmp) / 'documents'),
            'DEEPSEEK_API_KEY': '', 'GOOGLE_SHEETS_WEBHOOK_URL': '', 'GOOGLE_SHEETS_SYNC_SECRET': ''}):
            telegram = create_admin_lead(channel='telegram', document_scope='DOCSRC-TELEGRAM-test')
            web = create_admin_lead(channel='web', document_scope='DOCSRC-WEB-test')
            self.assertIsNotNone(telegram.finance)
            self.assertIsNotNone(telegram.document.engine)
            self.assertIsNotNone(telegram.document.session_store)
            self.assertIn('Telegram Admin: terhubung', telegram.handle_admin_message('/status').text)
            self.assertNotIn('Web Admin: terhubung', telegram.handle_admin_message('/status').text)
            client = Client()
            adapter = TelegramAdminAdapter(client, AdminIdentity(123), telegram.handle_admin_message,
                store=TelegramUpdateStore(Path(tmp) / 'assistant.db', 9))
            event = update(text='Catat pengeluaran 80 ribu beli tinta untuk Taqi DocuTech pakai BCA')
            adapter.process_update(event)
            adapter.process_update(event)
            self.assertEqual(telegram.finance.balances()['BCA'], -80000)
            self.assertEqual(web.finance.balances()['BCA'], -80000)
            self.assertEqual(telegram.finance.today_summary()['count'], 1)
            adapter.process_update(update(11, 'Saya mau makalah tentang AI Agent, 8 halaman'))
            saved_topic = telegram.document.brief.topic_title
            self.assertIn('AI Agent', saved_topic)
            self.assertEqual(web.document.brief.topic_title, '')
            restored = create_admin_lead(channel='telegram', document_scope='DOCSRC-TELEGRAM-test')
            self.assertEqual(restored.document.brief.topic_title, saved_topic)
            self.assertEqual(restored.document.brief.target_length, '8 halaman')

    def test_nara_ai_is_called_from_telegram(self):
        provider = Mock(configured=True, provider_name='test', model_name='test')
        provider.generate.return_value = ModelReply('berhasil', json.dumps({
            'brief': {'topic_title': 'AI Agent', 'target_length': '8 halaman'}, 'cover': {},
            'evidence': {'brief.topic_title': 'AI Agent', 'brief.target_length': '8 halaman'},
            'intent': 'update', 'reply': '', 'clarification': ''}), 'test', 'test')
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'DATABASE_PATH': str(Path(tmp) / 'db')}), \
             patch('app.admin_runtime.DeepSeekProvider.from_env', return_value=provider):
            lead = create_admin_lead(channel='telegram', document_scope='telegram-ai')
            client = Client()
            adapter = TelegramAdminAdapter(client, AdminIdentity(123), lead.handle_admin_message)
            adapter.process_update(update(text='Saya mau makalah AI Agent, 8 halaman'))
            provider.generate.assert_called_once()
            self.assertEqual(lead.document.brief.topic_title, 'AI Agent')
            self.assertIn('Nara — Document Agent', provider.generate.call_args.args[0][0]['content'])
            self.assertTrue(client.sent)


if __name__ == '__main__':
    unittest.main()
