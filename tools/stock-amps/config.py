"""Local inputs only; generated artifacts must be outside the repository."""
from pathlib import Path
import os,hashlib
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(os.environ['MIGHTY_NAM_STOCK_WORK']).resolve()
BASE=Path(os.environ['MIGHTY_NAM_BASELINE']).resolve()
LOOP=Path(os.environ['MIGHTY_NAM_LOOP29']).resolve()
PAYLOAD=Path(os.environ['MIGHTY_NAM_STOCK_PAYLOAD']).resolve()
STOCK_FILE=Path(os.environ['MIGHTY_NAM_STOCK_FILE']).resolve()
TEST_BANK=Path(os.environ['MIGHTY_NAM_TEST_BANK']).resolve()
assert ROOT not in HERE.parents and HERE!=ROOT, 'Keep generated NUX-containing files outside the repository'
assert hashlib.sha256(PAYLOAD.read_bytes()).hexdigest()=='e971240a1e333003804cfd154e5ee053026254bbf09b11499e8b4968d3600752'
HERE.mkdir(parents=True,exist_ok=True)
