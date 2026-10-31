from __future__ import annotations
import os
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from datamate.core.types import AnswerType, QuestionItem, SubmissionItem
from datamate.data.loader import BusinessDataLoader
from datamate.data.schema_inspector import SchemaInspector
from datamate.engine.agent import DataMateAgent
from datamate.engine.rule_compiler import BusinessRuleCompiler
from datamate.evaluator.metric import compute_penalized_accuracy
from datamate.temporal.resolver import TemporalResolver

app = FastAPI(title="DataMate Interactive Playground", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Default data directory is data/sample or environment variable
DATA_ROOT = os.environ.get("DATAMATE_DATA_DIR", os.path.abspath("data/sample"))
agent = DataMateAgent(DATA_ROOT)


class AskRequest(BaseModel):
    business_id: str
    question: str
    as_of_date: str = "2026-03-04"


@app.get("/api/businesses")
def get_businesses():
    if not os.path.exists(DATA_ROOT):
        return []
    biz_list = []
    for d in sorted(os.listdir(DATA_ROOT)):
        full_p = os.path.join(DATA_ROOT, d)
        if os.path.isdir(full_p):
            readme_p = os.path.join(full_p, "README.md")
            readme_content = ""
            if os.path.exists(readme_p):
                with open(readme_p, "r", encoding="utf-8", errors="replace") as f:
                    readme_content = f.read()
            biz_list.append({"id": d, "readme": readme_content})
    return biz_list


@app.get("/api/business/{biz_id}/tables")
def get_business_tables(biz_id: str):
    biz_dir = os.path.join(DATA_ROOT, biz_id)
    if not os.path.exists(biz_dir):
        raise HTTPException(status_code=404, detail="Business not found")

    loader = agent.get_or_load_business(biz_id)
    tables_meta = SchemaInspector.inspect(loader.conn)

    res = {}
    for t_name, t_info in tables_meta.items():
        # Fetch first 10 rows
        cursor = loader.conn.cursor()
        cursor.execute(f"SELECT * FROM `{t_name}` LIMIT 10;")
        col_names = [d[0] for d in cursor.description]
        rows = cursor.fetchall()

        res[t_name] = {
            "row_count": t_info.row_count,
            "columns": [c.model_dump() for c in t_info.columns],
            "preview_cols": col_names,
            "preview_rows": [list(r) for r in rows],
        }
    return res


@app.post("/api/ask")
def ask_question(req: AskRequest):
    t_start = time.time()
    q_item = QuestionItem(
        id=f"q_{int(time.time() * 1000)}",
        business_id=req.business_id,
        question=req.question,
        as_of_date=req.as_of_date,
    )

    # 1. Resolve temporal
    temp_range = TemporalResolver.resolve(req.question, req.as_of_date)
    temp_info = (
        {
            "start_date": temp_range.start_date,
            "end_date": temp_range.end_date,
            "target_month": temp_range.target_month,
            "is_exact_day": temp_range.is_exact_day,
        }
        if temp_range
        else None
    )

    # 2. Get business schema
    loader = agent.get_or_load_business(req.business_id)
    tables = SchemaInspector.inspect(loader.conn)

    # 3. Plan compilation
    plan = BusinessRuleCompiler.compile(req.question, req.as_of_date, tables)

    # 4. Agent answer
    sub_item = agent.answer_question(q_item)
    latency_ms = round((time.time() - t_start) * 1000, 2)

    return {
        "submission": sub_item.to_dict(),
        "temporal": temp_info,
        "plan": {
            "intent": plan.intent,
            "expected_type": plan.expected_type.value,
            "sql": plan.sql,
            "confidence": plan.confidence,
            "unanswerable_reason": plan.unanswerable_reason,
        },
        "latency_ms": latency_ms,
    }


@app.get("/api/sample-questions")
def get_sample_questions():
    q_file = os.path.join(DATA_ROOT, "questions.jsonl")
    if not os.path.exists(q_file):
        return []
    items = []
    with open(q_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                import json
                items.append(json.loads(line))
    return items


@app.get("/", response_class=HTMLResponse)
def index_html():
    return HTML_CONTENT


HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DataMate AI Playground — Zalo AI Challenge 2026</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; }
    .code-font { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
  </style>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen flex flex-col">

  <!-- Header -->
  <header class="border-b border-slate-800 bg-slate-950/70 backdrop-blur sticky top-0 z-40">
    <div class="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
          <i class="fa-solid fa-robot text-white text-lg"></i>
        </div>
        <div>
          <h1 class="font-bold text-lg text-white flex items-center gap-2">
            DataMate Agentic AI
            <span class="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30 font-medium">Zalo AI Challenge 2026</span>
          </h1>
          <p class="text-xs text-slate-400">Talking To Your Data Through Agentic AI & Vietnamese Semantic Parsing</p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <span class="inline-flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full font-medium">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          Penalized Accuracy (PA) Enabled (+1 / 0 / -1)
        </span>
      </div>
    </div>
  </header>

  <!-- Main Container -->
  <main class="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">

    <!-- Left Column: Business Selection & Schema Explorer (4 cols) -->
    <div class="lg:col-span-4 flex flex-col gap-5">
      <!-- Business Selector Card -->
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-5 shadow-xl">
        <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
          <i class="fa-solid fa-store text-blue-400"></i> Doanh Nghiệp (Business Package)
        </h2>
        <select id="businessSelect" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50">
          <option value="" disabled selected>Đang tải danh sách doanh nghiệp...</option>
        </select>
        <div id="bizReadme" class="mt-3.5 text-xs text-slate-400 bg-slate-900/80 p-3 rounded-xl border border-slate-700/40 line-clamp-3">
          Chọn một doanh nghiệp để xem thông tin
        </div>
      </div>

      <!-- Tables Explorer Card -->
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-5 shadow-xl flex-1 flex flex-col">
        <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center justify-between">
          <span class="flex items-center gap-2"><i class="fa-solid fa-database text-purple-400"></i> Bảng Dữ Liệu (Tables)</span>
          <span id="tableCountBadge" class="text-xs bg-slate-700 px-2 py-0.5 rounded-full text-slate-300">0 bảng</span>
        </h2>
        <div id="tablesContainer" class="space-y-3 overflow-y-auto max-h-[380px] pr-1 flex-1">
          <p class="text-xs text-slate-500 italic text-center py-8">Chưa có dữ liệu bảng</p>
        </div>
      </div>
    </div>

    <!-- Right Column: Interactive Chat & QA Playground (8 cols) -->
    <div class="lg:col-span-8 flex flex-col gap-5">
      
      <!-- Query Input Card -->
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-5 shadow-xl">
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-3">
          <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
            <i class="fa-solid fa-comment-dots text-emerald-400"></i> Đặt câu hỏi bằng Tiếng Việt
          </h2>
          <!-- As-of date selector -->
          <div class="flex items-center gap-2 text-xs bg-slate-900 border border-slate-700 px-3 py-1.5 rounded-xl">
            <span class="text-slate-400"><i class="fa-regular fa-calendar-check text-blue-400 mr-1"></i> As-of Date:</span>
            <input type="date" id="asOfDate" value="2026-03-04" class="bg-transparent text-white font-medium focus:outline-none">
          </div>
        </div>

        <!-- Sample question pills -->
        <div class="mb-3">
          <span class="text-xs text-slate-400 mr-2">Gợi ý mẫu:</span>
          <div id="samplePills" class="inline-flex flex-wrap gap-1.5 mt-1.5">
            <!-- Rendered by JS -->
          </div>
        </div>

        <div class="relative">
          <textarea id="questionInput" rows="2" placeholder="Ví dụ: sp bán dc nhiều nhất tuần rồi là gì, doanh thu tháng này là bao nhiêu..." class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 resize-none"></textarea>
          <button id="askBtn" class="absolute right-3 bottom-3 px-4 py-1.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-lg text-xs font-semibold shadow-md transition flex items-center gap-2">
            <span>Hỏi Agent</span>
            <i class="fa-solid fa-paper-plane text-[10px]"></i>
          </button>
        </div>
      </div>

      <!-- Execution & Answer Results Card -->
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-5 shadow-xl flex-1 flex flex-col">
        <div class="flex items-center justify-between pb-3 border-b border-slate-700/60 mb-4">
          <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <i class="fa-solid fa-wand-magic-sparkles text-amber-400"></i> Kết quả Suy Luận (Agent Execution)
          </h3>
          <div id="latencyTag" class="text-xs text-slate-400"></div>
        </div>

        <!-- Answer Hero Box -->
        <div id="answerHero" class="bg-gradient-to-r from-slate-900 to-slate-950 border border-slate-700/80 rounded-xl p-5 mb-5 flex flex-col gap-2">
          <div class="flex items-center justify-between">
            <span class="text-xs uppercase tracking-wider text-slate-400 font-medium">Câu trả lời (Output Answer)</span>
            <span id="answerTypeBadge" class="text-xs px-2.5 py-0.5 rounded-full bg-slate-700 text-slate-300 font-mono">--</span>
          </div>
          <div id="answerValue" class="text-xl md:text-2xl font-bold text-white mt-1">
            Hãy chọn doanh nghiệp và đặt câu hỏi ở trên để bắt đầu!
          </div>
        </div>

        <!-- Deep Inspection Details Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 flex-1">
          <!-- Temporal Resolution Card -->
          <div class="bg-slate-900/70 border border-slate-800 p-3.5 rounded-xl">
            <h4 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <i class="fa-solid fa-clock-rotate-left text-blue-400"></i> Phân giải Thời gian (Temporal)
            </h4>
            <div id="temporalInfo" class="text-xs text-slate-300 space-y-1">
              <p class="text-slate-500 italic">Chưa có thông tin</p>
            </div>
          </div>

          <!-- Semantic Plan & Intent Card -->
          <div class="bg-slate-900/70 border border-slate-800 p-3.5 rounded-xl">
            <h4 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <i class="fa-solid fa-brain text-purple-400"></i> Ý định & Độ tin cậy (Intent & Confidence)
            </h4>
            <div id="planInfo" class="text-xs text-slate-300 space-y-1">
              <p class="text-slate-500 italic">Chưa có thông tin</p>
            </div>
          </div>

          <!-- Generated SQL Query Card (Full width) -->
          <div class="md:col-span-2 bg-slate-900/70 border border-slate-800 p-3.5 rounded-xl">
            <h4 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center justify-between">
              <span class="flex items-center gap-1.5"><i class="fa-solid fa-code text-emerald-400"></i> Truy vấn SQL Sinh ra (Compiled SQL)</span>
              <button id="copySqlBtn" class="text-[11px] text-slate-400 hover:text-white transition"><i class="fa-regular fa-copy"></i> Sao chép</button>
            </h4>
            <pre id="sqlCode" class="code-font text-xs text-emerald-300 bg-slate-950 p-3 rounded-lg overflow-x-auto border border-slate-800/80">-- SQL sẽ hiển thị tại đây khi thực thi</pre>
          </div>
        </div>

      </div>

    </div>

  </main>

  <!-- Table Modal -->
  <div id="tableModal" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950">
        <h3 id="modalTableTitle" class="font-bold text-white text-base flex items-center gap-2">
          <i class="fa-solid fa-table text-blue-400"></i> Chi tiết bảng
        </h3>
        <button id="closeModalBtn" class="text-slate-400 hover:text-white text-lg"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div id="modalTableContent" class="p-6 overflow-auto flex-1">
        <!-- Injected by JS -->
      </div>
    </div>
  </div>

  <script>
    let businesses = [];
    let currentTables = {};

    async function init() {
      await loadBusinesses();
      await loadSampleQuestions();
      setupEvents();
    }

    async function loadBusinesses() {
      try {
        const res = await fetch('/api/businesses');
        businesses = await res.json();
        const sel = document.getElementById('businessSelect');
        sel.innerHTML = '';
        businesses.forEach((b, idx) => {
          const opt = document.createElement('option');
          opt.value = b.id;
          opt.textContent = `${b.id} — ${b.readme.split('\\n')[0].replace('#', '').trim() || 'Doanh nghiệp'}`;
          sel.appendChild(opt);
        });
        if (businesses.length > 0) {
          sel.value = businesses[0].id;
          onBusinessChange(businesses[0].id);
        }
      } catch (e) {
        console.error('Error loading businesses:', e);
      }
    }

    async function onBusinessChange(bizId) {
      const b = businesses.find(x => x.id === bizId);
      if (b) {
        document.getElementById('bizReadme').textContent = b.readme || 'Không có mô tả';
      }
      // Load tables
      try {
        const res = await fetch(`/api/business/${bizId}/tables`);
        currentTables = await res.json();
        renderTables(currentTables);
      } catch (e) {
        console.error('Error loading tables:', e);
      }
    }

    function renderTables(tables) {
      const container = document.getElementById('tablesContainer');
      const keys = Object.keys(tables);
      document.getElementById('tableCountBadge').textContent = `${keys.length} bảng`;
      if (keys.length === 0) {
        container.innerHTML = '<p class="text-xs text-slate-500 italic text-center py-8">Không có bảng nào</p>';
        return;
      }
      container.innerHTML = '';
      keys.forEach(tName => {
        const t = tables[tName];
        const card = document.createElement('div');
        card.className = 'bg-slate-900/90 border border-slate-700/60 hover:border-blue-500/40 p-3 rounded-xl transition cursor-pointer flex items-center justify-between';
        card.onclick = () => openTableModal(tName, t);
        card.innerHTML = `
          <div>
            <div class="font-semibold text-xs text-blue-400 flex items-center gap-1.5">
              <i class="fa-solid fa-table text-[10px]"></i> \${tName}
            </div>
            <div class="text-[11px] text-slate-400 mt-0.5">
              \${t.columns.length} cột • \${t.row_count} dòng
            </div>
          </div>
          <span class="text-slate-500 text-xs hover:text-white"><i class="fa-solid fa-eye"></i></span>
        `;
        container.appendChild(card);
      });
    }

    function openTableModal(tName, t) {
      document.getElementById('modalTableTitle').innerHTML = `<i class="fa-solid fa-table text-blue-400"></i> Bảng: \${tName} (\${t.row_count} dòng)`;
      const content = document.getElementById('modalTableContent');
      
      let html = `<div class="mb-4">
        <h4 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Các cột & Vai trò ngữ nghĩa (Semantic Roles)</h4>
        <div class="flex flex-wrap gap-2">`;
      t.columns.forEach(c => {
        const roleBadge = c.semantic_role 
          ? `<span class="bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded text-[10px]">\${c.semantic_role}</span>`
          : `<span class="bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded text-[10px]">default</span>`;
        html += `<div class="bg-slate-800/80 border border-slate-700/60 px-2.5 py-1.5 rounded-lg text-xs flex items-center gap-2">
          <span class="font-mono text-slate-200">\${c.name}</span>
          \${roleBadge}
        </div>`;
      });
      html += `</div></div>`;

      // Preview Table
      html += `<h4 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Xem trước dữ liệu (Top 10 rows)</h4>
      <div class="overflow-x-auto border border-slate-800 rounded-xl">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800">
            <tr>`;
      t.preview_cols.forEach(c => {
        html += `<th class="px-3 py-2.5">\${c}</th>`;
      });
      html += `</tr></thead><tbody class="divide-y divide-slate-800 text-slate-300">`;
      t.preview_rows.forEach(r => {
        html += `<tr class="hover:bg-slate-800/40">`;
        r.forEach(v => {
          html += `<td class="px-3 py-2 whitespace-nowrap">\${v !== null ? v : '<span class="text-slate-600">NULL</span>'}</td>`;
        });
        html += `</tr>`;
      });
      html += `</tbody></table></div>`;

      content.innerHTML = html;
      document.getElementById('tableModal').classList.remove('hidden');
    }

    async function loadSampleQuestions() {
      try {
        const res = await fetch('/api/sample-questions');
        const qList = await res.json();
        const pillsContainer = document.getElementById('samplePills');
        pillsContainer.innerHTML = '';
        qList.forEach(q => {
          const btn = document.createElement('button');
          btn.className = 'text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/60 px-2.5 py-1 rounded-lg transition';
          btn.textContent = q.question;
          btn.onclick = () => {
            document.getElementById('businessSelect').value = q.business_id;
            onBusinessChange(q.business_id);
            document.getElementById('questionInput').value = q.question;
            if (q.as_of_date) {
              document.getElementById('asOfDate').value = q.as_of_date;
            }
          };
          pillsContainer.appendChild(btn);
        });
      } catch (e) {
        console.error('Error loading sample questions:', e);
      }
    }

    function setupEvents() {
      document.getElementById('businessSelect').onchange = (e) => onBusinessChange(e.target.value);
      document.getElementById('closeModalBtn').onclick = () => document.getElementById('tableModal').classList.add('hidden');
      document.getElementById('askBtn').onclick = ask;
      document.getElementById('questionInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          ask();
        }
      });
      document.getElementById('copySqlBtn').onclick = () => {
        const sql = document.getElementById('sqlCode').textContent;
        navigator.clipboard.writeText(sql);
        alert('Đã sao chép câu lệnh SQL!');
      };
    }

    async function ask() {
      const bizId = document.getElementById('businessSelect').value;
      const question = document.getElementById('questionInput').value.trim();
      const asOfDate = document.getElementById('asOfDate').value;
      if (!question) return;

      const btn = document.getElementById('askBtn');
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner animate-spin"></i> Đang xử lý...';

      try {
        const res = await fetch('/api/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ business_id: bizId, question: question, as_of_date: asOfDate })
        });
        const data = await res.json();
        renderResult(data);
      } catch (e) {
        alert('Lỗi truy vấn: ' + e.message);
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>Hỏi Agent</span><i class="fa-solid fa-paper-plane text-[10px]"></i>';
      }
    }

    function renderResult(data) {
      document.getElementById('latencyTag').textContent = `Thời gian xử lý: \${data.latency_ms} ms`;
      const sub = data.submission;
      const typeBadge = document.getElementById('answerTypeBadge');
      typeBadge.textContent = sub.type.toUpperCase();

      const ansVal = document.getElementById('answerValue');
      if (sub.type === 'unanswerable') {
        typeBadge.className = 'text-xs px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30 font-mono';
        ansVal.innerHTML = `<span class="text-amber-400"><i class="fa-solid fa-triangle-exclamation mr-2"></i>UNANSWERABLE</span> <span class="text-sm font-normal text-slate-400 block mt-1">Dữ liệu hiện tại không đủ để trả lời câu hỏi này.</span>`;
      } else if (sub.type === 'abstain') {
        typeBadge.className = 'text-xs px-2.5 py-0.5 rounded-full bg-slate-500/20 text-slate-400 border border-slate-500/30 font-mono';
        ansVal.innerHTML = `<span class="text-slate-400"><i class="fa-solid fa-hand mr-2"></i>ABSTAIN</span> <span class="text-sm font-normal text-slate-400 block mt-1">Agent chủ động từ chối trả lời để bảo vệ điểm số (0 điểm thay vì mạo hiểm bị -1).</span>`;
      } else {
        typeBadge.className = 'text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-mono';
        let displayVal = sub.answer;
        if (typeof sub.answer === 'number') {
          displayVal = Number(sub.answer).toLocaleString('vi-VN');
          if (sub.type === 'percent') displayVal += ' %';
          else if (sub.type === 'number' && sub.answer >= 1000) displayVal += ' VNĐ';
        } else if (Array.isArray(sub.answer)) {
          displayVal = `<ul class="list-disc list-inside text-sm font-medium mt-1">` + sub.answer.map(x => `<li>\${x}</li>`).join('') + `</ul>`;
        }
        ansVal.innerHTML = `<span class="text-emerald-400">\${displayVal}</span>`;
      }

      // Temporal
      const tempDiv = document.getElementById('temporalInfo');
      if (data.temporal) {
        tempDiv.innerHTML = `
          <div><strong class="text-slate-400">Từ ngày:</strong> \${data.temporal.start_date}</div>
          <div><strong class="text-slate-400">Đến ngày:</strong> \${data.temporal.end_date}</div>
          \${data.temporal.target_month ? `<div><strong class="text-slate-400">Tháng:</strong> \${data.temporal.target_month}</div>` : ''}
        `;
      } else {
        tempDiv.innerHTML = '<p class="text-slate-500 italic">Không có mốc thời gian cụ thể</p>';
      }

      // Plan
      const planDiv = document.getElementById('planInfo');
      planDiv.innerHTML = `
        <div><strong class="text-slate-400">Ý định (Intent):</strong> <span class="text-indigo-400 font-mono">\${data.plan.intent}</span></div>
        <div><strong class="text-slate-400">Độ tin cậy:</strong> \${(data.plan.confidence * 100).toFixed(0)}%</div>
        \${data.plan.unanswerable_reason ? `<div class="text-amber-400 text-[11px] mt-1"><i class="fa-solid fa-circle-info"></i> \${data.plan.unanswerable_reason}</div>` : ''}
      `;

      // SQL
      document.getElementById('sqlCode').textContent = data.plan.sql || '-- Không có câu lệnh SQL (Truy vấn được xử lý đặc biệt hoặc từ chối)';
    }

    window.onload = init;
  </script>
</body>
</html>
"""
