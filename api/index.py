from http.server import BaseHTTPRequestHandler
import json

# Telemetry (region, latency_ms, uptime_pct), embedded so the function has no file/dependency issues
DATA = [["apac", 151.96, 99.29], ["apac", 117.64, 99.427], ["apac", 120.03, 97.76], ["apac", 164.51, 97.835], ["apac", 168.77, 98.064], ["apac", 167.43, 98.909], ["apac", 197.81, 99.208], ["apac", 219.57, 98.301], ["apac", 185.92, 97.651], ["apac", 145.37, 98.361], ["apac", 230.58, 97.97], ["apac", 157.83, 97.802], ["emea", 120.3, 98.602], ["emea", 178.85, 99.207], ["emea", 214.88, 99.011], ["emea", 126.69, 97.33], ["emea", 104.39, 97.598], ["emea", 201.2, 98.645], ["emea", 193.52, 97.25], ["emea", 209.36, 99.146], ["emea", 131.92, 97.699], ["emea", 182.72, 97.72], ["emea", 209.21, 99.201], ["emea", 161.87, 97.58], ["amer", 181.09, 97.989], ["amer", 120.7, 99.185], ["amer", 130.75, 97.53], ["amer", 138.38, 99.122], ["amer", 189.79, 97.978], ["amer", 184.67, 97.526], ["amer", 141.71, 98.972], ["amer", 192.77, 99.492], ["amer", 140.32, 98.055], ["amer", 175.73, 97.258], ["amer", 158.06, 99.165], ["amer", 169.16, 97.356]]

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS, HEAD",
    "Access-Control-Allow-Headers": "*",
}


def percentile(values, p):
    """Linear-interpolation percentile (same as numpy.percentile default)."""
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def metrics(regions, threshold):
    out = {}
    for r in regions:
        rows = [(lat, up) for (reg, lat, up) in DATA if reg == r]
        if not rows:
            out[r] = {"avg_latency": None, "p95_latency": None,
                      "avg_uptime": None, "breaches": 0}
            continue
        lats = [x[0] for x in rows]
        ups = [x[1] for x in rows]
        out[r] = {
            "avg_latency": round(sum(lats) / len(lats), 4),
            "p95_latency": round(percentile(lats, 95), 4),
            "avg_uptime": round(sum(ups) / len(ups), 4),
            "breaches": sum(1 for v in lats if v > threshold),
        }
    return out


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for k, v in CORS.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        # Preflight: headers only, empty body
        self.send_response(200)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self):
        self.send_response(200)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            regions = body["regions"]
            threshold = float(body["threshold_ms"])
            if not isinstance(regions, list):
                raise ValueError("regions must be a list")
        except Exception as e:
            return self._send(400, {"error": "Send JSON like "
                                    '{"regions": ["emea"], "threshold_ms": 180}: ' + str(e)})
        m = metrics(regions, threshold)
        # Per-region results at the top level, and also under "regions"
        self._send(200, {**m, "regions": m})

    def do_GET(self):
        self._send(405, {"error": "Use POST with JSON {regions: [...], threshold_ms: n}"})
