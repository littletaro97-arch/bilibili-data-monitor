from pathlib import Path
import sys
import os
import pytest
from types import SimpleNamespace
from app import launcher

def test_missing_gui_streams_initialized_for_uvicorn(tmp_path,monkeypatch):
 monkeypatch.setattr(launcher,'RUNTIME_DIR',tmp_path)
 with monkeypatch.context() as patch:
  patch.setattr(sys,'stdout',None);patch.setattr(sys,'stderr',None);patch.setattr(sys,'stdin',None)
  launcher._ensure_stdio()
  output=sys.stdout;input_stream=sys.stdin
  assert sys.stdout is sys.stderr and sys.stdout.isatty() is False
  import uvicorn
  uvicorn.Config(app=None,log_level='warning')
  import logging
  for name in ('uvicorn','uvicorn.error','uvicorn.access'):
   for handler in list(logging.getLogger(name).handlers):
    if getattr(handler,'stream',None) is output:logging.getLogger(name).removeHandler(handler)
  output.close();input_stream.close()
 assert (tmp_path/'logs/launcher.log').exists()

@pytest.mark.skipif(os.name!="nt",reason="Windows process flags")
def test_hidden_detached_flags_are_not_conflicting():
 assert launcher._creationflags(hidden=True,detached=True)==launcher.subprocess.DETACHED_PROCESS
 assert launcher._creationflags(hidden=True)==launcher.subprocess.CREATE_NO_WINDOW

def test_frozen_server_console_off_never_allocates_console(tmp_path,monkeypatch):
 called=[]
 monkeypatch.setattr(sys,'argv',['program','--server'])
 monkeypatch.setattr(launcher,'load_settings',lambda:SimpleNamespace(launcher=SimpleNamespace(show_console=False)))
 monkeypatch.setattr(launcher,'_ensure_visible_console',lambda:called.append('console'))
 monkeypatch.setattr(launcher,'_ensure_stdio',lambda:None)
 from app import main
 monkeypatch.setattr(main,'main',lambda:called.append('server'))
 assert launcher.main()==0 and called==['server']

def test_build_uses_gui_subsystem():
 script=(Path(__file__).parents[1]/'scripts/build-installer.ps1').read_text(encoding='utf-8')
 assert '--windowed' in script and '--console' not in script
