"""Shared Browser checks: public egress, pinned IP, .onion never DNS, no JS."""
import io
import os
import socket
import unittest
from unittest.mock import patch

from asterion_remote import shared_browser as browser


def dns(host,port,**kwargs):
    return [(socket.AF_INET,socket.SOCK_STREAM,6,"",("93.184.216.34",port))]


class FakeSocket:
    def __init__(self,reply:bytes):
        self.reply=reply
        self.sent=b""
        self.closed=False
    def sendall(self,data):self.sent+=data
    def makefile(self,mode,buffering=None):return io.BytesIO(self.reply)
    def settimeout(self,value):pass
    def close(self):self.closed=True


def answer(content:bytes=b"<title>A real test</title><p>Hello owner</p>",
           status=b"200 OK",headers:bytes=b"Content-Type: text/html"):
    return b"HTTP/1.1 "+status+b"\r\n"+headers+b"\r\nContent-Length: "+str(
        len(content)).encode()+b"\r\nConnection: close\r\n\r\n"+content


class BrowserTests(unittest.TestCase):
    def test_pinned_public_ipv4_fetch_and_no_javascript_execution(self):
        sock=FakeSocket(answer(b'<title>Sample</title><script>steal()</script>'
                               b'<a href="/docs">Guidance</a><p>Answer.</p>'))
        dialed=[]
        def dial(ip,port,timeout):
            dialed.append((ip,port))
            return sock
        out=browser.fetch("http://example.com/path",resolver=dns,dialer=dial)
        self.assertTrue(out["ok"])
        self.assertEqual(dialed,[("93.184.216.34",80)])
        self.assertEqual(out["title"],"Sample")
        self.assertIn("Answer.",out["text"])
        self.assertNotIn("steal()",out["text"])
        self.assertIn("http://example.com/docs",out["links"])
        self.assertFalse(out["page_js_executed"])
        self.assertTrue(sock.closed)
        self.assertIn(b"GET /path HTTP/1.1",sock.sent)

    def test_private_dns_response_blocks_network_connection(self):
        for ip in ["127.0.0.1","192.168.1.3","10.0.0.3","169.254.169.254",
                   "100.64.1.1","::1","fd00::1"]:
            with self.subTest(ip=ip):
                def private(*args,**kw):
                    return [(socket.AF_INET,socket.SOCK_STREAM,6,"",(ip,80))]
                touched=[]
                with self.assertRaises(PermissionError):
                    browser.fetch("http://example.com/",resolver=private,
                                  dialer=lambda *args:touched.append(args))
                self.assertEqual(touched,[])

    def test_mixed_public_private_dns_fails_closed(self):
        def mixed(host,port,**kwargs):
            return [(socket.AF_INET,socket.SOCK_STREAM,6,"",
                     ("93.184.216.34",port)),
                    (socket.AF_INET,socket.SOCK_STREAM,6,"",
                     ("10.0.0.1",port))]
        with self.assertRaises(PermissionError):
            browser.fetch("http://example.com",resolver=mixed)

    def test_disallowed_url_forms_and_private_networks(self):
        for url in ["file:///etc/passwd","http://localhost",
                    "http://127.0.0.1","http://10.0.0.2",
                    "http://example.com:8080/","http://user:password@example.com",
                    "http://example.com/path#fragment",
                    "http://host.local/resource","http://example.com\\@private",
                    "javascript:alert(1)"]:
            with self.subTest(url=url):
                with self.assertRaises((ValueError,PermissionError)):
                    browser.fetch(url,resolver=dns,dialer=lambda *args:None)

    def test_redirect_to_private_address_never_dials_private_host(self):
        redirect=answer(b"",status=b"302 Found",
                        headers=b"Location: http://192.168.1.1/admin")
        sock=FakeSocket(redirect)
        with self.assertRaises(PermissionError):
            browser.fetch("http://example.com",resolver=dns,
                          dialer=lambda *args:sock)
        self.assertTrue(sock.closed)

    def test_html_body_cap_enforced(self):
        response=answer(b"A"*(browser._MAX_BODY+1),
                        headers=b"Content-Type: text/plain")
        with self.assertRaises(ValueError):
            browser.fetch("http://example.com",resolver=dns,
                          dialer=lambda *args:FakeSocket(response))

    def test_onion_requires_explicit_tor_and_no_system_dns(self):
        onion="a"*56+".onion"
        with patch.dict(os.environ,{"ASTERION_TOR_ENABLED":"0"}):
            with self.assertRaises(RuntimeError):
                browser.fetch("http://"+onion,tor=True)
        requested=[]
        def no_dns(*args,**kw):
            raise AssertionError("never resolve onion with system DNS")
        fake=FakeSocket(answer(b"<title>Onion</title><p>Tor-only content</p>"))
        with patch.dict(os.environ,{"ASTERION_TOR_ENABLED":"1"}), patch.object(
                browser,"_socks5_onion",side_effect=lambda *args:
                requested.append(args) or fake),patch(
                "asterion_remote.shared_browser.socket.getaddrinfo",no_dns):
            result=browser.fetch("http://"+onion,tor=True)
        self.assertTrue(result["ok"])
        self.assertTrue(result["tor_mode"])
        self.assertEqual(len(requested),1)
        self.assertIn("Tor-only",result["text"])

    def test_onion_without_tor_mode_never_falls_back(self):
        with self.assertRaises(ValueError):
            browser.fetch("http://"+"a"*56+".onion",tor=False)

    def test_http_non200_returns_failure_not_complete_research(self):
        sock=FakeSocket(answer(b"blocked",status=b"403 Forbidden",
                               headers=b"Content-Type: text/plain"))
        out=browser.fetch("http://example.com",resolver=dns,
                          dialer=lambda *args:sock)
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"],403)
        self.assertFalse(out["verified_page_content"])

    def test_tor_proxy_cannot_point_to_foreign_or_remote_host(self):
        onion="b"*56+".onion"
        with patch.dict(os.environ,{"ASTERION_TOR_ENABLED":"1",
                                    "ASTERION_TOR_SOCKS_HOST":"192.168.1.2"}):
            with self.assertRaises(ValueError):
                browser.fetch("http://"+onion,tor=True)


if __name__=="__main__":
    unittest.main()
