"""
Kioxus — 桌面版入口
"""

import sys
import os
import threading
import time
import socket
import argparse
import logging

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    sys.path.insert(0, BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

logging.getLogger('werkzeug').setLevel(logging.WARNING)


def find_free_port(start=18080, end=18180):
    for port in range(start, end):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    raise RuntimeError("没有可用端口")


def create_app():
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(BASE_DIR) / ".env")

    from flask import Flask, request, jsonify, render_template_string
    from core_v2 import (
        Engine, LLMClient, get_llm_client,
        ProviderConfig, ModelRole,
        SessionManager, get_session_manager,
    )
    from memory_v2 import get_memory_store, get_search, get_tag_dictionary, MemoryRouter

    app = Flask(__name__)
    llm = get_llm_client()
    xiaomi_key = os.getenv("XIAOMI_TOKEN_PLAN_API_KEY", "")
    minimax_key = os.getenv("MINIMAX_API_KEY", "")

    if xiaomi_key:
        llm.register_provider(ProviderConfig(
            name="xiaomi",
            api_url="https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
            api_key=xiaomi_key,
            model="mimo-v2.5-pro",
            role=ModelRole.DEFAULT,
            max_tokens=2048,
            temperature=0.7,
        ))
    elif minimax_key:
        llm.register_provider(ProviderConfig(
            name="minimax",
            api_url="https://api.minimax.chat/v1/text/chatcompletion_v2",
            api_key=minimax_key,
            model="MiniMax-Text-01",
            role=ModelRole.DEFAULT,
            max_tokens=2048,
            temperature=0.7,
        ))
    else:
        llm.register_mock()

    session_mgr = get_session_manager(Path(BASE_DIR) / "data" / "sessions")
    session_mgr.get_or_create("main")
    store = get_memory_store()
    tags = get_tag_dictionary()
    search = get_search()
    memory_router = MemoryRouter(store, search, tags)
    engine = Engine(llm_client=llm, session_manager=session_mgr, memory_router=memory_router)

    @app.route("/")
    def index():
        return render_template_string(HTML)

    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        data = request.get_json()
        message = data.get("message", "").strip()
        if not message:
            return jsonify({"error": "空消息"}), 400
        try:
            reply = engine.process(message)
            return jsonify({"reply": reply, "turns": engine._turn_count})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/history")
    def api_history():
        return jsonify({"messages": session_mgr.get_recent_messages(50)})

    @app.route("/api/clear", methods=["POST"])
    def api_clear():
        session_mgr.current.messages.clear()
        session_mgr.save_session()
        return jsonify({"ok": True})

    @app.route("/api/config", methods=["GET"])
    def api_get_config():
        """读取当前Provider配置"""
        from core_v2.provider_registry import get_registry
        registry = get_registry()
        return jsonify(registry.get_status())

    @app.route("/api/config", methods=["POST"])
    def api_save_config():
        """保存Provider配置"""
        from core_v2.provider_registry import get_registry, ProviderConfig as RegProviderConfig
        from core_v2.config_watcher import validate_config
        registry = get_registry()

        data = request.get_json()
        provider = data.get("provider", "").strip()
        api_url = data.get("api_url", "").strip()
        api_key = data.get("api_key", "").strip()
        model = data.get("model", "").strip()

        if not all([provider, api_url, api_key, model]):
            return jsonify({"error": "所有字段都必填"}), 400

        # 保存到 .env
        env_path = Path(BASE_DIR).parent / ".env"
        env_var = f"{provider.upper()}_API_KEY"
        env_lines = []
        if env_path.exists():
            env_lines = env_path.read_text(encoding="utf-8").splitlines()
        found = False
        for i, line in enumerate(env_lines):
            if line.startswith(f"{env_var}="):
                env_lines[i] = f"{env_var}={api_key}"
                found = True
                break
        if not found:
            env_lines.append(f"{env_var}={api_key}")
        env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")

        os.environ[env_var] = api_key

        # 注册到ProviderRegistry
        registry.register(RegProviderConfig(
            name=provider,
            api_url=api_url,
            api_keys=[api_key],
            model=model,
            max_tokens=2048,
            temperature=0.7,
        ))
        registry.set_default(provider)
        cfg_path = str(Path(BASE_DIR).parent / "config" / "kioxus.json")
        registry.save_to_config(cfg_path)

        # 校验配置
        is_valid, errors = validate_config(cfg_path)
        if not is_valid:
            return jsonify({"error": "配置校验失败", "details": errors}), 400

        # 重新注册到LLM client
        llm.register_provider(ProviderConfig(
            name=provider,
            api_url=api_url,
            api_key=api_key,
            model=model,
            role=ModelRole.DEFAULT,
            max_tokens=2048,
            temperature=0.7,
        ))

        return jsonify({"ok": True, "provider": provider})

    # 启动配置热更新
    cfg_path = str(Path(BASE_DIR).parent / "config" / "kioxus.json")
    from core_v2.config_watcher import ConfigWatcher
    from core_v2.provider_registry import get_registry

    def on_config_change(path):
        registry = get_registry()
        registry.load_from_config(path)
        print(f"[ConfigWatcher] reloaded providers: {registry.list_providers()}")

    watcher = ConfigWatcher(cfg_path, on_config_change)
    watcher.start()

    return app


# ========== 内置HTML ==========
HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>Kioxus</title>
<style>
/* ===== 深色主题：黑金（鎏金） ===== */
:root{
  --bg:#0a0a0a;
  --surface:#111111;
  --surface2:#1a1a1a;
  --surface3:#222222;
  --border:#2a2a2a;
  --border2:#333333;
  --text:#f0ece2;
  --text2:#8a8578;
  --accent:#C69139;
  --accent2:#E2A83B;
  --accent-dim:rgba(198,145,57,.12);
  --green:#4ade80;
  --red:#ef4444;
  --user-bg:linear-gradient(135deg,#C69139,#8B6914);
  --bot-bg:#151515;
  --glow:rgba(198,145,57,.06);
  --radius:14px;
  --mono:'Cascadia Code','Fira Code','Consolas',monospace;
  --sans:-apple-system,'Segoe UI','Microsoft YaHei',sans-serif;
  --fs:14px;
  --shadow:0 2px 12px rgba(0,0,0,.4);
  --acrylic-bg:rgba(17,17,17,.65);
  --acrylic-blur:blur(24px) saturate(180%);
  --acrylic-border:rgba(255,255,255,.06);
}

/* ===== 浅色主题：白蓝 ===== */
[data-theme="light"]{
  --bg:#f7f9fc;
  --surface:#ffffff;
  --surface2:#f0f4f8;
  --surface3:#e8edf2;
  --border:#e2e8f0;
  --border2:#cbd5e1;
  --text:#1e293b;
  --text2:#64748b;
  --accent:#3b82f6;
  --accent2:#60a5fa;
  --accent-dim:rgba(59,130,246,.08);
  --green:#22c55e;
  --red:#ef4444;
  --user-bg:linear-gradient(135deg,#3b82f6,#2563eb);
  --bot-bg:#ffffff;
  --glow:rgba(59,130,246,.04);
  --shadow:0 2px 12px rgba(0,0,0,.06);
  --acrylic-bg:rgba(255,255,255,.72);
  --acrylic-blur:blur(24px) saturate(180%);
  --acrylic-border:rgba(0,0,0,.06);
}

*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--sans);background:var(--bg);color:var(--text);height:100vh;overflow:hidden;display:flex;flex-direction:column;font-size:var(--fs);-webkit-font-smoothing:antialiased}

/* ===== 标题栏 ===== */
.titlebar{height:40px;background:var(--acrylic-bg);-webkit-backdrop-filter:var(--acrylic-blur);backdrop-filter:var(--acrylic-blur);border-bottom:1px solid var(--acrylic-border);display:flex;align-items:center;padding:0 14px;flex-shrink:0;user-select:none;cursor:default;-webkit-app-region:drag}
.tb-logo{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;margin-right:10px}
.tb-title{font-size:13px;font-weight:600;color:var(--text);letter-spacing:.3px}
.tb-spacer{flex:1}
.tb-btn{width:38px;height:28px;border:none;background:transparent;color:var(--text2);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:14px;transition:all .15s;border-radius:6px;-webkit-app-region:no-drag}
.tb-btn:hover{background:var(--surface2);color:var(--text)}
.tb-btn.close:hover{background:var(--red);color:#fff}

/* ===== 主体 ===== */
.body{flex:1;display:flex;overflow:hidden}

/* ===== 侧边栏 ===== */
.sidebar{width:220px;background:var(--acrylic-bg);-webkit-backdrop-filter:var(--acrylic-blur);backdrop-filter:var(--acrylic-blur);border-right:1px solid var(--acrylic-border);display:flex;flex-direction:column;flex-shrink:0}
.sb-section{padding:18px 16px 8px;font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text2);font-weight:700}
.sb-item{padding:10px 14px;margin:2px 10px;border-radius:10px;cursor:pointer;font-size:13px;color:var(--text2);transition:all .2s;display:flex;align-items:center;gap:10px;font-weight:500}
.sb-item:hover{background:var(--accent-dim);color:var(--text)}
.sb-item.active{background:var(--accent-dim);color:var(--accent);font-weight:600}
.sb-item.active svg{stroke:var(--accent)}
.sb-item svg{width:16px;height:16px;flex-shrink:0;opacity:.7}
.sb-item:hover svg{opacity:1}
.sb-spacer{flex:1}
.sb-footer{padding:14px 16px;border-top:1px solid var(--border);font-size:11px;color:var(--text2);display:flex;align-items:center;gap:8px}
.sb-dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 6px rgba(74,222,128,.4)}

/* ===== 主区域 ===== */
.main{flex:1;display:flex;flex-direction:column;min-width:0;background:var(--bg)}
.messages{flex:1;overflow-y:auto;padding:24px 0}
.messages::-webkit-scrollbar{width:6px}
.messages::-webkit-scrollbar-track{background:transparent}
.messages::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
.messages::-webkit-scrollbar-thumb:hover{background:var(--text2)}
.wrap{width:100%;max-width:860px;margin:0 auto;padding:0 28px}

/* ===== 消息 ===== */
.msg{display:flex;gap:12px;margin-bottom:18px;animation:fadeIn .3s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.msg-user{flex-direction:row-reverse}
.avatar{width:32px;height:32px;border-radius:10px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;margin-top:2px}
.msg-bot .avatar{background:var(--surface2);border:1px solid var(--border);color:var(--accent)}
.msg-user .avatar{background:var(--accent-dim);color:var(--accent);border:1px solid transparent}
.bubble{max-width:82%;padding:12px 16px;border-radius:var(--radius);line-height:1.75;word-break:break-word;font-size:var(--fs)}
.msg-bot .bubble{background:var(--bot-bg);border:1px solid var(--border);border-bottom-left-radius:4px}
.msg-user .bubble{background:var(--user-bg);color:#fff;border-bottom-right-radius:4px;box-shadow:0 2px 8px rgba(0,0,0,.15)}
.bubble p{margin-bottom:8px}.bubble p:last-child{margin-bottom:0}
.bubble strong{color:var(--accent);font-weight:600}
.bubble code{background:var(--accent-dim);padding:2px 6px;border-radius:5px;font-family:var(--mono);font-size:.88em;color:var(--accent)}
.msg-user .bubble code{background:rgba(255,255,255,.2);color:#fff}
.bubble pre{background:var(--surface);border:1px solid var(--border);border-radius:12px;margin:10px 0;overflow:hidden;position:relative}
.bubble pre code{display:block;padding:14px 16px;overflow-x:auto;font-size:.86em;line-height:1.65;background:none;color:var(--text)}
.bubble pre .copy-btn{position:absolute;top:8px;right:8px;background:var(--surface2);border:1px solid var(--border);color:var(--text2);padding:4px 10px;border-radius:6px;font-size:10px;cursor:pointer;opacity:0;transition:all .15s}
.bubble pre:hover .copy-btn{opacity:1}
.bubble pre .copy-btn:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
.bubble ul,.bubble ol{padding-left:20px;margin:8px 0}
.bubble li{margin-bottom:4px}
.msg-sys{justify-content:center;margin:12px 0}
.msg-sys .bubble{background:none;border:none;color:var(--text2);font-size:11px;padding:4px 12px;max-width:none}
.typing{display:flex;gap:5px;padding:4px 0}
.typing span{width:6px;height:6px;border-radius:50%;background:var(--accent);opacity:.5;animation:bounce .6s ease-in-out infinite}
.typing span:nth-child(2){animation-delay:.15s}.typing span:nth-child(3){animation-delay:.3s}
@keyframes bounce{0%,100%{transform:translateY(0);opacity:.5}50%{transform:translateY(-5px);opacity:1}}

/* ===== 输入区 ===== */
.input-area{padding:12px 20px 16px;background:var(--acrylic-bg);-webkit-backdrop-filter:var(--acrylic-blur);backdrop-filter:var(--acrylic-blur);border-top:1px solid var(--acrylic-border);flex-shrink:0}
.input-wrap{width:100%;max-width:860px;margin:0 auto;display:flex;gap:10px;align-items:flex-end}
.input-box{flex:1;background:var(--surface2);border:1px solid var(--border);border-radius:14px;padding:10px 14px;display:flex;align-items:flex-end;gap:6px;transition:all .25s}
.input-box:focus-within{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-dim)}
.input-box textarea{flex:1;background:none;border:none;color:var(--text);font-size:var(--fs);font-family:var(--sans);resize:none;outline:none;line-height:1.5;max-height:120px;min-height:22px}
.input-box textarea::placeholder{color:var(--text2)}
.send-btn{width:38px;height:38px;border-radius:12px;border:none;background:var(--accent);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s;flex-shrink:0;box-shadow:0 2px 8px var(--accent-dim)}
.send-btn:hover{transform:scale(1.06);filter:brightness(1.1)}
.send-btn:disabled{background:var(--border);color:var(--text2);cursor:default;transform:none;box-shadow:none}
.send-btn svg{width:17px;height:17px}
.status-bar{width:100%;max-width:860px;margin:6px auto 0;padding:0 28px;display:flex;justify-content:space-between;font-size:10px;color:var(--text2)}

/* ===== 欢迎 ===== */
.welcome{text-align:center;padding:100px 20px 50px;color:var(--text2)}
.welcome .logo-big{width:60px;height:60px;border-radius:16px;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;font-weight:800;font-size:24px;color:#fff;margin:0 auto 18px;box-shadow:0 4px 24px var(--accent-dim)}
.welcome h2{font-size:20px;color:var(--text);margin-bottom:8px;font-weight:700;letter-spacing:.5px}
.welcome p{font-size:13px;line-height:1.7;max-width:360px;margin:0 auto}

/* ===== 设置 ===== */
.settings-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.4);-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);z-index:100;align-items:center;justify-content:center}
.settings-overlay.show{display:flex}
.settings-panel{background:var(--acrylic-bg);-webkit-backdrop-filter:var(--acrylic-blur);backdrop-filter:var(--acrylic-blur);border:1px solid var(--acrylic-border);border-radius:18px;width:460px;max-height:80vh;overflow-y:auto;box-shadow:0 24px 64px rgba(0,0,0,.5)}
.sp-header{padding:20px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
.sp-header h3{font-size:16px;font-weight:700}
.sp-close{width:30px;height:30px;border-radius:8px;border:none;background:transparent;color:var(--text2);cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center;transition:all .15s}
.sp-close:hover{background:var(--surface2);color:var(--text)}
.sp-body{padding:20px 24px}
.sp-group{margin-bottom:22px}.sp-group:last-child{margin-bottom:0}
.sp-label{font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text2);margin-bottom:10px;font-weight:700}
.sp-row{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.sp-row label{font-size:13px;color:var(--text);min-width:60px;font-weight:500}
.sp-btn{padding:7px 16px;border-radius:10px;border:1px solid var(--border);background:var(--surface2);color:var(--text);font-size:12px;cursor:pointer;transition:all .2s;font-weight:500}
.sp-btn:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
.sp-btn-group{display:flex;gap:8px;flex-wrap:wrap}.sp-btn-group .sp-btn{flex:1;text-align:center}
.sp-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 2px 8px var(--accent-dim)}
.sp-btn.danger{border-color:var(--red);color:var(--red)}.sp-btn.danger:hover{background:var(--red);color:#fff}
.sp-hint{font-size:11px;color:var(--text2);margin-top:4px;line-height:1.5}
.sp-divider{height:1px;background:var(--border);margin:18px 0}
.sp-about{text-align:center;padding:10px 0}
.sp-about .logo-sm{width:40px;height:40px;border-radius:12px;background:linear-gradient(135deg,var(--accent),var(--accent2));display:inline-flex;align-items:center;justify-content:center;font-weight:800;font-size:16px;color:#fff;margin-bottom:10px;box-shadow:0 2px 12px var(--accent-dim)}
.sp-about p{font-size:12px;color:var(--text2);line-height:1.7}
.sp-about .version{font-size:11px;color:var(--text2);margin-top:6px;opacity:.7}
.sp-toast{position:fixed;bottom:30px;left:50%;transform:translateX(-50%);background:var(--accent);color:#fff;padding:10px 24px;border-radius:10px;font-size:13px;z-index:200;opacity:0;transition:opacity .3s;pointer-events:none;font-weight:500;box-shadow:0 4px 16px var(--accent-dim)}
.sp-toast.show{opacity:1}
[data-fontsize="small"]{--fs:13px}[data-fontsize="large"]{--fs:16px}
</style>
</head>
<body>

<div class="titlebar" id="titlebar">
  <div class="tb-logo"><img src="data:image/png;base64,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" style="width:22px;height:22px;border-radius:6px;"></div>
  <div class="tb-title">Kioxus</div>
  <div class="tb-spacer"></div>
  <button class="tb-btn" id="btn-min" title="最小化">─</button>
  <button class="tb-btn" id="btn-max" title="最大化">□</button>
  <button class="tb-btn close" id="btn-close" title="关闭">✕</button>
</div>

<div class="body">
  <aside class="sidebar">
    <div class="sb-section">对话</div>
    <div class="sb-item active">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      对话
    </div>
    <div class="sb-section">设置</div>
    <div class="sb-item" onclick="openSettings()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
      设置
    </div>
    <div class="sb-spacer"></div>
    <div class="sb-footer"><div class="sb-dot"></div><span>就绪</span></div>
  </aside>

  <div class="main">
    <div class="messages" id="messages">
      <div class="wrap" id="msg-wrap">
        <div class="welcome" id="welcome">
          <div class="logo-big"><img src="data:image/png;base64,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" style="width:60px;height:60px;border-radius:16px;"></div>
          <h2>Kioxus</h2>
          <p>输入消息开始对话</p>
        </div>
      </div>
    </div>
    <div class="input-area">
      <div class="input-wrap">
        <div class="input-box">
          <textarea id="input" placeholder="说点什么..." rows="1"></textarea>
        </div>
        <button class="send-btn" id="send-btn" onclick="send()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
      <div class="status-bar"><span id="st-text">就绪</span><span id="st-turns">0 轮</span></div>
    </div>
  </div>
</div>

<div class="settings-overlay" id="settings-overlay" onclick="if(event.target===this)closeSettings()">
  <div class="settings-panel">
    <div class="sp-header"><h3>设置</h3><button class="sp-close" onclick="closeSettings()">✕</button></div>
    <div class="sp-body">
      <div class="sp-group">
        <div class="sp-label">外观</div>
        <div class="sp-row"><label>主题</label><div class="sp-btn-group" id="theme-btns"><button class="sp-btn active" data-val="dark" onclick="setTheme('dark')">深色</button><button class="sp-btn" data-val="light" onclick="setTheme('light')">浅色</button></div></div>
        <div class="sp-row"><label>字号</label><div class="sp-btn-group" id="font-btns"><button class="sp-btn" data-val="small" onclick="setFontSize('small')">小</button><button class="sp-btn active" data-val="medium" onclick="setFontSize('medium')">中</button><button class="sp-btn" data-val="large" onclick="setFontSize('large')">大</button></div></div>
      </div>
      <div class="sp-divider"></div>
      <div class="sp-group">
        <div class="sp-label">LLM 配置</div>
        <div class="sp-hint" style="margin-bottom:12px">配置API密钥后即可使用，支持任意标准API</div>
        <div class="sp-row"><label>Provider</label><input type="text" id="cfg-provider" placeholder="如 xiaomi / openai / custom" style="flex:1;padding:6px 10px;border-radius:8px;border:1px solid var(--border);background:var(--surface2);color:var(--text);font-size:13px;"></div>
        <div class="sp-row"><label>API URL</label><input type="text" id="cfg-url" placeholder="https://api.openai.com/v1/chat/completions" style="flex:1;padding:6px 10px;border-radius:8px;border:1px solid var(--border);background:var(--surface2);color:var(--text);font-size:13px;"></div>
        <div class="sp-row"><label>API Key</label><input type="password" id="cfg-key" placeholder="sk-..." style="flex:1;padding:6px 10px;border-radius:8px;border:1px solid var(--border);background:var(--surface2);color:var(--text);font-size:13px;"></div>
        <div class="sp-row"><label>Model</label><input type="text" id="cfg-model" placeholder="gpt-4o" style="flex:1;padding:6px 10px;border-radius:8px;border:1px solid var(--border);background:var(--surface2);color:var(--text);font-size:13px;"></div>
        <div class="sp-row"><button class="sp-btn" onclick="saveConfig()" style="background:var(--accent);color:#fff;border-color:var(--accent)">保存配置</button><button class="sp-btn" onclick="testConfig()">测试连接</button></div>
        <div class="sp-hint" id="cfg-status"></div>
      </div>
      <div class="sp-divider"></div>
      <div class="sp-group">
        <div class="sp-label">数据</div>
        <div class="sp-row"><button class="sp-btn danger" onclick="clearChat()">清空对话记录</button></div>
      </div>
      <div class="sp-divider"></div>
      <div class="sp-group sp-about">
        <div class="logo-sm"><img src="data:image/png;base64,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" style="width:40px;height:40px;border-radius:12px;"></div>
        <p>Kioxus — 自主Agent框架<br>对抗性验证 · 硬边界隔离 · 可量化上下文</p>
        <div class="version">v2.0</div>
      </div>
    </div>
  </div>
</div>
<div class="sp-toast" id="toast"></div>

<script>
const $=s=>document.querySelector(s),msgWrap=$('#msg-wrap'),messages=$('#messages'),input=$('#input'),sendBtn=$('#send-btn');
let turns=0,sending=false,welcomeShown=true,isMax=false,api=null;

// ===== 窗口控制（等 pywebview 注入完成后初始化）=====
window.addEventListener('pywebviewready',function(){
  api=window.pywebview.api;

  $('#btn-min').addEventListener('click',()=>api.minimize());
  $('#btn-max').addEventListener('click',()=>{api.toggle_max();isMax=!isMax;updateMaxBtn()});
  $('#btn-close').addEventListener('click',()=>api.close());

  // ===== 自定义拖拽：最大化时不可拖动 =====
  let dragging=false,dragOffX=0,dragOffY=0;

  $('#titlebar').addEventListener('mousedown',async(e)=>{
    if(e.target.closest('.tb-btn'))return;
    if(isMax)return;
    dragging=true;
    const pos=await api.get_position();
    if(!pos)return;
    dragOffX=e.screenX-pos.x;
    dragOffY=e.screenY-pos.y;
    e.preventDefault();
  });

  document.addEventListener('mousemove',async(e)=>{
    if(!dragging)return;
    const newX=e.screenX-dragOffX;
    const newY=e.screenY-dragOffY;
    await api.set_position(newX,newY);
  });

  document.addEventListener('mouseup',()=>{dragging=false});
});

function updateMaxBtn(){
  const btn=$('#btn-max');
  if(isMax){btn.textContent='❐';btn.title='还原'}
  else{btn.textContent='□';btn.title='最大化'}
}

// ===== 设置 =====
(function(){const t=localStorage.getItem('kx_theme')||'dark',f=localStorage.getItem('kx_fontsize')||'medium';applyTheme(t);applyFontSize(f);document.querySelectorAll('#theme-btns .sp-btn').forEach(b=>b.classList.toggle('active',b.dataset.val===t));document.querySelectorAll('#font-btns .sp-btn').forEach(b=>b.classList.toggle('active',b.dataset.val===f))})();

function applyTheme(t){document.documentElement.setAttribute('data-theme',t)}
function applyFontSize(f){document.documentElement.setAttribute('data-fontsize',f)}
function setTheme(t){localStorage.setItem('kx_theme',t);applyTheme(t);document.querySelectorAll('#theme-btns .sp-btn').forEach(b=>b.classList.toggle('active',b.dataset.val===t));showToast('主题已切换')}
function setFontSize(f){localStorage.setItem('kx_fontsize',f);applyFontSize(f);document.querySelectorAll('#font-btns .sp-btn').forEach(b=>b.classList.toggle('active',b.dataset.val===f));showToast('字号已调整')}
function openSettings(){$('#settings-overlay').classList.add('show')}
function closeSettings(){$('#settings-overlay').classList.remove('show')}
function showToast(m){const t=$('#toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),1800)}

// ===== API配置 =====
async function loadConfig(){
  try{
    const r=await fetch('/api/config');
    const d=await r.json();
    const ps=d.providers||{};
    const names=Object.keys(ps);
    if(names.length>0){
      const first=names[0];
      const p=ps[first];
      $('#cfg-provider').value=first;
      $('#cfg-url').value=p.api_url||'';
      $('#cfg-model').value=p.model||'';
      if(p.has_key)$('#cfg-status').textContent='已配置: '+first+' ('+p.api_key_masked+')';
    }
  }catch(e){}
}

async function saveConfig(){
  const provider=$('#cfg-provider').value.trim();
  const url=$('#cfg-url').value.trim();
  const key=$('#cfg-key').value.trim();
  const model=$('#cfg-model').value.trim();
  if(!provider||!url||!key||!model){showToast('请填写所有字段');return}
  try{
    const r=await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider,api_url:url,api_key:key,model})});
    const d=await r.json();
    if(d.ok){showToast('配置已保存');$('#cfg-key').value='';loadConfig()}
    else showToast('错误: '+(d.error||'未知'))
  }catch(e){showToast('保存失败: '+e.message)}
}

async function testConfig(){
  const status=$('#cfg-status');
  status.textContent='测试中...';
  try{
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:'你好，请回复OK'})});
    const d=await r.json();
    if(d.error){status.textContent='连接失败: '+d.error;status.style.color='var(--red)'}
    else{status.textContent='连接成功! 回复: '+d.reply.substring(0,50);status.style.color='var(--accent)'}
  }catch(e){status.textContent='网络错误: '+e.message;status.style.color='var(--red)'}
}

// 打开设置时加载配置
function openSettings(){loadConfig();$('#settings-overlay').classList.add('show')}
async function clearChat(){if(!confirm('确定清空？'))return;try{await fetch('/api/clear',{method:'POST'});msgWrap.innerHTML='<div class="welcome" id="welcome"><div class="logo-big"><img src="data:image/png;base64,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" style="width:60px;height:60px;border-radius:16px;"></div><h2>Kioxus</h2><p>输入消息开始对话</p></div>';welcomeShown=true;turns=0;$('#st-turns').textContent='0 轮';showToast('已清空')}catch(e){showToast('失败')}}

// ===== 消息 =====
input.addEventListener('input',()=>{input.style.height='auto';input.style.height=Math.min(input.scrollHeight,120)+'px'});
input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});
function removeWelcome(){if(welcomeShown){const w=$('#welcome');if(w)w.remove();welcomeShown=false}}
function addMsg(text,role){removeWelcome();const d=document.createElement('div');d.className='msg msg-'+role;const av=document.createElement('div');av.className='avatar';av.textContent=role==='bot'?'甲':'你';const b=document.createElement('div');b.className='bubble';if(role==='bot')b.innerHTML=render(text);else b.textContent=text;d.append(av,b);msgWrap.appendChild(d);messages.scrollTop=messages.scrollHeight}
function addLoading(){const d=document.createElement('div');d.className='msg msg-bot';d.innerHTML='<div class="avatar">甲</div><div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>';msgWrap.appendChild(d);messages.scrollTop=messages.scrollHeight;return d}
function render(t){t=t.replace(/```(\w*)\n([\s\S]*?)```/g,(m,l,c)=>'<pre><button class="copy-btn" onclick="copyCode(this)">复制</button><code>'+c.replace(/</g,'&lt;')+'</code></pre>');t=t.replace(/`([^`]+)`/g,'<code>$1</code>');t=t.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');t=t.replace(/\*(.+?)\*/g,'<em>$1</em>');t=t.replace(/^- (.+)$/gm,'<li>$1</li>');t=t.replace(/(<li>.*<\/li>)/gs,'<ul>$1</ul>');t=t.replace(/\n\n/g,'</p><p>');return'<p>'+t+'</p>'}
function copyCode(btn){navigator.clipboard.writeText(btn.nextElementSibling.textContent);btn.textContent='已复制';setTimeout(()=>btn.textContent='复制',1500)}
async function send(){const text=input.value.trim();if(!text||sending)return;sending=true;sendBtn.disabled=true;input.value='';input.style.height='auto';addMsg(text,'user');turns++;$('#st-turns').textContent=turns+' 轮';const l=addLoading();$('#st-text').textContent='思考中...';try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});const d=await r.json();l.remove();if(d.error)addMsg('[错误] '+d.error,'bot');else addMsg(d.reply,'bot')}catch(e){l.remove();addMsg('[网络错误] '+e.message,'bot')}sending=false;sendBtn.disabled=false;$('#st-text').textContent='就绪';input.focus()}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeSettings()});
window.onload=()=>{input.focus()};
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    if not args.dev:
        logging.disable(logging.INFO)

    port = args.port or find_free_port()
    app = create_app()

    threading.Thread(
        target=lambda: app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False),
        daemon=True,
    ).start()

    for _ in range(30):
        try:
            import urllib.request
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
            break
        except Exception:
            time.sleep(0.3)
    else:
        sys.exit(1)

    import webview

    class Api:
        def __init__(self):
            self._win = None
        def set_win(self, w):
            self._win = w
        def minimize(self):
            if self._win: self._win.minimize()
        def toggle_max(self):
            if self._win:
                if self._win._is_maximized:
                    self._win.restore()
                    self._win._is_maximized = False
                else:
                    self._win.maximize()
                    self._win._is_maximized = True
        def close(self):
            if self._win: self._win.destroy()
        def get_position(self):
            if self._win:
                return {"x": self._win.x, "y": self._win.y}
            return {"x": 0, "y": 0}
        def set_position(self, x, y):
            if self._win: self._win.move(int(x), int(y))

    api = Api()

    # 图标通过 PyInstaller --icon 参数设置
    icon_path = os.path.join(BASE_DIR, 'logo.ico') if os.path.exists(os.path.join(BASE_DIR, 'logo.ico')) else None

    window = webview.create_window(
        title="Kioxus",
        url=f"http://127.0.0.1:{port}/?v={int(time.time())}",
        width=1000, height=700,
        min_size=(600, 400),
        frameless=True,
        easy_drag=False,
        js_api=api,
    )
    window._is_maximized = False
    api.set_win(window)

    webview.start(debug=args.dev)


if __name__ == "__main__":
    main()
