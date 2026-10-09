import re
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

class ProductionTests(unittest.TestCase):
    def test_unique_migration_versions(self):
        versions = [p.name.split('__')[0] for p in (ROOT/'backend/src/main/resources/db/migration').glob('V*.sql')]
        self.assertEqual(len(versions), len(set(versions)))
    def test_seed_password_never_logged(self):
        source = (ROOT/'backend/src/main/java/com/aimall/backend/config/SeedDataInitializer.java').read_text(encoding='utf-8')
        self.assertNotIn('default password:', source)
    def test_no_public_demo_credentials(self):
        source = (ROOT/'frontend/src/views/LoginView.vue').read_text(encoding='utf-8')
        self.assertNotIn('密码均为 123456', source)
        self.assertIn('不产生真实扣款', source)
    def test_production_network_and_secrets(self):
        source = (ROOT/'deploy/compose.production.yml').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'127\.0\.0\.1:[0-9]+:[0-9]+', source), ['127.0.0.1:18100:80'])
        self.assertNotIn('root123456', source)
        self.assertIn('${JWT_SECRET:?', source)
        self.assertIn('${SEED_PASSWORD:?', source)
        self.assertIn('MYSQL_USERNAME: aimall', source)
        self.assertIn('restart: unless-stopped', source)
        self.assertIn('wget -q -O /dev/null http://127.0.0.1/', source)
    def test_nginx_hides_internal_routes(self):
        source = (ROOT/'deploy/aimall.nginx.conf').read_text(encoding='utf-8') + (ROOT/'deploy/aimall-proxy.conf').read_text(encoding='utf-8')
        for value in ['aimall.novo.ccwu.cc', 'location ^~ /internal/', 'location ^~ /actuator/', 'limit_req', 'X-Content-Type-Options', 'proxy_buffering off']:
            self.assertIn(value, source)
    def test_frontend_preserves_verified_visitor_ip(self):
        source = (ROOT/'deploy/frontend.production.conf').read_text(encoding='utf-8')
        self.assertIn('proxy_set_header X-Real-IP $http_x_real_ip;', source)
        self.assertIn('proxy_set_header X-Forwarded-For $http_x_forwarded_for;', source)
        self.assertIn('proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;', source)
    def test_simulated_payment_is_labeled(self):
        for filename in ['CartView.vue', 'ProductDetailView.vue']:
            source = (ROOT/'frontend/src/views'/filename).read_text(encoding='utf-8')
            self.assertNotIn('立即支付', source)
            self.assertIn('模拟支付', source)
    def test_subpath_deployment(self):
        router = (ROOT/'frontend/src/router/index.ts').read_text(encoding='utf-8')
        self.assertIn('createWebHistory(import.meta.env.BASE_URL)', router)
        for name in ['api/request.ts', 'api/index.ts', 'composables/useSseChat.ts']:
            source = (ROOT/'frontend/src'/name).read_text(encoding='utf-8')
            self.assertNotIn("fetch('/api/v1/", source)
            self.assertNotIn("baseURL: '/api/v1'", source)
        conf = (ROOT/'deploy/aimall.nginx.conf').read_text(encoding='utf-8')
        self.assertIn('location /aimall/', conf)
    def test_pdf_parser_has_audited_fix(self):
        source = (ROOT/'ai-service/requirements.txt').read_text(encoding='utf-8')
        self.assertIn('pypdf==6.19.0', source)
    def test_no_ip_fallback_is_installed(self):
        source = (ROOT/'deploy/ip-access.locations.conf').read_text(encoding='utf-8')
        self.assertNotIn('proxy_pass', source)
        self.assertIn('return 404;', source)
        config = (ROOT/'deploy/compose.production.yml').read_text(encoding='utf-8')
        self.assertIn('APP_CORS_ALLOWED_ORIGINS: https://aimall.novo.ccwu.cc\n', config)
        handoff = (ROOT/'deploy/admin-handoff.py').read_text(encoding='utf-8')
        self.assertNotIn('HTTPS fallback:', handoff)
    def test_cors_has_no_wildcard_credentials(self):
        source = (ROOT/'backend/src/main/java/com/aimall/backend/config/SecurityConfig.java').read_text(encoding='utf-8')
        self.assertNotIn('setAllowedOriginPatterns(List.of("*"))', source)
        self.assertIn('app.cors.allowed-origins', source)

if __name__ == '__main__': unittest.main()
