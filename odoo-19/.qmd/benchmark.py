#!/usr/bin/env python3
"""
QMD vs Grep Benchmark Script
Usage: python3 .qmd/benchmark.py
"""
import subprocess, time, re, sys

COLLECTION = "odoo19-vault"
VAULT_PATH = "/Users/tri-mac/odoo-vaults/odoo-19"

CASES = [
    ("stock.quant model",         "stock quant",                    "stock.quant ORM"),
    ("api.depends decorator",      "api decorator odoo",            "@api.depends decorator"),
    ("ir.rule domain filter",     "security rule access",           "ir.rule security"),
    ("sale order workflow state", "sale order state",               "sale.order workflow"),
    ("Many2one relation field",   "relation field database",        "Many2one field relation"),
]

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True,
        cwd=VAULT_PATH,
        env={"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
             "HOME": "/Users/tri-mac"}).stdout

def grep_ms(query):
    t0 = time.time()
    out = run(f'grep -rl "{query}" . 2>/dev/null')
    ms = round((time.time()-t0)*1000, 1)
    hits = [l for l in out.strip().split("\n") if l.endswith(".md")]
    return ms, hits

def qmd_ms(query, mode="vsearch"):
    t0 = time.time()
    out = run(f"qmd {mode} {COLLECTION} '{query}' --limit 5 2>&1")
    ms = round((time.time()-t0)*1000, 1)
    # Filter only odoo19-vault results
    urls = re.findall(rf'qmd://{COLLECTION}/([^:#\s]+)', out)
    hits = list(dict.fromkeys(urls))
    return ms, hits

def warmup():
    print("Warming up QMD server...")
    run(f"qmd vsearch {COLLECTION} 'warmup' --limit 1 2>&1 > /dev/null")
    print("QMD ready.\n")

def run_benchmark():
    warmup()
    results = []

    for i,(query, semantic, label) in enumerate(CASES):
        g_ms,g_h = grep_ms(query)
        qv_ms,qv_h = qmd_ms(semantic,"vsearch")
        qq_ms,qq_h = qmd_ms(semantic,"query")
        results.append((label, g_ms, g_h, qv_ms, qv_h, qq_ms, qq_h))

    # Summary table
    n = len(results)
    # results = [(label, g_ms, g_h, qv_ms, qv_h, qq_ms, qq_h)]
    t_g = sum(r[1] for r in results)  # grep ms
    t_qv = sum(r[3] for r in results) # qmd-vector ms
    t_qq = sum(r[5] for r in results) # qmd-full ms
    n_g = sum(len(r[2]) for r in results)  # grep hits
    n_qv = sum(len(r[4]) for r in results) # qmd-vector hits
    n_qq = sum(len(r[6]) for r in results) # qmd-full hits

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║         BENCHMARK: QMD vs GREP — {n} Case (WARM)                   ║
╠══════════════════════════╦════════════════════╦════════════════════╦══════════════════╣
║        Case               ║        Grep         ║     QMD-vector      ║    QMD-full      ║
║                          ║  ms        Hasil   ║  ms         Hasil  ║  ms       Hasil  ║
╠══════════════════════════╬════════════════════╬════════════════════╬══════════════════╣""")

    for label,g_ms,g_h,qv_ms,qv_h,qq_ms,qq_h in results:
        print(f"║  {label:<24}║ {g_ms:>6.0f}    {len(g_h):<4}        ║ {qv_ms:>6.0f}     {len(qv_h):<4}        ║ {qq_ms:>7.0f}      {len(qq_h):<4}       ║")

    print(f"╠══════════════════════════╬════════════════════╬════════════════════╬══════════════════╣")
    print(f"║  RATA2                  ║ {t_g/n:>6.0f}              ║ {t_qv/n:>6.0f}              ║ {t_qq/n:>7.0f}              ║")
    print(f"║  TOTAL                  ║          {n_g:<4}        ║          {n_qv:<4}        ║          {n_qq:<4}              ║")
    print("╚══════════════════════════╩════════════════════╩════════════════════╩══════════════════╝")

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║  KESIMPULAN                                                       ║
╠══════════════════╦══════════════════╦══════════════════════════════╣
║                  ║  Speed (rata2)    ║  Hasil (total)            ║
╠══════════════════╬══════════════════╬══════════════════════════════╣
║  Grep            ║  ~{t_g/n:.0f}ms   (tercepat) ║  {n_g}  (exact match)          ║
║  QMD-vector      ║  ~{t_qv/n:.0f}ms              ║  {n_qv} (semantic)            ║
║  QMD-full        ║  ~{t_qq/n:.0f}ms              ║  {n_qq} (semantic + LLM rerank)║
╚══════════════════╩══════════════════╩══════════════════════════════╝
""")

if __name__ == "__main__":
    run_benchmark()
