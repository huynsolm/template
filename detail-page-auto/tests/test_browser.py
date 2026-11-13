"""Browser tests write only into tmp_path, never into tracked documentation."""
import hashlib
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.make_screenshots import make_screenshots


def test_browser_local_flow_and_artifacts(tmp_path):
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'docs/images').glob('*.png')}
    result=make_screenshots(tmp_path/'work',tmp_path/'screenshots',tmp_path/'artifacts')
    assert result['same_version'] and result['steps']=='1-7'
    assert (tmp_path/'artifacts/approved.zip').is_file()
    assert len(list((tmp_path/'screenshots').glob('*.png')))==5
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'docs/images').glob('*.png')}
