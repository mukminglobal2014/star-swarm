"""
═══════════════════════════════════════════════════════════════
  SHOOT TO THE STAR 🚀 — AUTONOMOUS FINAL
  Save as: star.py
═══════════════════════════════════════════════════════════════
"""
import os, sys, json, time, subprocess, sqlite3, hashlib, ctypes
from datetime import datetime

# Auto-install requests
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

BASE = os.path.dirname(os.path.abspath(__file__))
CFG  = os.path.join(BASE, "star_config.json")
DB   = os.path.join(BASE, "star.db")
LOCK = os.path.join(BASE, ".running")
TASK = "StarSwarm"
PY   = sys.executable

# ═══════════════════════════════════════════════════════════
#  AUTO-PASANG TASK SCHEDULER
# ═══════════════════════════════════════════════════════════
def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

def task_exist():
    r = subprocess.run(f'schtasks /query /tn "{TASK}"',
                       shell=True, capture_output=True, text=True)
    return r.returncode == 0

def install_task():
    pyw = PY.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pyw): pyw = PY
    script = os.path.join(BASE, "star.py")
    cmd = (f'schtasks /create /tn "{TASK}" '
           f'/tr "\'{pyw}\' \'{script}\'" '
           f'/sc minute /mo 5 /f /rl HIGHEST')
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode == 0, r.stderr

# ═══════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════
def load_cfg():
    if os.path.exists(CFG):
        try: return json.load(open(CFG, encoding="utf-8"))
        except: pass
    return {
        "api_key":   os.getenv("GROQ_API_KEY", ""),
        "destinasi": os.getenv("STAR_DESTINASI", "Bina content unik"),
        "agents":    int(os.getenv("STAR_AGENTS", "200")),
    }

def save_cfg(c):
    json.dump(c, open(CFG, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

cfg = load_cfg()
if not os.path.exists(CFG):
    save_cfg(cfg)

API_KEY   = cfg.get("api_key", "")
DESTINASI = cfg.get("destinasi", "Bina content unik")
PER_RUN   = cfg.get("agents", 200)
ROLES     = ["Planner","Research","Creative","Builder","Refiner","QC","Rebel","Verifier"]
DELAY     = 2.1
API_URL   = "https://api.groq.com/openai/v1/chat/completions"
MODEL     = "llama-3.3-70b-versatile"

if not API_KEY:
    print("❌ Edit star_config.json — paste GROQ_API_KEY. Run balik.")
    print("   Dapat free key: https://console.groq.com")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════
#  AUTO-PASANG CRON
# ═══════════════════════════════════════════════════════════
if not task_exist():
    print("🔧 Kali pertama — pasang auto-cron...")
    if not is_admin():
        print("⚠️  Naik taraf ke Administrator...")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", PY,
            f'"{os.path.abspath(__file__)}"', None, 1)
        sys.exit(0)
    ok, err = install_task()
    if ok:
        print(f"✅ Auto-cron dipasang: {TASK}")
        print("   Jalan setiap 5 minit, selamanya.")
        print(f"   Stop: schtasks /delete /tn {TASK} /f")
    else:
        print(f"❌ Gagal: {err}")
    print()

# ═══════════════════════════════════════════════════════════
#  LOCK — auto-clean lock lama
# ═══════════════════════════════════════════════════════════
if os.path.exists(LOCK):
    try:
        age = time.time() - os.path.getmtime(LOCK)
        if age < 600:
            print("⏸  Instance lain masih jalan. Skip.")
            sys.exit(0)
    except: pass
    try: os.remove(LOCK)
    except: pass

open(LOCK, "w").write(str(os.getpid()))

# ═══════════════════════════════════════════════════════════
#  DB
# ═══════════════════════════════════════════════════════════
conn = sqlite3.connect(DB, check_same_thread=False)
conn.executescript("""
CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT, role TEXT, content TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS ledger (id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, agent TEXT, action TEXT, hash TEXT, prev TEXT);
""")
conn.commit()

def ledger(agent, action):
    cur = conn.cursor()
    last = cur.execute("SELECT hash FROM ledger ORDER BY id DESC LIMIT 1").fetchone()
    prev = last[0] if last else "GENESIS"
    ts = datetime.now().isoformat()
    h = hashlib.sha256(f"{ts}{agent}{action}{prev}".encode()).hexdigest()[:10]
    cur.execute("INSERT INTO ledger (ts,agent,action,hash,prev) VALUES (?,?,?,?,?)",
                (ts, agent, action, h, prev))
    conn.commit()

def call_ai(system, prompt, max_tok=400, retry=3):
    for a in range(retry):
        try:
            r = requests.post(API_URL,
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={"model": MODEL, "messages": [
                    {"role":"system","content":system},
                    {"role":"user","content":prompt}],
                    "max_tokens": max_tok, "temperature": 0.9}, timeout=60)
            if r.status_code == 429:
                time.sleep(30); continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except:
            if a < retry-1: time.sleep(2); continue
            raise
    raise RuntimeError("gagal")

def run_agent(nama, role, task, ctx=""):
    try:
        out = call_ai(f"Kau {nama} ({role}). Destinasi: {DESTINASI}. Output unik.",
                      f"TASK: {task}\nKONTEKS: {ctx[:600]}", 400)
        conn.execute("INSERT INTO memory (agent,role,content,ts) VALUES (?,?,?,?)",
                     (nama, role, out[:400], datetime.now().isoformat()))
        conn.commit(); ledger(nama, "ok")
        return out
    except:
        ledger(nama, "err"); return None

# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════
def main():
    rows = conn.execute("SELECT content FROM memory ORDER BY id DESC LIMIT 3").fetchall()
    ctx = "\n".join(r[0] for r in rows) if rows else ""

    print(f"""
╔══════════════════════════════════════════════════════════╗
║  🚀 STAR — RUNNING                                       ║
║  Destinasi : {DESTINASI[:42]:<44}║
║  Agent     : {PER_RUN:<44}║
║  Stop      : Ctrl + C                                    ║
╚══════════════════════════════════════════════════════════╝
""")

    ledger("SWARM", "cycle")
    ok = 0
    for i in range(PER_RUN):
        role = ROLES[i % len(ROLES)]
        nama = f"{role[:4]}_{i:04d}"
        print(f"[{i+1:>4}/{PER_RUN}] {nama:<12} ", end="", flush=True)

        t0 = time.time()
        out = run_agent(nama, role, DESTINASI, ctx)
        took = time.time() - t0
        if took < DELAY: time.sleep(DELAY - took)

        if out:
            ok += 1; ctx = out[:600]
            print("✅")
        else:
            print("❌")

    mem = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
    led = conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]

    print(f"""
╔══════════════════════════════════════════════════════════╗
║  📊 CYCLE SELESAI                                        ║
║  OK     : {ok}/{PER_RUN}                                            ║
║  Memory : {mem}                                                 ║
║  Ledger : {led}                                                 ║
╚══════════════════════════════════════════════════════════╝
""")

    log = os.path.join(BASE, "star.log")
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} | OK {ok}/{PER_RUN} | Mem {mem} | Led {led}\n")

if __name__ == "__main__":
    try:
        main()
    finally:
        try: os.remove(LOCK)
        except: pass
