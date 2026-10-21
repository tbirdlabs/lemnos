// Runs the USB page (Salient.html) without a browser: its script, with stand-ins for the page and for Web Serial,
// talking to a desktop copy of the board software (tools/page_bridge.py: the real host and console hub) over a pipe.
// Connects, then checks the HELLO answer, the lights, keys and the on-screen pad, the game and brightness (and that
// they're remembered through a restart), the console, restarting without saved settings, and disconnecting.
//   Node:     node tools/test_page.js
//   VS Code:  set ELECTRON_RUN_AS_NODE=1 && "%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe" tools\test_page.js
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { spawn } = require("child_process");

const HERE = __dirname;
const html = fs.readFileSync(path.join(HERE, "..", "Salient.html"), "utf8");
const script = html.slice(html.lastIndexOf("<script>") + 8, html.lastIndexOf("</script>"));
const FAILS = [];
function check(name, ok, detail) {
  if (!ok) { FAILS.push(name); console.log("FAIL", name, detail === undefined ? "" : detail); }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(what, ms) {
  const end = Date.now() + (ms || 15000);
  while (Date.now() < end) { if (what()) return true; await sleep(25); }
  return false;
}

// ---- a page: elements made on first use
class El {
  constructor(tag, id) {
    this.tag = tag; this.id = id || ""; this.children = []; this.listeners = {}; this.dataset = {}; this.style = {};
    this.textContent = ""; this.innerHTML = ""; this.value = ""; this.disabled = false; this.checked = true;
    this.open = false; this.className = ""; this.scrollTop = 0; this.scrollHeight = 0; this.clientHeight = 0;
    this.clientWidth = 600;
    const set = new Set();
    this.classList = {
      add: (c) => set.add(c), remove: (c) => set.delete(c), contains: (c) => set.has(c),
      toggle: (c, on) => { if (on === undefined ? !set.has(c) : on) set.add(c); else set.delete(c); },
    };
    this.width = 0; this.height = 0;
  }
  get textContent() { return this._text; }
  set textContent(v) { this._text = v; this.children = []; }      // as in a browser: the children go too
  append(...k) { this.children.push(...k); }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  fire(t, e) { for (const f of this.listeners[t] || []) f(Object.assign({ preventDefault() { }, stopPropagation() { } }, e)); }
  querySelector() { return new El("div"); }
  setPointerCapture() { }
  focus() { document.activeElement = this; }
  blur() { document.activeElement = document.body; }
  getContext() { return ctx; }
}
const ctx = new Proxy({}, { get: (t, k) => (k in t ? t[k] : () => ({ addColorStop() { } })), set: (t, k, v) => { t[k] = v; return true; } });
const els = {};
const docListeners = {};
const pad = ["up", "left", "pick", "right", "down", "move_back", "move", "back"].map((a) => {
  const b = new El("button"); b.dataset.a = a; return b;
});
const document = {
  body: new El("body"),
  getElementById: (id) => els[id] || (els[id] = new El("div", id)),
  createElement: (t) => new El(t),
  querySelectorAll: () => pad,
  addEventListener: (t, f) => { (docListeners[t] = docListeners[t] || []).push(f); },
};
document.activeElement = document.body;
const els_view = document.getElementById("view");
els_view.clientHeight = 600;
function key(k, extra) {
  for (const f of docListeners.keydown || []) f(Object.assign({ key: k, repeat: false, shiftKey: false, preventDefault() { } }, extra));
}

// ---- Web Serial, with the bridge on the other end
let bridge = null;
const written = [];
class Port {
  constructor() { this.queue = []; this.waiting = null; this.closed = false; }
  getInfo() { return { usbVendorId: 0x239A, usbProductId: 0x8122 }; }
  async open() {
    bridge = spawn("py", ["-3", path.join(HERE, "page_bridge.py")], { stdio: ["pipe", "pipe", "inherit"] });
    bridge.stdout.on("data", (d) => this.push(new Uint8Array(d)));
    this.readable = { getReader: () => ({
      read: () => this.queue.length ? Promise.resolve({ value: this.queue.shift(), done: false })
        : this.closed ? Promise.resolve({ done: true }) : new Promise((r) => { this.waiting = r; }),
      releaseLock() { }, cancel: async () => { this.end(); },
    }) };
    this.writable = { getWriter: () => ({
      write: async (bytes) => { const s = Buffer.from(bytes).toString("latin1"); written.push(s); if (bridge) bridge.stdin.write(Buffer.from(bytes)); },
      releaseLock() { },
    }) };
  }
  push(v) { if (this.waiting) { const w = this.waiting; this.waiting = null; w({ value: v, done: false }); } else this.queue.push(v); }
  end() { this.closed = true; if (this.waiting) { const w = this.waiting; this.waiting = null; w({ done: true }); } }
  async setSignals() { }
  async close() { this.end(); this.readable = null; if (bridge) { bridge.stdin.end(); bridge = null; } }
}
const port = new Port();
const serial = { getPorts: async () => [], requestPort: async () => port, addEventListener() { } };

Object.assign(globalThis, {
  document, window: { devicePixelRatio: 1, addEventListener() { } },
  requestAnimationFrame: (f) => setTimeout(f, 0), ResizeObserver: class { observe() { } }, confirm: () => true,
});
Object.defineProperty(globalThis, "navigator", { value: { serial }, configurable: true });   // Node 21+ has its own
const t = vm.runInThisContext(script + "\n;({ link, board, view, form });", { filename: "Salient.html" });
const $ = (id) => document.getElementById(id);
const sent = () => written.join("");

(async () => {
  try {
    await $("connect").onclick();
    check("connects and the board answers", await until(() => t.link.ready), $("cstatus").textContent);
    check("status", $("cstatus").textContent === "Connected", $("cstatus").textContent);
    check("games listed", await until(() => t.board.games.includes("salient") && t.board.games.includes("paint"), 3000), t.board.games);
    check("board kind and LED count", t.board.kind === "large" && t.board.count === 171, t.board);
    check("running game", await until(() => t.board.game === t.board.deflt && t.board.game !== ""), t.board.game);
    check("game list filled", $("game").children.length === t.board.games.length && !$("game").disabled);
    check("asked for the lights", sent().includes("!WATCH on\n"));
    check("lights arrive", await until(() => t.view.frame && t.view.frame.length === 171 * 3), t.view.frame && t.view.frame.length);
    check("clock set from the computer", await until(() => /!TIME \d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\n/.test(sent()), 3000));

    key("ArrowUp");
    key("Enter");
    check("keys send presses", sent().includes("!IN p1 up\n!IN p1 pick\n"));
    key("3");
    key(" ", { shiftKey: true });
    check("player 3, move back", sent().includes("!IN p3 move_back\n"));
    pad[2].fire("pointerdown", { pointerId: 1 });
    pad[2].fire("pointerup", {});
    check("the pad's Pick", sent().endsWith("!IN p3 pick\n"));
    check("players listed", await until(() => $("players").children.length === 2), $("players").children.length);

    // the setup form (Salient's options): Invasion with player 1 against the computer, then a refusal, then New game
    check("form: Salient's fields", await until(() => t.form.fields.some((f) => f.key === "red" &&
          f.choices.some((c) => c[0] === "usb-p1"))), t.form.fields.map((f) => f.key));
    check("form: drawn, Rush fields hidden", $("fields").children.some((e) => e.textContent === "Red, the invader") &&
          !$("fields").children.some((e) => e.textContent === "Players"));
    Object.assign(t.form.picked, { mode: "invasion", red: "usb-p1", blue: "computer", red_seat: "2" });
    $("start").onclick();
    check("form: Start", await until(() => $("setupmsg").textContent === "Started."), $("setupmsg").textContent);
    check("form: sent what's shown", /!START \{"mode":"invasion","red":"usb-p1","blue":"computer","red_seat":"2","level":"7"\}\n/.test(sent()),
          sent().split("\n").filter((l) => l.startsWith("!START")));
    t.form.picked.blue = "usb-p1";
    $("start").onclick();
    check("form: the board's refusal shown", await until(() => $("setupmsg").textContent === "One controller can't play both sides."),
          $("setupmsg").textContent);
    t.form.picked.mode = "rush";
    t.form.touched.add("mode");
    $("newgame").onclick();
    check("form: New game", await until(() => $("setupmsg").textContent === "Started." && sent().includes("!NEWGAME\n")));
    check("form: picks kept when the form comes again", t.form.picked.mode === "rush");

    $("game").value = "paint";
    $("game").onchange({ target: $("game") });
    check("game switched", await until(() => t.board.game === "paint"), t.board.game);
    check("form: paint has none", await until(() => t.form.fields.length === 0 && $("start").classList.contains("hidden") &&
          $("newgame").textContent === "New game"));
    $("bright").value = "4";
    $("bright").onchange({ target: $("bright") });
    check("brightness set", await until(() => t.board.brightness === "4"), t.board.brightness);
    check("brightness shown", $("bval").textContent === "4 of 10 (6.3%)", $("bval").textContent);

    $("cmd").value = "radio";
    $("send").onclick();
    check("console command answered", await until(() => /\nradio\n(Radio: |No command "radio")/.test($("log").textContent)),
          $("log").textContent.slice(-300));

    $("restart").onclick();
    check("restart: goes away", await until(() => !t.link.ready, 3000));
    check("restart: comes back", await until(() => t.link.ready), $("cstatus").textContent);
    check("restart: no 'stopped' on the way", $("stopped").classList.contains("hidden"));
    check("restart: the saved game and brightness", await until(() => t.board.game === "paint" && t.board.brightness === "4"), [t.board.game, t.board.brightness]);

    // a crash: the program stops by itself; the page says so, and restarting without saved settings recovers
    bridge.stdin.write("\x03");
    check("stopped: noticed", await until(() => t.link.state === "stopped", 3000), t.link.state);
    check("stopped: shown", !$("stopped").classList.contains("hidden") && $("cstatus").textContent === "Program stopped");
    $("clean").onclick();
    check("clean: comes back", await until(() => t.link.ready), $("cstatus").textContent);
    check("clean: config.py's game and brightness", await until(() => t.board.game === t.board.deflt && t.board.brightness === "default"),
          [t.board.game, t.board.brightness]);
    check("clean: the stop on the way isn't shown", $("stopped").classList.contains("hidden"));

    await $("disconnect").onclick();
    check("disconnect: BYE", sent().includes("!BYE\n"));
    check("disconnect: status", $("cstatus").textContent === "Not connected" && !t.link.port);
  } catch (e) {
    FAILS.push("exception");
    console.log(e.stack);
  }
  if (bridge) bridge.kill();
  console.log(FAILS.length ? FAILS.length + " failed" : "all passed");
  process.exit(FAILS.length ? 1 : 0);
})();
