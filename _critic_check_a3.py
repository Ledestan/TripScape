import sys, yaml, json
from collections import defaultdict

p = "docs/competition/A3-service-blueprint.yaml"
d = yaml.safe_load(open(p, encoding="utf-8"))

nodes = {n["id"]: n for n in d["nodes"]}
ids = set(nodes)
print("node ids:", sorted(ids))
print("counts:", {k: len(v) for k, v in d["lines"].__class__ and [(l["id"], l["stations"]) for l in d["lines"]]} if False else "")

# 1. next targets exist
issues = []
for nid, n in nodes.items():
    for t in n.get("next") or []:
        if t not in ids:
            issues.append(f"next target missing: {nid} -> {t}")

hubs = {h["id"]: h for h in d["interchanges"]}
allids = set(ids) | set(hubs)
for nid, n in nodes.items():
    for t in n.get("next") or []:
        if t not in allids:
            issues.append(f"next target missing(incl hubs): {nid} -> {t}")

for h in d["interchanges"]:
    hid = h["id"]
    # who actually points at hub
    actual = sorted(nid for nid, n in nodes.items() if hid in (n.get("next") or []))
    declared = sorted(h["incoming"])
    if actual != declared:
        issues.append(f"HUB {hid}: incoming declared {declared} != actual next {actual}")
    for o in h.get("outgoing") or []:
        if o not in allids:
            issues.append(f"HUB {hid} outgoing missing: {o}")

# feedback_edges / constraint_links targets
for e in d["feedback_edges"]:
    for k in ("from", "to"):
        if e[k] not in allids:
            issues.append(f"feedback target missing: {e}")

# lines: station ids exist, belong to that line
line_of = {}
for l in d["lines"]:
    for s in l["stations"]:
        if s not in ids:
            issues.append(f"line {l['id']} station missing node: {s}")
        else:
            line_of[s] = l["id"]
for nid, n in nodes.items():
    if line_of.get(nid) != n["line"]:
        issues.append(f"line mismatch: node {nid} line={n['line']} but in lines[] {line_of.get(nid)}")

# 2. same-line next edges
for nid, n in nodes.items():
    for t in n.get("next") or []:
        if t in nodes and line_of.get(t) == n["line"]:
            issues.append(f"SAME-LINE next (violates edge_semantics): {nid}({n['line']}) -> {t}")

# 3. stage monotonic per line
for l in d["lines"]:
    st = [(s, nodes[s]["stage_order"]) for s in l["stations"] if s in nodes]
    inc = all(st[i][1] <= st[i+1][1] for i in range(len(st)-1))
    print(f"line {l['id']} stages:", st, "monotonic:", inc)
    if not inc:
        issues.append(f"line {l['id']} not monotonic")

# 4. feedback_edges decreasing stage
st = {nid: n["stage_order"] for nid, n in nodes.items()}
for h in d["interchanges"]:
    st[h["id"]] = h["stage_order"]
for e in d["feedback_edges"]:
    a, b = st[e["from"]], st[e["to"]]
    ok = a > b
    print(f"feedback {e['from']}({a}) -> {e['to']}({b}) decreasing={ok}")
    if not ok:
        issues.append(f"feedback edge not decreasing: {e['from']}({a})->{e['to']}({b})")

for e in d["constraint_links"]:
    for k in ("from", "to"):
        if e[k] not in allids:
            issues.append(f"constraint target missing: {e}")
    a, b = st[e["from"]], st[e["to"]]
    if a != b:
        issues.append(f"constraint_link cross-stage (should be equal stage): {e['from']}({a})->{e['to']}({b})")

# lanes
for nid, n in nodes.items():
    print(nid, n["node"] if "node" in n else "", n["line"], n["lane"], n["stage_order"], "next=", n.get("next"))

print("\n=== ISSUES ===")
for i in issues:
    print(" -", i)
print("total issues:", len(issues))
