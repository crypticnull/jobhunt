// The job hunt as one window on his desktop.
//
// A browser tab was the wrong container for this. It is not a page he visits,
// it is the thing he works in, and a tab gets buried, duplicated and closed by
// accident. So: one window, one taskbar icon, and a single instance lock, which
// means launching it twice focuses the window that is already open instead of
// starting a second copy fighting the first one for the same port.
//
// Two views in that window. The search is the console, served by python off his
// own store. The site is the Astro dev server, so the design sandbox is in here
// too rather than being a second thing to remember to start. The site is heavy
// and he will not always want it, so it is started the first time he asks for
// it and not before.

const { app, BrowserWindow, shell, Menu } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const WIN = process.platform === "win32";
const CONSOLE_PORT = 4319;
const SITE_PORT = 4321;

let win = null;
let ready = null;
const kids = [];

// The scheduled tasks and run.cmd both read this file to decide which python
// owns the database. A third opinion here is how two pythons end up writing
// the same sqlite file with different sets of migrations applied.
function python() {
  const pin = path.join(ROOT, "data", "local", "python.txt");
  try {
    const named = fs.readFileSync(pin, "utf8").trim();
    if (named) return named;
  } catch {}
  return WIN ? "python" : "python3";
}

// npm on Windows is npm.cmd, and node refuses to spawn a .cmd without a shell,
// so that one gets cmd.exe in the middle. python does not, and must not: a
// shell in the middle is a process that gets killed while the thing it started
// carries on holding the store.
function start(name, cmd, args, cwd, { shell = false } = {}) {
  const child = spawn(cmd, args, {
    cwd,
    shell,
    windowsHide: true,
    // On unix this makes the child a process group leader so the whole tree can
    // be signalled at once. On Windows the tree is taskkill's job instead.
    detached: !WIN,
  });
  child.on("error", (e) => console.error(`${name} did not start: ${e.message}`));
  // Its output is the only place a stack trace can surface once the window
  // owns the screen, so it goes to the terminal rather than nowhere.
  child.stdout?.on("data", (b) => process.stdout.write(`[${name}] ${b}`));
  child.stderr?.on("data", (b) => process.stderr.write(`[${name}] ${b}`));
  kids.push(child);
  return child;
}

// Killing the child is not killing what the child started. Through cmd.exe on
// Windows, child.kill() ends the shell and leaves python holding the database,
// which is the exact thing nobody notices until the four in the morning poll
// fails. taskkill /T takes the tree; on unix the negative pid takes the group.
function stop(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  try {
    if (WIN) {
      spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], { windowsHide: true });
    } else {
      process.kill(-child.pid, "SIGTERM");
    }
  } catch {
    try { child.kill(); } catch {}
  }
}

function up(port) {
  return new Promise((resolve) => {
    const req = http.get({ host: "127.0.0.1", port, path: "/", timeout: 700 }, (res) => {
      res.resume();
      resolve(true);
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

// A server that is still binding is not a failure, it is a server that is still
// binding. Loading the view before it answers is how you get a blank window and
// no way to tell whether anything is wrong.
async function waitFor(port, seconds = 40) {
  const deadline = Date.now() + seconds * 1000;
  while (Date.now() < deadline) {
    if (await up(port)) return true;
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
}

async function startConsole() {
  // Already listening means he started it from the command line. Attaching to
  // it beats starting a second one and losing to EADDRINUSE.
  if (await up(CONSOLE_PORT)) return true;
  start("console", python(), ["-m", "scraper", "console", "--no-open", "--port", String(CONSOLE_PORT)], ROOT);
  return waitFor(CONSOLE_PORT);
}

async function startSite() {
  if (await up(SITE_PORT)) return true;
  const site = path.join(ROOT, "site");
  if (!fs.existsSync(path.join(site, "node_modules"))) {
    start("site install", WIN ? "npm.cmd" : "npm", ["install"], site, { shell: WIN });
    // npm install then astro dev, so the first ever click on Site works rather
    // than failing with a missing binary he then has to go and fix by hand.
    await new Promise((r) => kids[kids.length - 1].on("exit", r));
  }
  start("site", WIN ? "npm.cmd" : "npm", ["run", "dev"], site, { shell: WIN });
  return waitFor(SITE_PORT, 90);
}

function createWindow() {
  win = new BrowserWindow({
    width: 1500,
    height: 1000,
    minWidth: 900,
    backgroundColor: "#0f1113",
    title: "Job Hunt",
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, "preload.js"),
    },
  });
  win.loadFile(path.join(__dirname, "shell.html"));
  win.once("ready-to-show", () => win.show());
  // A posting's own link belongs in his browser. Opening it in here would turn
  // the app into the browser he asked to stop using.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  win.on("closed", () => { win = null; });
}

function menu() {
  // The default menu is a browser's menu. This one has the four things that
  // are true of this app and nothing that implies a tab.
  const template = [
    {
      label: "Job Hunt",
      submenu: [
        { label: "Search", accelerator: "CmdOrCtrl+1", click: () => win?.webContents.send("go", "search") },
        { label: "Site", accelerator: "CmdOrCtrl+2", click: () => win?.webContents.send("go", "site") },
        { type: "separator" },
        { label: "Reload the view", accelerator: "CmdOrCtrl+R", click: () => win?.webContents.send("go", "reload") },
        { role: "toggleDevTools" },
        { type: "separator" },
        { role: "quit" },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// Launching it again focuses the window that is open. This is the whole answer
// to ending up with six of them.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });

  app.whenReady().then(() => {
    menu();
    // Started once and remembered as a promise. The renderer asks for it rather
    // than being told, because a message sent before the window has run its
    // script is a message nobody receives, and a reload loses one that landed:
    // both left the window saying "starting the console" over a console that
    // had been serving for a minute.
    ready = startConsole();
    createWindow();
  });

  app.on("window-all-closed", () => app.quit());

  // Nothing this app started outlives it. A python server left holding the
  // store is the kind of thing that is only noticed at four in the morning.
  // Closing the window is the end of it. Nothing this app started keeps
  // running, so there is never a process to go and find later.
  const reap = () => { for (const c of kids) stop(c); kids.length = 0; };
  app.on("before-quit", reap);
  app.on("will-quit", reap);
  process.on("exit", reap);
}

const { ipcMain } = require("electron");

// Both views are asked for, never announced, so a reload rebuilds the window
// from what is actually running rather than from a message that already went.
ipcMain.handle("console-state", async () => ((await ready) ? "ready" : "failed"));
ipcMain.handle("start-site", async () => ((await startSite()) ? "ready" : "failed"));
ipcMain.handle("site-up", () => up(SITE_PORT));
