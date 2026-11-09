import json
import urllib.request

USER = "luizoryone"
# USER ='pedrohpsantos'
REPO = "grupo-8-residencia/Fatura-Aberta"

print(f"\n🔔 === PAINEL DE NOTIFICAÇÕES:=== @{USER} ===\n")

# 1. PRs aguardando sua revisão
req_pr = urllib.request.Request(
    f"https://api.github.com/repos/{REPO}/pulls?state=open&per_page=100",
    headers={"User-Agent": "Python"},
)
with urllib.request.urlopen(req_pr) as resp:
    prs = json.loads(resp.read().decode())

meus_prs = [
    p for p in prs if USER in [r.get("login") for r in p.get("requested_reviewers", [])]
]
print(f"👉 PRs AGUARDANDO SUA REVISÃO ({len(meus_prs)}):")
for p in meus_prs:
    num = p["number"]
    title = p["title"]
    autor = p["user"]["login"]
    url = p["html_url"]
    print(f"  • PR #{num}: {title}")
    print(f"    Autor: @{autor} | Link: {url}")

# 2. Issues atribuídas a você
req_issues = urllib.request.Request(
    f"https://api.github.com/repos/{REPO}/issues?state=open&per_page=100",
    headers={"User-Agent": "Python"},
)
with urllib.request.urlopen(req_issues) as resp:
    issues = json.loads(resp.read().decode())

minhas_issues = [
    i
    for i in issues
    if "pull_request" not in i
    and any(a.get("login") == USER for a in i.get("assignees", []))
]
print(f"\n👉 ISSUES ATRIBUÍDAS A VOCÊ ({len(minhas_issues)}):")
for i in minhas_issues:
    num = i["number"]
    title = i["title"]
    labels = [lbl.get("name") for lbl in i.get("labels", [])]
    url = i["html_url"]
    print(f"  • Issue #{num}: {title}")
    print(f"    Labels: {labels} | Link: {url}")
