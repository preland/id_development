// id language support for VS Code: linting by running idc.py and turning its
// `file:line: error|warning: message` output into diagnostics. (Syntax
// highlighting is declarative -- see syntaxes/id.tmLanguage.json.)

const vscode = require("vscode");
const cp = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");

let diagnostics;
const timers = new Map();   // document uri string -> debounce timer

function activate(context) {
  diagnostics = vscode.languages.createDiagnosticCollection("id");
  context.subscriptions.push(diagnostics);

  context.subscriptions.push(
    vscode.commands.registerCommand("id.lint", () => {
      const ed = vscode.window.activeTextEditor;
      if (ed && ed.document.languageId === "id") {
        lint(ed.document);
      }
    })
  );

  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument((doc) => maybeLint(doc, true))
  );
  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument((doc) => maybeLint(doc, true))
  );
  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument((e) => {
      if (cfg().get("lint.run") === "onType") {
        debounce(e.document);
      }
    })
  );
  context.subscriptions.push(
    vscode.workspace.onDidCloseTextDocument((doc) => {
      if (doc.languageId === "id") {
        diagnostics.delete(doc.uri);
      }
    })
  );

  // lint anything already open
  vscode.workspace.textDocuments.forEach((doc) => maybeLint(doc, true));
}

function cfg() {
  return vscode.workspace.getConfiguration("id");
}

function maybeLint(doc, immediate) {
  if (doc.languageId !== "id") return;
  if (cfg().get("lint.run") === "off") return;
  if (immediate) lint(doc);
  else debounce(doc);
}

function debounce(doc) {
  if (doc.languageId !== "id") return;
  if (cfg().get("lint.run") === "off") return;
  const key = doc.uri.toString();
  clearTimeout(timers.get(key));
  const ms = cfg().get("lint.debounce") || 400;
  timers.set(
    key,
    setTimeout(() => {
      timers.delete(key);
      lint(doc);
    }, ms)
  );
}

// Count a directory's entries the way idc does: .id files + non-hidden
// subdirectories (other files don't count).
function dirEntryCount(dir) {
  let n = 0;
  try {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      if (e.name.startsWith(".")) continue;
      if (e.isDirectory() || e.name.endsWith(".id")) n++;
    }
  } catch (e) {
    return 0;
  }
  return n;
}

function hasIdFiles(dir) {
  for (const f of idFilesIn(dir)) return true; // eslint-disable-line no-unused-vars
  return false;
}

function isBoundary(dir) {
  return (
    fs.existsSync(path.join(dir, "idc.py")) ||
    fs.existsSync(path.join(dir, ".git"))
  );
}

// Find the project root for a file. A project is a directory tree with at most
// 3 entries per directory, so its root's parent -- a mere container of several
// projects, or the repo itself -- will have >3 entries (or be the repo
// boundary). Walk up while the parent still looks like part of one project.
function findProjectRoot(filePath) {
  let dir = path.dirname(filePath);
  for (let i = 0; i < 64; i++) {
    const parent = path.dirname(dir);
    if (parent === dir) break;
    if (isBoundary(parent)) break;
    if (dirEntryCount(parent) > 3) break;
    if (!hasIdFiles(parent)) break;
    dir = parent;
  }
  return dir;
}

// Locate idc.py: the configured path, or the nearest one walking up from the
// edited file.
function findIdc(filePath) {
  const configured = (cfg().get("idcPath") || "").trim();
  if (configured) {
    return configured;
  }
  let dir = path.dirname(filePath);
  for (let i = 0; i < 64; i++) {
    const candidate = path.join(dir, "idc.py");
    if (fs.existsSync(candidate)) return candidate;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

function lint(doc) {
  const filePath = doc.uri.fsPath;
  const idc = findIdc(filePath);
  if (!idc) {
    return; // no idc.py found and none configured -- silently skip
  }
  const scope = cfg().get("lint.scope") || "directory";
  const target =
    scope === "file" ? filePath : findProjectRoot(filePath);
  const python = cfg().get("pythonPath") || "python3";
  const tmpC = path.join(
    os.tmpdir(),
    "idlint-" + process.pid + "-" + Date.now() + ".c"
  );

  const args = [idc, target, "--emit-c", tmpC];
  cp.execFile(
    python,
    args,
    { cwd: path.dirname(idc), timeout: 15000 },
    (err, stdout, stderr) => {
      try {
        fs.unlinkSync(tmpC);
      } catch (e) {
        /* ignore */
      }
      publish(parseDiagnostics(stderr || ""), target, scope);
    }
  );
}

// Parse `path:line: error|warning: message` lines into per-file diagnostics.
function parseDiagnostics(text) {
  const re = /^(.*?):(\d+):\s*(error|warning):\s*(.*)$/;
  const byFile = new Map(); // absolute fsPath -> Diagnostic[]
  for (const raw of text.split(/\r?\n/)) {
    const m = re.exec(raw);
    if (!m) continue;
    const file = path.resolve(m[1]);
    const line = Math.max(0, parseInt(m[2], 10) - 1);
    const severity =
      m[3] === "warning"
        ? vscode.DiagnosticSeverity.Warning
        : vscode.DiagnosticSeverity.Error;
    const range = lineRange(file, line);
    const d = new vscode.Diagnostic(range, m[4], severity);
    d.source = "idc";
    if (!byFile.has(file)) byFile.set(file, []);
    byFile.get(file).push(d);
  }
  return byFile;
}

// A range covering the offending line's text (first non-space to end), so the
// squiggle lands on the code rather than the indentation.
function lineRange(file, line) {
  let text = "";
  const open = vscode.workspace.textDocuments.find(
    (d) => d.uri.fsPath === file
  );
  if (open && line < open.lineCount) {
    text = open.lineAt(line).text;
  } else {
    try {
      text = (fs.readFileSync(file, "utf8").split(/\r?\n/)[line] || "");
    } catch (e) {
      /* ignore */
    }
  }
  const start = text.length - text.replace(/^\s+/, "").length;
  const end = Math.max(start + 1, text.length);
  return new vscode.Range(line, start, line, end);
}

// Replace diagnostics for every .id file in the linted scope, so fixed errors
// clear (idc reports one error at a time, plus any warnings).
function publish(byFile, target, scope) {
  const files =
    scope === "file" ? [target] : idFilesIn(target);
  for (const f of files) {
    const abs = path.resolve(f);
    const uri = vscode.Uri.file(abs);
    diagnostics.set(uri, byFile.get(abs) || []);
    byFile.delete(abs);
  }
  // any remaining files named in messages but outside the scope set
  for (const [abs, diags] of byFile) {
    diagnostics.set(vscode.Uri.file(abs), diags);
  }
}

// Every .id file in a project tree (so fixed errors clear across the project).
function idFilesIn(dir) {
  const out = [];
  const stack = [dir];
  while (stack.length) {
    const d = stack.pop();
    let ents;
    try {
      ents = fs.readdirSync(d, { withFileTypes: true });
    } catch (e) {
      continue;
    }
    for (const e of ents) {
      if (e.name.startsWith(".")) continue;
      const p = path.join(d, e.name);
      if (e.isDirectory()) stack.push(p);
      else if (e.name.endsWith(".id")) out.push(p);
    }
  }
  return out;
}

function deactivate() {
  for (const t of timers.values()) clearTimeout(t);
  timers.clear();
  if (diagnostics) diagnostics.clear();
}

module.exports = { activate, deactivate };
