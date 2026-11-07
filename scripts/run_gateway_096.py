import sys, os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('ASTERION_CONTROL_STATE',str(Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'AsterionControl'))
import uvicorn
uvicorn.run('asterion_remote.mcp_gateway:app',host='127.0.0.1',port=8995,log_level='warning')
