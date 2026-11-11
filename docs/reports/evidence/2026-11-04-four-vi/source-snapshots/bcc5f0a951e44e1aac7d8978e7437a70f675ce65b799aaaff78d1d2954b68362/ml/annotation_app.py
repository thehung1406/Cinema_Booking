"""Loopback-only annotation tool. A person explicitly supplies every accepted label."""
import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading

from ml.data import read_jsonl, write_jsonl

HTML = """<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gán nhãn dữ liệu Cinema Booking</title><style>
body{font:16px system-ui;background:#f7f6f4;color:#202020;margin:0}main{max-width:900px;margin:40px auto;padding:24px}
.card{background:white;border:1px solid #ddd;border-radius:16px;padding:24px;margin:20px 0}button,input,select,textarea{font:inherit;padding:10px;border:1px solid #ccc;border-radius:8px}button{cursor:pointer;background:#a81f32;color:white}button:disabled{opacity:.5}label{display:block;margin:14px 0}input,textarea{box-sizing:border-box;width:100%}small{color:#666}#text{white-space:pre-wrap;line-height:1.7}#error{color:#a00}header{display:flex;gap:20px;align-items:center;justify-content:space-between}.hint{background:#fff3cd;padding:14px;border-radius:10px}</style>
<main><header><h1>Gán nhãn đánh giá phim</h1><span id="progress" role="status">Đang tải…</span></header>
<p>Đọc nội dung rồi chọn cảm xúc về phim. Nhận xét về dịch vụ, mỉa mai hoặc thiếu bối cảnh cần ghi chú và để chờ xử lý nếu chưa kết luận được.</p>
<p class="hint">Nhãn gợi ý từ AI không phải nhãn đã duyệt. Dữ liệu mẫu tổng hợp được đánh dấu riêng và không được tính là benchmark độc lập.</p>
<label>Người đang gán nhãn<input id="reviewer" placeholder="Tên thật hoặc mã thành viên của bạn" required></label>
<div class="card"><small id="identity"></small><p id="text"></p><p id="suggestion"></p>
<label>Nhãn<select id="label"><option value="">Chọn sau khi đọc</option><option value="positive">Tích cực</option><option value="neutral">Trung lập</option><option value="negative">Tiêu cực</option></select></label>
<label>Ghi chú<textarea id="note" rows="3" placeholder="Giải thích khi câu hỗn hợp, mỉa mai, nhầm đối tượng…"></textarea></label>
<button id="save" disabled>Xác nhận nhãn và chuyển tiếp</button> <button id="skip" disabled>Để lại chờ xử lý</button><p id="error" role="alert"></p><button id="retry" type="button" hidden>Thử tải lại</button></div>
<p><small>Kết quả được lưu trên máy vào file do người chạy công cụ chỉ định. Không tự huấn luyện, gửi dữ liệu ra API hoặc đưa lên GitHub.</small></p></main>
<script>
const token='__TOKEN__';let state=null,current=null,cursor=0;
const el=id=>document.getElementById(id);el('reviewer').value=localStorage.getItem('annotation-reviewer')||'';
async function request(path,options={}){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
try{const response=await fetch(path,{...options,signal:controller.signal,cache:'no-store'});const payload=await response.json();
if(!response.ok)throw new Error(payload.error||'Không tải được dữ liệu.');return payload;}finally{clearTimeout(timer);}}
async function load(){el('save').disabled=true;el('skip').disabled=true;el('retry').hidden=true;el('error').textContent='';el('progress').textContent='Đang tải…';
try{state=await request('/api/items',{headers:{'X-Annotation-Token':token}});show();}
catch(error){el('progress').textContent='Chưa kết nối được';el('error').textContent='Không tải được danh sách. Các nhãn đã xác nhận vẫn được lưu trên máy. Bấm Thử tải lại để kết nối lại.';el('retry').hidden=false;}}
el('retry').onclick=()=>window.location.reload();
function show(){const pending=state.items.filter(item=>item.review_status!=='approved');current=pending[cursor%Math.max(1,pending.length)];
el('progress').textContent=`${state.items.length-pending.length}/${state.items.length} đã duyệt`;
el('save').disabled=!current;el('skip').disabled=!current;el('label').value=current?.annotation_mode==='ai-assisted'?(current?.suggested_label||''):'';el('note').value='';
el('identity').textContent=current?`${current.id} · ${current.synthetic?'DỮ LIỆU TỔNG HỢP':'nguồn cần kiểm tra'} · ${current.source||'chưa có nguồn'}`:'';
el('text').textContent=current?.text||'Đã duyệt hết danh sách hiện tại.';
el('suggestion').textContent=current?.first_label?`Cần phân xử: lượt A = ${current.first_label}, lượt B = ${current.second_label}. Một người thứ ba đọc và ghi lý do quyết định.`:current?.suggested_label?`Gợi ý chưa được xác nhận: ${current.suggested_label}. ${current.suggested_reason||''}${current.suggested_needs_context?' · CẦN KIỂM TRA BỐI CẢNH':''}`:'';}
el('skip').onclick=()=>{cursor++;show();};el('save').onclick=async()=>{el('error').textContent='';if(!current)return;
const reviewer=el('reviewer').value.trim(),label=el('label').value;if(!reviewer||!label){el('error').textContent='Điền người gán nhãn và chọn nhãn trước khi xác nhận.';return;}
localStorage.setItem('annotation-reviewer',reviewer);el('save').disabled=true;
try{await request('/api/decision',{method:'POST',headers:{'Content-Type':'application/json','X-Annotation-Token':token},body:JSON.stringify({id:current.id,reviewer,label,note:el('note').value,revision:state.revision})});await load();}
catch(error){el('error').textContent=error.name==='AbortError'?'Kết nối phản hồi chậm. Bấm Thử tải lại để kiểm tra nhãn đã được lưu chưa.':error.message;el('save').disabled=false;el('retry').hidden=false;}};load();
</script></html>"""


def create_server(original, output, port=8765, host='127.0.0.1'):
    if host not in {'127.0.0.1','0.0.0.0'}:
        raise ValueError('Use loopback, or explicit container binding with a loopback-only published port')
    original, output = Path(original), Path(output)
    rows = read_jsonl(original)
    if output.exists():
        saved = read_jsonl(output)
        if [(r["id"], r["text"]) for r in saved] != [(r["id"], r["text"]) for r in rows]:
            raise ValueError("Saved annotations do not match this source file")
        rows = saved
    if len({str(row["id"]) for row in rows}) != len(rows):
        raise ValueError("Duplicate sample IDs")
    token, lock = secrets.token_hex(24), threading.Lock()

    def revision():
        return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    class Handler(BaseHTTPRequestHandler):
        timeout = 10  # Close idle preconnections without blocking other browser requests.
        def log_message(self, *args):
            pass  # Do not log review text, people or annotation tokens.

        def respond(self, code, payload):
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                body=HTML.replace("__TOKEN__", token).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/items" and secrets.compare_digest(self.headers.get("X-Annotation-Token", ""), token):
                with lock:
                    self.respond(200, {"items": rows, "revision": revision()})
            else:
                self.respond(404, {"error": "Not found"})

        def do_POST(self):
            if self.path != "/api/decision" or not secrets.compare_digest(self.headers.get("X-Annotation-Token", ""), token):
                self.respond(403, {"error": "Invalid annotation session"})
                return
            if self.headers.get("Origin") not in {None, f"http://127.0.0.1:{self.server.server_port}"}:
                self.respond(403, {"error": "Invalid origin"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 5000:
                    raise ValueError("Invalid request length")
                body = json.loads(self.rfile.read(length))
                with lock:
                    if body["revision"] != revision():
                        self.respond(409, {"error": "Danh sách đã thay đổi, tải lại trang."})
                        return
                    row = next(row for row in rows if str(row["id"]) == str(body["id"]))
                    if body["label"] not in {"positive", "neutral", "negative"} or not 1 <= len(body["reviewer"].strip()) <= 100:
                        raise ValueError("Nhãn hoặc người duyệt không hợp lệ")
                    adjudication = row.get("first_label") and row.get("second_label") and row["first_label"] != row["second_label"]
                    if adjudication and (not str(body.get("note", "")).strip() or body["reviewer"].strip().casefold() in
                            {str(row.get(key, "")).strip().casefold() for key in ("first_reviewer", "second_reviewer")}):
                        raise ValueError("Phân xử cần người thứ ba và ghi rõ lý do quyết định")
                    updated = row | dict(label=body["label"], reviewer=body["reviewer"].strip(), review_status="approved",
                               confirmed_at=datetime.now(timezone.utc).isoformat(),
                               annotation_note=str(body.get("note", ""))[:1000],
                               annotation_origin="manual-adjudication" if adjudication else
                                   "manual-ai-assisted-confirmation" if row.get('annotation_mode')=='ai-assisted' else "manual-tool-confirmation")
                    output.parent.mkdir(parents=True, exist_ok=True)
                    temporary = output.with_suffix(output.suffix+".tmp")
                    write_jsonl(temporary, [updated if item is row else item for item in rows])
                    temporary.replace(output)
                    row.update(updated)
                self.respond(200, {"saved": True})
            except (ValueError, KeyError, StopIteration) as exc:
                self.respond(422, {"error": str(exc) or "Invalid sample"})

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", choices=['127.0.0.1','0.0.0.0'],default='127.0.0.1',help='0.0.0.0 is for Docker with a loopback-only published port')
    args = parser.parse_args()
    server = create_server(args.input, args.output, args.port,args.host)
    print(f"Annotation tool: http://127.0.0.1:{server.server_port} (local only)", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
