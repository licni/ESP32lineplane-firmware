# 版本流水號: r1 (2026-10-29) 依 manifest.json 建 GitHub Release:組完整燒錄檔,說明取 CHANGELOG 當版條目,同一天只留最新一版
# (和主專案 tools/publish_firmware.py 的 release()/prune_releases() 同一套規則;Release 已存在就更新說明與補檔案)
import hashlib
import json
import os
import re
import subprocess
import sys

FULL_PREFIX = "lineplane-full"
BOOT = os.path.join("firmware", "boot-0x0-0x10000.bin")   # 開機程式 + 分割表 + boot_app0,0x0~0x10000,各版相同(2026-10-29 比對 10.07.1 與 10.29.1)
VER_RE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})\.(\d+)$")


def run(cmd, check=True):
    print("  $", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        sys.exit(f"指令失敗:{' '.join(cmd)}")
    return r


def main():
    with open("manifest.json", encoding="utf-8") as f:
        man = json.load(f)
    ver = man["version"]
    m = VER_RE.match(ver)
    if not m:
        sys.exit(f"版本號格式不對:{ver}")
    with open(man["file"], "rb") as f:
        fw = f.read()
    if len(fw) != man["size"] or hashlib.sha256(fw).hexdigest() != man["sha256"]:
        sys.exit(f"{man['file']} 與 manifest.json 的大小/SHA-256 不符")
    with open(BOOT, "rb") as f:
        boot = f.read()
    if len(boot) != 0x10000:
        sys.exit(f"{BOOT} 要剛好 65536 位元組")
    os.makedirs("full", exist_ok=True)
    full = os.path.join("full", f"{FULL_PREFIX}-{ver}.bin")
    with open(full, "wb") as f:
        f.write(boot + fw)

    # 說明:CHANGELOG 當版條目(發布工具已把當天修改合併進去),沒有就用 manifest 的精簡說明
    day_text = man.get("notes", "")
    if os.path.exists("CHANGELOG.md"):
        with open("CHANGELOG.md", encoding="utf-8") as f:
            cm = re.search(r"(?ms)^## " + re.escape(ver) + r"[^\n]*\n(.*?)(?=^## |\Z)", f.read())
        if cm and cm.group(1).strip():
            day_text = cm.group(1).strip()
    body = (day_text + "\n\n---\n板子網頁「系統 → 韌體更新 → 檢查更新」即可更新.\n"
            "手動更新:下載下面的 firmware-版本.bin,到「手動上傳韌體檔」上傳(裝錯板子會被擋下).\n\n"
            f"全新開發板第一次燒錄:用 {FULL_PREFIX}-版本.bin 從位址 0x0 燒入整片(或用免安裝燒錄工具 LineplaneFlasher.exe),"
            "做法見專案首頁 README「全新開發板第一次燒錄」. 已在用的板子不要用這個檔,用上面的檢查更新.\n\n"
            "帶螢幕板(OLED)自 2026-10-29 起不再維護,停在 2026.10.07.1.")
    with open("notes.md", "w", encoding="utf-8", newline="\n") as f:
        f.write(body)

    tag = f"v{ver}"
    files = [man["file"], full]
    if run(["gh", "release", "view", tag], check=False).returncode == 0:
        run(["gh", "release", "edit", tag, "--title", f"韌體 {ver}", "--notes-file", "notes.md", "--latest"])
        run(["gh", "release", "upload", tag, *files, "--clobber"])
    else:
        run(["gh", "release", "create", tag, *files, "--title", f"韌體 {ver}", "--notes-file", "notes.md", "--latest"])

    # 每天只留最新一版:刪同一天序號較小的 Release 與 tag
    day, seq = ver.rsplit(".", 1)[0], int(m.group(4))
    r = run(["gh", "release", "list", "--limit", "200", "--json", "tagName"])
    for t in [x["tagName"] for x in json.loads(r.stdout or "[]")]:
        d = VER_RE.match(t[1:]) if t.startswith("v") else None
        if d and t[1:].rsplit(".", 1)[0] == day and int(d.group(4)) < seq:
            run(["gh", "release", "delete", t, "--yes", "--cleanup-tag"])
            print("  刪除同一天的舊版 Release", t)
    print(f"== Release {tag} 完成")


if __name__ == "__main__":
    main()
