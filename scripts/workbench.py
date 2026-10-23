#!/usr/bin/env python3
"""Vflow 可视化工作台。

零依赖本地服务（只用标准库）+ 剪映风格的单页看板：
项目库 / 预览 / 七阶段时间线 / 阶段产出 / 资产面板。

用法：
    python3 ~/Vflow/scripts/workbench.py            # 默认 http://127.0.0.1:8765
    VFLOW_PORT=9000 python3 ~/Vflow/scripts/workbench.py
    python3 ~/Vflow/scripts/workbench.py --no-open  # 不自动开浏览器

只监听 127.0.0.1。所有读写限制在 VFLOW_HOME 内。
"""
import html
import json
import os
import re
import subprocess
import sys
import webbrowser
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.abspath(
    os.environ.get("VFLOW_HOME") or os.path.expanduser("~/Vflow")
)
PORT = int(os.environ.get("VFLOW_PORT", "8765"))
UI = os.path.join(HERE, "workbench_ui.html")

import vflow_state as VS          # noqa: E402  项目状态机
import hooks as HK                # noqa: E402
import ledger as LG               # noqa: E402
import risk_scan as RS            # noqa: E402
import setup as SU                # noqa: E402  首次使用引导

MEDIA_EXT = (".mp4", ".mov", ".webm", ".m4v", ".png", ".jpg",
             ".jpeg", ".gif", ".webp", ".mp3", ".wav")


# ---------- Markdown 渲染 ----------

def esc(s):
    return html.escape(s, quote=False)


def inline(s):
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(^|[^*])\*([^*]+)\*", r"\1<em>\2</em>", s)
    s = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
               r'<a href="\2" target="_blank">\1</a>', s)
    return s


def render_md(text):
    """极简 Markdown → HTML。表格必须渲染成真 <table>。"""
    if not text.strip():
        return '<p class="empty">（空）</p>'
    lines = text.replace("\r\n", "\n").split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]

        if line.strip().startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(esc(lines[i]))
                i += 1
            i += 1
            out.append("<pre><code>%s</code></pre>" % "\n".join(buf))
            continue

        # 表格：以 | 开头，下一行是分隔行
        if line.startswith("|") and i + 1 < n and re.match(
                r"^\|?[\s:\-\|]+\|[\s:\-\|]*$", lines[i + 1]):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].startswith("|"):
                rows.append([c.strip() for c in
                             lines[i].strip().strip("|").split("|")])
                i += 1
            out.append("<table>")
            out.append("<thead><tr>%s</tr></thead>" %
                       "".join("<th>%s</th>" % inline(h) for h in header))
            out.append("<tbody>")
            for r in rows:
                cells = []
                for idx in range(len(header)):
                    v = r[idx] if idx < len(r) else ""
                    v = re.sub(r"^(✅|❌|⚠️|⏸|⛔)\s*", r"\1 ", v)
                    cells.append("<td>%s</td>" % inline(v))
                out.append("<tr>%s</tr>" % "".join(cells))
            out.append("</tbody></table>")
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lv = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lv, inline(m.group(2)), lv))
            i += 1
            continue

        if re.match(r"^\s*(-{3,}|\*{3,})\s*$", line):
            out.append("<hr>")
            i += 1
            continue

        if line.strip().startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>%s</blockquote>" % inline(" ".join(buf)))
            continue

        if re.match(r"^\s*[-*+]\s+", line):
            buf = []
            while i < n and re.match(r"^\s*[-*+]\s+", lines[i]):
                item = re.sub(r"^\s*[-*+]\s+", "", lines[i])
                checked = re.match(r"^\[( |x)\]\s*(.*)$", item)
                if checked:
                    mark = "checked" if checked.group(1) == "x" else ""
                    buf.append(
                        '<li class="task"><span class="box %s"></span>%s</li>'
                        % (mark, inline(checked.group(2))))
                else:
                    buf.append("<li>%s</li>" % inline(item))
                i += 1
            out.append("<ul>%s</ul>" % "".join(buf))
            continue

        if re.match(r"^\s*\d+[.)]\s+", line):
            buf = []
            while i < n and re.match(r"^\s*\d+[.)]\s+", lines[i]):
                buf.append("<li>%s</li>" % inline(
                    re.sub(r"^\s*\d+[.)]\s+", "", lines[i])))
                i += 1
            out.append("<ol>%s</ol>" % "".join(buf))
            continue

        if line.strip() == "":
            i += 1
            continue

        para = [line]
        i += 1
        while i < n and lines[i].strip() and not lines[i].startswith(("#", "|", ">")) \
                and not re.match(r"^\s*[-*+]\s+", lines[i]) \
                and not re.match(r"^\s*\d+[.)]\s+", lines[i]):
            para.append(lines[i])
            i += 1
        out.append("<p>%s</p>" % inline(" ".join(para)))

    return "\n".join(out)


# ---------- 项目数据 ----------

def project_payload(slug, with_files=True):
    st = VS.build_state(slug)
    try:
        old = VS.load_state(slug)
        for k in ("final", "drafts", "hooks", "metrics", "platforms"):
            if k in old:
                st[k] = old[k]
        VS.write_state(slug, st)
    except OSError:
        pass

    if with_files:
        files, raw = {}, {}
        for key, name, fname, skill in VS.STAGES:
            p = os.path.join(VS.slug_dir(slug), fname)
            if os.path.isfile(p):
                try:
                    with open(p, encoding="utf-8") as fh:
                        txt = fh.read()
                except (OSError, UnicodeDecodeError):
                    txt = ""
                raw[fname] = txt
                files[fname] = render_md(txt)
        st["files"] = files
        st["raw"] = raw
    return st


def assets_payload():
    # 钩子
    hooks_rows = HK.parse_hooks()
    ranking = []
    for h in hooks_rows:
        eff = sum(1 for r in h["rows"] if r.get("verdict") == "有效")
        bad = sum(1 for r in h["rows"] if r.get("verdict") == "无效")
        scoring = eff * 2 - bad + (1 if not h["rows"] else 0)
        ranking.append({
            "id": h["id"], "name": h["name"], "used": len(h["rows"]),
            "effective": eff, "invalid": bad, "score": scoring,
            "template": h.get("template", ""), "rows": h["rows"],
        })
    ranking.sort(key=lambda x: -x["score"])

    # 台账
    led = LG.parse(LG.read_text(LG.LEDGER_MD))
    cands = []
    for r in led["candidate"]:
        try:
            n = int(str(r.get("count", "1")))
        except ValueError:
            n = 1
        cands.append({"id": r["id"], "observation": r["text"],
                      "evidence": n, "projects": r.get("projects", ""),
                      "ready": n >= LG.PROMOTE_THRESHOLD})
    ledger = {"candidates": cands,
              "promoted": led["promoted"], "retracted": led["retracted"],
              "threshold": LG.PROMOTE_THRESHOLD}

    # 风格卡
    card_path = os.path.join(ROOT, "assets", "voice-card.json")
    voice = {"ok": False, "reason": "还没有风格卡，先跑 voice_profile.py build"}
    if os.path.isfile(card_path):
        try:
            with open(card_path, encoding="utf-8") as fh:
                c = json.load(fh)
            voice = {"ok": True, **{k: c.get(k) for k in (
                "avg_sent_len", "median_sent_len", "max_sent_len",
                "short_sent_ratio", "question_ratio", "exclaim_ratio",
                "first_person_per_100", "latin_per_1000", "emoji",
                "tone_markers", "absent", "samples", "built_at", "chars")}}
        except (json.JSONDecodeError, OSError):
            pass

    # 词表
    wl = RS.load_words()
    wordlist = {"counts": {k: len(set(v)) for k, v in wl.items()}}

    return {"hooks": {"ranking": ranking}, "ledger": ledger,
            "voice": voice, "wordlist": wordlist}


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, ctype):
        with open(path, "rb") as fh:
            data = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        p = unquote(u.path)

        if p in ("/", "/index.html"):
            if os.path.isfile(UI):
                with open(UI, "rb") as fh:
                    data = fh.read()
                self.send_response(200)
                self.send_header("Content-Type",
                                 "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_json({"error": "缺少 workbench_ui.html"}, 500)
            return

        if p == "/api/state":
            self.send_json(VS.cmd_list(None))
            return

        if p == "/api/setup":
            self.send_json(SU.status())
            return

        if p == "/api/assets":
            self.send_json(assets_payload())
            return

        if p.startswith("/api/project/"):
            slug = p[len("/api/project/"):]
            d = VS.slug_dir(slug)
            if not os.path.isdir(d):
                self.send_json({"error": "项目不存在"}, 404)
                return
            self.send_json(project_payload(slug))
            return

        if p == "/api/open":
            q = parse_qs(u.query)
            target = (q.get("path") or [""])[0].strip()
            path = ROOT
            if target:
                found = None
                for cand in (os.path.join(ROOT, target), VS.slug_dir(target)):
                    real = os.path.abspath(cand)
                    if real == ROOT or real.startswith(ROOT + os.sep):
                        if os.path.exists(real):
                            found = real
                            break
                if not found:
                    self.send_json({"error": "路径不存在或超出数据目录"}, 404)
                    return
                path = found
            try:
                subprocess.run(["open", path], check=False, timeout=8)
                opened = True
                err = ""
            except Exception as exc:      # 无 GUI / 沙箱 / 命令不存在
                opened = False
                err = str(exc)
            self.send_json({"ok": opened, "path": path,
                            "error": err or None})
            return

        if p.startswith("/media/"):
            rest = p[len("/media/"):]
            slug, _, rel = rest.partition("/")
            full = os.path.abspath(os.path.join(VS.slug_dir(slug), rel))
            if not full.startswith(VS.slug_dir(slug)) or \
                    not os.path.isfile(full):
                self.send_json({"error": "文件不存在"}, 404)
                return
            ext = os.path.splitext(full)[1].lower()
            ctype = {".mp4": "video/mp4", ".mov": "video/quicktime",
                     ".webm": "video/webm", ".m4v": "video/mp4",
                     ".png": "image/png", ".jpg": "image/jpeg",
                     ".jpeg": "image/jpeg", ".gif": "image/gif",
                     ".webp": "image/webp", ".mp3": "audio/mpeg",
                     ".wav": "audio/wav"}.get(ext, "application/octet-stream")
            self.send_file(full, ctype)
            return

        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        p = unquote(u.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {}

        if p == "/api/projects":
            name = (body.get("name") or "").strip()
            if not name:
                self.send_json({"error": "项目名不能为空"}, 400)
                return
            slug = "%s-%s" % (datetime.now().strftime("%Y%m%d"), name)
            d = VS.slug_dir(slug)
            if os.path.isdir(d):
                self.send_json({"error": "已存在同名项目"}, 400)
                return
            script = os.path.join(ROOT, "scripts", "new_project.sh")
            if os.path.isfile(script):
                subprocess.run(["bash", script, name], check=False,
                               cwd=ROOT)
            else:
                os.makedirs(os.path.join(d, "assets"), exist_ok=True)
                os.makedirs(os.path.join(d, "output"), exist_ok=True)
            if not os.path.isdir(d):
                self.send_json({"error": "创建失败"}, 500)
                return
            VS.write_state(slug, VS.build_state(slug))
            self.send_json({"ok": True, "slug": slug,
                            "project": project_payload(slug)})
            return

        if p.startswith("/api/project/") and p.endswith("/stage"):
            slug = p[len("/api/project/"):-len("/stage")]
            d = VS.slug_dir(slug)
            if not os.path.isdir(d):
                self.send_json({"error": "项目不存在"}, 404)
                return
            key = str(body.get("key", ""))
            status = body.get("status", "done")
            if key not in VS.build_state(slug)["stages"]:
                self.send_json({"error": "阶段不存在"}, 400)
                return
            VS.cmd_set(type("A", (), {"slug": slug, "stage": key,
                                      "status": status})())
            self.send_json({"ok": True, "project": project_payload(slug)})
            return

        self.send_json({"error": "not found"}, 404)


def main():
    if "--no-open" not in sys.argv:
        try:
            webbrowser.open("http://127.0.0.1:%d" % PORT)
        except Exception:
            pass
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("Vflow 工作台：http://127.0.0.1:%d  (数据目录 %s)" % (PORT, ROOT))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        srv.shutdown()


if __name__ == "__main__":
    main()
