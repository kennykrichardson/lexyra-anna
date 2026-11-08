#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXECUTA_DIR="$ROOT/executas/lexyra-writer"
cd "$EXECUTA_DIR"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "Build must run on Linux x86_64 (found $(uname -s) $(uname -m))." >&2
  exit 2
fi

python -m PyInstaller --clean --noconfirm --onefile --name lexyra-writer \
  --distpath "$EXECUTA_DIR/dist/build" \
  "$EXECUTA_DIR/lexyra_writer_plugin.py"

PACKAGE="$EXECUTA_DIR/dist/lexyra-writer-linux-x86_64.tar.gz"
STAGE="$EXECUTA_DIR/dist/package"
rm -rf "$STAGE"
mkdir -p "$STAGE"
install -m 755 "$EXECUTA_DIR/dist/build/lexyra-writer" "$STAGE/lexyra-writer"
tar -C "$STAGE" -czf "$PACKAGE" lexyra-writer

VERIFY="$EXECUTA_DIR/dist/verify"
rm -rf "$VERIFY"
mkdir -p "$VERIFY"
tar -xzf "$PACKAGE" -C "$VERIFY"
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"describe"}' | \
  "$VERIFY/lexyra-writer" > "$VERIFY/describe.jsonl"
python - "$VERIFY/describe.jsonl" <<'PY'
import json, sys
frame = json.loads(open(sys.argv[1], encoding="utf-8").readline())
assert frame.get("jsonrpc") == "2.0" and frame.get("id") == 1
assert "enhance" in [tool["name"] for tool in frame["result"]["tools"]]
print("Packaged Linux x86_64 Executa describe handshake passed.")
PY
python "$ROOT/scripts/smoke-linux-binary.py" "$VERIFY/lexyra-writer"
file "$VERIFY/lexyra-writer" | grep -E 'ELF 64-bit.*x86-64'
test -x "$VERIFY/lexyra-writer"
test "$(tar -tzf "$PACKAGE")" = "lexyra-writer"
sha256sum "$PACKAGE"
echo "Created $PACKAGE"
