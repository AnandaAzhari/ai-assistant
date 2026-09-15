import unittest

from app.web_admin import WEB_ROOT, create_server, system_status


class WebAdminTests(unittest.TestCase):
    def test_status_contains_core_components(self):
        data = system_status()
        self.assertTrue(data['ok'])
        names = {item['name'] for item in data['components']}
        self.assertIn('Lead Agent', names)
        self.assertIn('Finance Agent', names)
        self.assertIn('TaqiDesk', names)

    def test_web_assets_exist(self):
        for name in ['index.html', 'style.css', 'app.js', 'voice.js', 'pwa.js', 'manifest.webmanifest', 'service-worker.js']:
            self.assertTrue((WEB_ROOT / name).is_file(), name)
        html = (WEB_ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertIn('micButton', html)
        self.assertIn('commandPalette', html)

    def test_server_can_bind_ephemeral_local_port(self):
        server = create_server('127.0.0.1', 0)
        try:
            self.assertGreater(server.server_address[1], 0)
        finally:
            server.server_close()


if __name__ == '__main__':
    unittest.main()
