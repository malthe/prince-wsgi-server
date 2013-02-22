import os
import sys
import atexit
import binascii
import cookielib
import webob
import hashlib
import logging
import shutil
import tarfile
import tempfile
import multiprocessing
import subprocess
import itertools

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s: %(asctime)s %(levelname)s -- %(message)s ---'
    )

log = logging.getLogger('prince.wsgi')


def processor(spool, event):
    while True:
        event.wait()
        event.clear()

        if not os.path.exists(spool):
            return

        for job in os.listdir(spool):
            filename = os.path.join(spool, job)
            name, ext = os.path.splitext(filename)

            if ext == ".tar":
                log.info("Running job: %s." % name)
                try:
                    tar = tarfile.TarFile.open(filename, mode='r')
                except tarfile.ReadError:
                    log.warn("Read error while opening input: %s." % filename)
                else:
                    temp_dir = tempfile.mkdtemp()
                    tar.extractall(temp_dir)
                    tar.close()
                    log.info("%d files extracted." % len(os.listdir(temp_dir)))

                    output_filename = os.readlink(name + ".pdf")
                    input_filename = os.path.join(temp_dir, "index.html")

                    stylesheets = tuple(
                        itertools.chain(*(
                            ("-s", os.path.join(temp_dir, filename))
                            for filename in os.listdir(temp_dir)
                            if filename.endswith('.css')
                            ))
                        )

                    if not os.path.exists(input_filename):
                        log.warn("Index document does not exist.")
                    else:
                        cookies_path = os.path.join(temp_dir, 'cookiejar')
                        cookiejar = cookielib.MozillaCookieJar(cookies_path)

                        try:
                            import crawler
                        except ImportError:
                            pass
                        else:
                            crawler.load_iframe_content(
                                input_filename, cookiejar, 5000
                                )

                        cookiejar.save()

                        job = (
                            '/usr/bin/env',
                            'prince',
                            '--verbose',
                            '--disallow-modify',
                            '--input=html',
                            # '--no-network',
                            input_filename,
                            '-o',
                            output_filename,
                            '--cookiejar',
                            cookies_path,
                            ) + stylesheets

                        try:
                            subprocess.call(job)
                        except KeyboardInterrupt:
                            return
                        finally:
                            log.info("Process ended; cleanup: %s." % temp_dir)
                            shutil.rmtree(temp_dir)

                try:
                    os.unlink(name + ".tar")
                    os.unlink(name + ".pdf")
                except:
                    log.warn("Unable to clean up after job: %s." % name)

        sys.stderr.flush()

tempdir = None
event = None
process = None

def start_process():
    process = multiprocessing.Process(target=processor, args=(tempdir, event))
    process.daemon = False
    process.start()
    return process

def init():
    global tempdir
    global event
    global process

    tempdir = tempfile.mkdtemp()
    event = multiprocessing.Event()
    process = start_process()

    @atexit.register
    def on_quit():
        shutil.rmtree(tempdir)
        event.set()

try:
    import uwsgi
except ImportError:
    pass
else:
    init()


def application(environ, start_response):
    global process
    output_directory = environ.get(
        'PDF_OUTPUT_DIRECTORY', os.environ.get('PDF_OUTPUT_DIRECTORY'))
    if output_directory is None:
        raise ValueError("Missing environment setting ``PDF_OUTPUT_DIRECTORY.")

    pdf_base_url = environ.get('PDF_BASE_URL', os.environ.get('PDF_BASE_URL'))

    if pdf_base_url is None:
        log.warn("No PDF base url set --- using \"file://\" prefix.")
        pdf_base_url = "file://" + tempdir

    if environ.get('REQUEST_METHOD', 'GET') == 'GET':
        response = webob.Response(
            status='405',
            content_type='text/plain',
            body="This service only accepts POST requests."
            )
    else:
        fileobj = environ['wsgi.input']

        # write entire input to disk (read into memory)
        length = int(
            environ.get('HTTP_CONTENT_LENGTH',
                        environ['CONTENT_LENGTH']) or -1
            )

        contents = fileobj.read(length)
        if environ.get('HTTP_CONTENT_TRANSFER_ENCODING') == 'base64':
            contents = binascii.a2b_base64(contents)

        # compute digest
        digest = hashlib.sha1(contents).hexdigest()

        # document output name
        filename = "%s.pdf" % digest
        output_filename = os.path.join(output_directory, filename)
        spool = os.path.join(tempdir, digest)

        # write tar to temporary file
        f = open(spool + ".tar", "w")
        f.write(contents)
        f.flush()
        f.close()

        try:
            # create symlink to (non-existing) target location
            os.symlink(output_filename, spool + ".pdf")
        except OSError:
            # job probably already
            pass
        else:
            if not process.is_alive():
                process = start_process()

            # set process event
            event.set()

        response = webob.Response(
            status='200',
            content_type='text/plain',
            body="%s/%s" % (pdf_base_url, filename),
            )

    sys.stderr.flush()

    for item in response(environ, start_response):
        yield item


def make_app(config):
    init()
    return application
