#!/usr/bin/env python3
"""Vflow 可视化工作台。

一个零依赖的本地服务（只用 Python 标准库）+ 单页看板：
看全部项目在哪个阶段、点开看各阶段产出、开新项目、推阶段、打开目录。

用法：
    python3 ~/Vflow/scripts/workbench.py            # 默认 http://127.0.0.1:8765
    VFLOW_PORT=9000 python3 ~/Vflow/scripts/workbench.py

只监听 127.0.0.1，不对外暴露。所有写操作限制在 VFLOW_HOME 目录内。
"""
import html
import json
import os
import re
import subprocess
import sys
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, urlparse

ROOT = os.path.abspath(
    os.environ.get("VFLOW_HOME") or os.path.expanduser("~/Vflow")
)
PORT = int(os.environ.get("VFLOW_PORT", "8765"))
HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(HERE, "workbench_ui.html")

# 七阶段：编号 / 名字 / 产出文件 / 负责技能
STAGES = [
    ("01", "选题", "01-topic.md", "vflow-topic"),
    ("02", "结构", "02-outline.md", "vflow-outline"),
    ("03", "剧本", "03-script.md", "vflow-script"),
    ("04", "包装", "04-package.md", "vflow-package"),
    ("05", "检查", "05-check.md", "vflow-check"),
    ("06", "制作", "publish-copy.md", "vflow-produce"),
    ("07", "复盘", "06-review.md", "vflow-review"),
]

CHECKBOX_RE = re.compile(r"^- \[( |x)\] (\d{2}) ", re.M)
TEMPLATE_MARK = "<!-- vflow-template"


def safe_path(*parts):
    """把路径限制在 ROOT 内，挡掉 ../ 穿越。"""
    target = os.path.abspath(os.path.join(ROOT, *parts))
    if target != ROOT and not target.startswith(ROOT + os.sep):
        raise ValueError("path escapes VFLOW_HOME")
    return target


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return ""


def stage_state(slug_dir, readme):
    """返回每阶段的完成勾选状态、以及产出文件是否真写了内容。"""
    done = {}
    for m in CHECKBOX_RE.finditer(readme):
        done[m.group(2)] = m.group(1) == "x"
    out = []
    for key, name, fname, skill in STAGES:
        content = read_text(os.path.join(slug_dir, fname))
        # 新建项目会把空模板一起复制进去，带标记的不算"有产出"
        filled = bool(content.strip()) and TEMPLATE_MARK not in content
        out.append({
            "key": key, "name": name, "file": fname, "skill": skill,
            "done": done.get(key, False),
            "hasFile": filled,
        })
    return out


def current_stage(stages):
    """第一个还没完成的阶段；全完成就是已发布。"""
    for s in stages:
        if not (s["done"] or s["hasFile"]):
            return {"key": s["key"], "name": s["name"]}
    return {"key": "done", "name": "已发布"}


def list_projects():
    pdir = os.path.join(ROOT, "projects")
    items = []
    if not os.path.isdir(pdir):
        return items
    for slug in sorted(os.listdir(pdir), reverse=True):
        slug_dir = os.path.join(pdir, slug)
        if not os.path.isdir(slug_dir) or slug.startswith("."):
            continue
        readme = read_text(os.path.join(slug_dir, "README.md"))
        stages = stage_state(slug_dir, readme)
        title = slug
        m = re.search(r"^# (.+)$", readme, re.M)
        if m:
            title = m.group(1).strip()
        created = ""
        m = re.search(r"创建:\s*([\d\-]+)", readme)
        if m:
            created = m.group(1)
        items.append({
            "slug": slug, "title": title, "created": created,
            "stages": stages, "current": current_stage(stages),
            "progress": sum(1 for s in stages if s["done"] or s["hasFile"]),
        })
    return items


def new_project(name):
    name = name.strip().replace("/", "-")
    if not name:
        raise ValueError("项目名不能为空")
    script = os.path.join(ROOT, "scripts", "new_project.sh")
    subprocess.run(["bash", script, name], check=True,
                   capture_output=True, text=True)
    # 脚本生成 YYYYMMDD-<name>，取最新那个
    cands = [d for d in os.listdir(os.path.join(ROOT, "projects"))
             if d.endswith("-" + name)]
    return sorted(cands)[-1] if cands else name


def set_stage(slug, key, done):
    path = safe_path("projects", slug, "README.md")
    text = read_text(path)
    if not text:
        raise ValueError("项目没有 README.md")

    def repl(m):
        if m.group(2) == key:
            return "- [%s] %s " % ("x" if done else " ", key)
        return m.group(0)

    new = CHECKBOX_RE.sub(repl, text)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new)


def render_md(text):
    """极简 markdown 渲染：标题、勾选框、列表、粗体、代码块、表格。"""
    if not text.strip():
        return '<p class="empty">（还没写）</p>'
    out = []
    in_code = False
    for line in html.escape(text).split("\n"):
        if line.strip().startswith("```"):
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(line)
            continue
        line = re.sub(r"^- \[( |x)\] (.*)$",
                      lambda m: '<div class="check %s">%s</div>'
                      % ("on" if m.group(1) == "x" else "", m.group(2)),
                      line)
        line = re.sub(r"^(#{1,6}) (.*)$",
                      lambda m: "<h%d>%s</h%d>" % (
                          min(len(m.group(1)) + 2, 6), m.group(2),
                          min(len(m.group(1)) + 2, 6)), line)
        line = re.sub(r"^&gt; (.*)$", r'<blockquote>\1</blockquote>', line)
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        line = re.sub(r"`(.+?)`", r"<code>\1</code>", line)
        line = re.sub(r"^---+$", "<hr>", line)
        if line.startswith("|") and "|" in line[1:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells):
                continue  # 表格分隔行
            out.append("<tr>" + "".join(
                "<td>%s</td>" % c for c in cells) + "</tr>")
            continue
        out.append(line)
    body = "\n".join(out)
    # 把连续的 <tr> 合并进一个 <table>
    body = re.sub(r"(?:<tr>.*?</tr>\s*)+",
                  lambda m: "<table>%s</table>" % m.group(0).strip(),
                  body, flags=re.S)
    return body


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[vflow] %s\n" % (fmt % args))

    def _send(self, code, payload, ctype="application/json"):
        raw = payload.encode("utf-8") if isinstance(payload, str) else payload
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            return {}

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        try:
            if path in ("/", "/ui"):
                self._send(200, read_text(UI), "text/html")
            elif path == "/api/state":
                self._json({
                    "root": ROOT,
                    "profileExists": os.path.isfile(os.path.join(ROOT, "profile.md")),
                    "projects": list_projects(),
                    "stages": [{"key": k, "name": n, "skill": s}
                               for k, n, _, s in STAGES],
                })
            elif path.startswith("/api/project/"):
                slug = path[len("/api/project/"):]
                slug_dir = safe_path("projects", slug)
                readme = read_text(os.path.join(slug_dir, "README.md"))
                stages = stage_state(slug_dir, readme)
                files = {}
                for s in stages:
                    files[s["file"]] = render_md(
                        read_text(os.path.join(slug_dir, s["file"])))
                self._json({"slug": slug, "stages": stages, "files": files,
                            "readme": readme})
            elif path == "/api/profile":
                self._json({"content": render_md(
                    read_text(safe_path("profile.md")))})
            else:
                self._json({"error": "not found"}, 404)
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001
            self._json({"error": str(exc)}, 500)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        body = self._body()
        try:
            if path == "/api/projects":
                slug = new_project(body.get("name", ""))
                self._json({"ok": True, "slug": slug})
            elif path.startswith("/api/project/") and path.endswith("/stage"):
                slug = path[len("/api/project/"):-len("/stage")]
                set_stage(slug, body.get("key", ""), bool(body.get("done")))
                self._json({"ok": True})
            elif path == "/api/open":
                target = safe_path(body.get("path", ""))
                subprocess.Popen(["open", target])
                self._json({"ok": True})
            else:
                self._json({"error": "not found"}, 404)
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001
            self._json({"error": str(exc)}, 500)


def main():
    if not os.path.isdir(ROOT):
        sys.exit("VFLOW_HOME 不存在: %s" % ROOT)
    url = "http://127.0.0.1:%d" % PORT
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("Vflow 工作台: %s  (数据目录 %s)" % (url, ROOT))
    print("Ctrl+C 停止")
    if "--no-open" not in sys.argv:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
