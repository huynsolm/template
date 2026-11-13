import hashlib
import sys
import pytest
from PIL import Image
from core.background import available, get_remover, RemBgRemover, MODEL_NAME, MODEL_MD5


def test_optional_discovery_does_not_import_model(monkeypatch):
    monkeypatch.setattr('core.background.importlib.util.find_spec',lambda name: None)
    assert available() is False
    assert 'rembg' not in sys.modules


def test_model_constants_and_lazy_construction(tmp_path):
    remover=get_remover(tmp_path)
    assert isinstance(remover,RemBgRemover)
    assert MODEL_NAME=='u2netp'
    assert MODEL_MD5=='8e83ca70e441ab06c318d82300c84806'
    assert not tmp_path.exists() or not list(tmp_path.iterdir())


def test_existing_corrupt_model_rejected(tmp_path):
    model=tmp_path/'u2netp'; model.mkdir(); (model/'u2netp.onnx').write_bytes(b'corrupt')
    with pytest.raises(RuntimeError,match='checksum'):
        get_remover(tmp_path).remove(Image.new('RGB',(10,10)))


def test_checksum_bypass_rejected(tmp_path,monkeypatch):
    monkeypatch.setenv('MODEL_CHECKSUM_DISABLED','1')
    with pytest.raises(RuntimeError,match='CHECKSUM'):
        get_remover(tmp_path).remove(Image.new('RGB',(10,10)))


def test_empty_checksum_bypass_rejected(tmp_path,monkeypatch):
    monkeypatch.setenv('MODEL_CHECKSUM_DISABLED','')
    with pytest.raises(RuntimeError,match='CHECKSUM'):
        get_remover(tmp_path).remove(Image.new('RGB',(10,10)))


def test_nested_model_layout_checked(tmp_path):
    model=tmp_path/'models'/'u2netp'; model.mkdir(parents=True); (model/'u2netp.onnx').write_bytes(b'corrupt')
    with pytest.raises(RuntimeError,match='checksum'):
        get_remover(tmp_path).remove(Image.new('RGB',(10,10)))


def test_session_is_cpu_only_and_environment_is_restored(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import os
    import core.background as background
    sessions=[]
    telemetry=[]
    class Options:
        pass
    def new_session(name,*,sess_opts,providers):
        assert name=='u2netp'
        assert providers==['CPUExecutionProvider']
        assert sess_opts.intra_op_num_threads==sess_opts.inter_op_num_threads==2
        assert os.environ['U2NET_HOME']==str(tmp_path)
        target=tmp_path/'models'/'u2netp'/'u2netp.onnx'
        target.parent.mkdir(parents=True); target.write_bytes(b'fake test model')
        session=object(); sessions.append(session); return session
    monkeypatch.setattr(background,'available',lambda:True)
    monkeypatch.setattr(background,'verify_model',lambda path: None)
    monkeypatch.setitem(sys.modules,'rembg',SimpleNamespace(new_session=new_session,remove=lambda image,session:image))
    monkeypatch.setitem(sys.modules,'onnxruntime',SimpleNamespace(SessionOptions=Options,disable_telemetry_events=lambda:telemetry.append('disabled')))
    monkeypatch.setenv('U2NET_HOME','previous-home')
    remover=get_remover(tmp_path)
    assert remover.remove(Image.new('RGB',(10,10))).mode=='RGBA'
    assert remover.remove(Image.new('RGB',(10,10))).mode=='RGBA'
    assert len(sessions)==1
    assert telemetry
    assert os.environ['U2NET_HOME']=='previous-home'


def test_bg_check_missing_dependency_is_explicit_failure(monkeypatch,capsys):
    from tools import bg_check
    monkeypatch.setattr(bg_check,'available',lambda:False)
    assert bg_check.main([])==1
    assert 'FAILED' in capsys.readouterr().err
