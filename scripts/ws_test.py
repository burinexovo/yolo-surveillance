# ws_test.py
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()

html = """
<!doctype html>
<html>
  <body>
    <h1>WS 測試</h1>
    <pre id="log"></pre>
    <script>
      const logEl = document.getElementById("log");
      function log(msg) {
        console.log(msg);
        logEl.textContent += msg + "\\n";
      }

      const ws = new WebSocket("ws://localhost:8000/ws");
      log("connecting...");

      ws.onopen = () => {
        log("ws open, send hello");
        ws.send("hello from browser");
      };

      ws.onmessage = (ev) => {
        log("message from server: " + ev.data);
      };

      ws.onerror = (ev) => {
        log("ws error: " + ev.type);
      };

      ws.onclose = () => {
        log("ws closed");
      };
    </script>
  </body>
</html>
"""


@app.get("/")
async def index():
    return HTMLResponse(html)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    print("⚡ client trying connect")
    await ws.accept()
    print("✅ ws accepted")
    await ws.send_text("hello from server")
    try:
        while True:
            text = await ws.receive_text()
            print("📩 recv:", text)
            await ws.send_text("echo: " + text)
    except Exception as e:
        print("❌ ws error/close:", e)
