import os
import time
import logging
import Cookie
import cookielib
import urlparse
import datetime

try:
    import gtk
    import gobject
    import webkit
    import lxml.html
except ImportError, exc:
    logging.warn(exc)
    logging.info(
        "Modules `gtk`, `gobject`, `webkit` and `lxml` "
        "required for script-enabled HTML processing."
        )
    raise


gtk.gdk.threads_init()
log = logging.getLogger('prince.crawler')
encodings = 'windows-1251', 'windows-1252'


class WebView(webkit.WebView):
    def read_variable(self, expression):
        self.execute_script(
            'oldtitle=document.title;'
            'document.title=%s;' % expression
            )

        try:
            return self.get_main_frame().get_title()
        finally:
            self.execute_script('document.title=oldtitle;')

    def get_cookies(self):
        return self.read_variable("document.cookie")

    def get_html(self):
        html = self.read_variable("document.documentElement.innerHTML")
        if not html:
            return ""

        for encoding in encodings:
            header = 'charset=%s' % encoding
            if header in html:
                html = html.replace(header, 'charset=utf-8')
                break

        parser = lxml.html.HTMLParser()
        tree = lxml.etree.fromstring(html, parser)

        head = tree.find('head')
        if head is not None:
            base = tree.find('head/base')
            if base is None:
                base = lxml.html.Element("base")
                head.insert(0, base)

            uri = self.get_main_frame().get_uri()
            if uri is None:
                return html

            base.attrib['href'] = os.path.dirname(uri)

        return lxml.html.tostring(tree, encoding="utf-8")


class Crawler(gtk.Window):
    def __init__(self, url, file, cookiejar, timeout=None):
        gtk.Window.__init__(self)

        self._url = url
        self._file = file
        self._cookiejar = cookiejar
        self._timeout = timeout

        with gtk.gdk.lock:
            self._crawl()

    def _crawl(self):
        view = WebView()
        view.open(self._url)
        if self._timeout:
            gobject.timeout_add(self._timeout, self._save_and_quit, view)
        else:
            view.connect('load-finished', self._finished_loading)
        self.add(view)
        gtk.main()

    def _finished_loading(self, view, frame):
        gobject.idle_add(self._save_and_quit, view)

    def _save_and_quit(self, view):
        body = view.get_html()
        header = view.get_cookies()

        cookie = Cookie.SimpleCookie()
        cookie.load(header)

        uri = view.get_main_frame().get_uri()
        domain = urlparse.urlparse(uri).hostname

        future = datetime.datetime.now() + datetime.timedelta(days=1)
        expires = str(int(time.mktime(future.timetuple())))

        for morsel in cookie.values():
            self._cookiejar.set_cookie(cookielib.Cookie(
                1,             # Version
                morsel.key,    # Name
                morsel.value,  # Value
                None,          # Port
                False,         # Port specified
                domain,        # Domain
                True,          # Domain specified
                True,          # Domain initial dot
                "/",           # Path
                False,         # Path specified
                "",            # Secure
                expires,       # Expires
                False,         # Discard
                None,          # Comment
                None,          # Comment url,
                None,          # Rest
                ))

        try:
            with open(self._file, 'w') as f:
                html = "<html>\n%s\n</html>" % body
                f.write(html)
        finally:
            gtk.main_quit()


def load_iframe_content(path, cookiejar, timeout=None):
    parser = lxml.html.HTMLParser()
    tree = lxml.etree.parse(path, parser)

    iframes = tree.findall('//iframe')

    for i, iframe in enumerate(iframes):
        dirname = os.path.dirname(path)
        filename = os.path.join(dirname, 'iframe_%d.html' % i)
        url = iframe.attrib['src']
        log.info("Crawling URL: %s." % url)
        Crawler(url, filename, cookiejar, timeout=timeout)
        iframe.attrib['src'] = 'file://%s' % filename
        log.info("Updating iframe with local source: %s." % filename)

    html = lxml.etree.tostring(tree)

    with open(path, 'wb') as f:
        f.write(html)
