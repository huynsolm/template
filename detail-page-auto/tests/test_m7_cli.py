import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run([sys.executable,str(ROOT/'cli.py'),*map(str,args)],cwd=ROOT,capture_output=True,text=True)


def test_extract_cli_roundtrip_and_fix_prompt(tmp_path):
    prompt=run('extract','prompt','--output',tmp_path)
    assert prompt.returncode==0 and (tmp_path/'extract-prompt.md').is_file()
    result=run('extract','ingest','--answer',ROOT/'samples/extract-answer.txt','--output',tmp_path/'facts.json')
    assert result.returncode==0,result.stderr
    facts=json.loads((tmp_path/'facts.json').read_text())
    assert len(facts['pending_claims'])==1 and facts['product']['price']==''
    assert len(facts['facts'])==9
    invalid=tmp_path/'bad.txt'
    invalid.write_text('{"unknown":true}')
    result=run('extract','ingest','--answer',invalid,'--output',tmp_path/'failed.json')
    assert result.returncode!=0 and (tmp_path/'fix-extract-prompt.md').is_file()
    assert not (tmp_path/'failed.json').exists()


@pytest.mark.parametrize('data',[[],{'product':None},{'product':{},'images':[None]},
                                 {'product':{'name':'','price':''},'images':[]}])
def test_prompt_cli_required_inputs_fail_cleanly(tmp_path,data):
    path=tmp_path/'facts.json'
    path.write_text(json.dumps(data))
    result=run('prompt','--facts',path,'--images',ROOT/'samples','--output',tmp_path/'out')
    assert result.returncode!=0 and 'Traceback' not in result.stderr and '필수' in result.stderr
    assert not (tmp_path/'out').exists()
