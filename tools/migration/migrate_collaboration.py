"""Migration - Collaboration Objects (Annotations, Discussions) vers Power BI Comments"""
import json; from pathlib import Path
def gen_guide(output_dir: Path) -> str:
    path = output_dir / "COLLABORATION_MIGRATION_GUIDE.md"
    content = """# 💬 Guide Migration - Collaboration Objects vers Power BI Comments & Teams

**Date :** 13 février 2026

## 📋 Mapping

| Qlik | Power BI | Alternative |
|---|---|---|
| **Annotations** | Comments on visuals | Power BI comments |
| **Discussions** | Chat/threads | Teams channels |
| **Shared sheets** | Shared reports | Apps/workspaces |
| **Collaborative selection** | N/A | Shared bookmarks |

## 💬 Annotations → Power BI Comments

Power BI Service comments:
```
1. Open report
2. Click visual
3. "Start a comment"
4. Discussion thread on visual
```

Limitations:
- ❌ Can't resolve/close comments
- ✅ @mentions
- ✅ Real-time collab
- ✅ Notification

## 🗨️ Discussions → Microsoft Teams

Instead of Qlik discussions:
```
Teams Channel: #Sales-Analytics
├─ Thread: RevenueQ1 questions
├─ Thread: Dashboard improvement suggestions
└─ Pinned: Shared reports & links
```

## 📊 Community Sheets → Power BI Apps

```
Qlik: Community sheet (accessible tous)
↓
Power BI: App (published, shared workspace)
```

## 🚀 Steps

1. Audit annotations in Qlik
2. Plan Teams channels for discussions
3. Setup Power BI comment workflows
4. Communicate to users
5. Archive Qlik discussions

---

**Effort :** 1-2 semaines | **Complexité :** Basique
"""
    with open(path, 'w') as f: f.write(content)
    return str(path)

def main():
    output_dir = Path("output/collaboration")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ Collaboration: {gen_guide(output_dir)}")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
