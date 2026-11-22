import hashlib
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def test_fictional_brochure_to_rich_render(tmp_path):
    from tools.m7_scenario import run_scenario
    from core.workflow import read_json
    result=run_scenario(tmp_path)
    meta=read_json(result['bundle']/'manifest.json')
    assert not meta['horizontal_overflow'] and meta['font_loaded']
    assert result['summary']=={'facts':9,'highlights':4,'table_rows':4,'pending_claims':1}
    assert result['source'].is_file() and result['cropped'].is_file()
    source_hash=hashlib.sha256(result['source'].read_bytes()).hexdigest()
    assert source_hash==read_json(result['job']/'manifest.json')['image_processing'][0]['source_sha256']
