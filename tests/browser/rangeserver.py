"""Static file server with HTTP Range support (video seeking requires it)."""
import http.server, os, re
from pathlib import Path


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_head(self):
        rng = self.headers.get("Range")
        if not rng:
            return super().send_head()
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return super().send_head()
        m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
        if not m:
            return super().send_head()
        size = os.path.getsize(path)
        start = int(m.group(1)) if m.group(1) else 0
        end = int(m.group(2)) if m.group(2) else size - 1
        end = min(end, size - 1)
        if start > end:
            self.send_error(416)
            return None
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self._limit = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        # A media element abandons ranges it no longer needs, so a closed connection
        # mid-write is normal here rather than an error worth surfacing.
        try:
            limit = getattr(self, "_limit", None)
            if limit is None:
                return super().copyfile(source, outputfile)
            remaining = limit
            while remaining > 0:
                chunk = source.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                outputfile.write(chunk)
                remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def end_headers(self):
        if not getattr(self, "_sent_accept_ranges", False):
            self.send_header("Accept-Ranges", "bytes")
            self._sent_accept_ranges = True
        super().end_headers()
