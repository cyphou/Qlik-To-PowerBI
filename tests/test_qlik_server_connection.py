"""Tests for Qlik server connection / TLS / certificate diagnostics.

Network-free: exercises the building blocks of ``QlikServerClient.test_connection``
(Xrfkey application, certificate field checks, scheme validation, cert-file
validation) without contacting a live server.
"""

import time

import pytest

from qlik_export.qlik_server_client import QlikServerClient


def _client(url='https://qlik.corp.com', **kw):
    return QlikServerClient(url, **kw)


# ─────────────────────────────────────────────────────────────
#  Xrfkey (QSEoW CSRF token)
# ─────────────────────────────────────────────────────────────

class TestXrfkey:
    def test_xrfkey_is_16_chars(self):
        c = _client()
        assert len(c._xrfkey) == 16
        assert c._xrfkey.isalnum()

    def test_qrs_path_gets_xrfkey(self):
        c = _client()  # QSEoW (no api key)
        path, headers = c._apply_qrs_xrfkey('/qrs/about', c._build_headers())
        assert f'xrfkey={c._xrfkey}' in path
        assert headers['X-Qlik-Xrfkey'] == c._xrfkey

    def test_qrs_path_with_existing_query(self):
        c = _client()
        path, _ = c._apply_qrs_xrfkey('/qrs/app/full?filter=x', c._build_headers())
        assert '?filter=x&xrfkey=' in path

    def test_cloud_path_no_xrfkey(self):
        c = _client('https://tenant.qlikcloud.com', api_key='k')
        path, headers = c._apply_qrs_xrfkey('/api/v1/apps', c._build_headers())
        assert 'xrfkey' not in path
        assert 'X-Qlik-Xrfkey' not in headers


# ─────────────────────────────────────────────────────────────
#  Certificate field checks
# ─────────────────────────────────────────────────────────────

class TestCertChecks:
    def _collect(self, cert, host='qlik.corp.com'):
        checks = []
        QlikServerClient._append_cert_checks(
            cert, host, lambda n, s, m: checks.append((n, s, m))
        )
        return {n: (s, m) for n, s, m in checks}

    def _cert(self, days_until_expiry, sans=('qlik.corp.com',)):
        not_after = time.strftime(
            '%b %d %H:%M:%S %Y GMT',
            time.gmtime(time.time() + days_until_expiry * 86400),
        )
        return {
            'subject': ((('commonName', 'qlik.corp.com'),),),
            'issuer': ((('organizationName', 'Corp Root CA'),),),
            'notAfter': not_after,
            'subjectAltName': tuple(('DNS', s) for s in sans),
        }

    def test_subject_and_issuer(self):
        res = self._collect(self._cert(365))
        assert res['cert_subject'][0] == 'pass'
        assert 'qlik.corp.com' in res['cert_subject'][1]
        assert 'Corp Root CA' in res['cert_subject'][1]

    def test_valid_expiry(self):
        res = self._collect(self._cert(200))
        assert res['cert_expiry'][0] == 'pass'

    def test_expiring_soon_warns(self):
        res = self._collect(self._cert(10))
        assert res['cert_expiry'][0] == 'warn'

    def test_expired_fails(self):
        res = self._collect(self._cert(-5))
        assert res['cert_expiry'][0] == 'fail'
        assert 'EXPIRED' in res['cert_expiry'][1]

    def test_hostname_covered(self):
        res = self._collect(self._cert(100, sans=('qlik.corp.com',)))
        assert res['cert_hostname'][0] == 'pass'

    def test_wildcard_san_covers_host(self):
        res = self._collect(self._cert(100, sans=('*.corp.com',)))
        assert res['cert_hostname'][0] == 'pass'

    def test_hostname_not_covered_warns(self):
        res = self._collect(self._cert(100, sans=('other.example.com',)))
        assert res['cert_hostname'][0] == 'warn'
        assert 'does not cover' in res['cert_hostname'][1]


# ─────────────────────────────────────────────────────────────
#  Scheme + client-certificate file validation (early, no network)
# ─────────────────────────────────────────────────────────────

class TestConnectionEarlyChecks:
    def test_invalid_scheme_fails_fast(self):
        c = _client('ftp://not-a-web-server')
        result = c.test_connection()
        assert result['ok'] is False
        names = {ch['name']: ch['status'] for ch in result['checks']}
        assert names['url'] == 'fail'
        # Must not have attempted TCP/TLS after the scheme failure.
        assert 'tcp' not in names

    def test_http_scheme_warns(self):
        # Use an unroutable host so the TCP probe fails fast after the warn.
        c = _client('http://127.0.0.1:9', timeout=1)
        result = c.test_connection()
        names = {ch['name']: ch['status'] for ch in result['checks']}
        assert names['url'] == 'warn'

    def test_missing_client_cert_file_fails(self):
        c = _client(cert_path='C:/nonexistent/client.pem',
                    key_path='C:/nonexistent/client.key', timeout=1)
        result = c.test_connection()
        names = {ch['name']: ch['status'] for ch in result['checks']}
        assert names['client_cert'] == 'fail'

    def test_cert_without_key_fails(self, tmp_path):
        cert = tmp_path / 'client.pem'
        cert.write_text('dummy', encoding='utf-8')
        c = _client(cert_path=str(cert), timeout=1)
        result = c.test_connection()
        names = {ch['name']: ch['status'] for ch in result['checks']}
        assert names['client_cert'] == 'fail'
        msg = next(ch['message'] for ch in result['checks'] if ch['name'] == 'client_cert')
        assert 'private key' in msg


# ─────────────────────────────────────────────────────────────
#  Result envelope
# ─────────────────────────────────────────────────────────────

class TestResultEnvelope:
    def test_envelope_keys(self):
        c = _client('ftp://x')
        result = c.test_connection()
        assert set(result) >= {'ok', 'server', 'platform', 'auth_method', 'checks'}

    def test_auth_method_detection(self):
        assert _client('https://t.qlikcloud.com', api_key='k').test_connection()['auth_method'] == 'api_key'
        assert _client('https://x', jwt_token='j').test_connection()['auth_method'] == 'jwt'
