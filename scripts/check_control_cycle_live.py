"""Read-only device acceptance: distinguish published APK from installed cycle-capable APK."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from asterion_remote.phone_bridge import request

def main():
    reply=request('/cycles/status',timeout=7.0)
    data=reply.json()
    checkpoint=data.get('checkpoint',{})
    cycle=data.get('cycle',{})
    print(json.dumps({
       "phone_api_http":reply.status_code,
       "controller":data.get('controller'),
       "android_autonomous_cycle":data.get('android_autonomous_cycle',False),
       "cycle_active":cycle.get('active',False),
       "cycle_state":cycle.get('state',''),
       "cycle_index":cycle.get('index',0),
       "checkpoint_state":checkpoint.get('state',checkpoint if isinstance(checkpoint,str) else ''),
    },separators=(',',':')))
    if reply.status_code!=200 or data.get('android_autonomous_cycle') is not True:
        print("ACCEPTANCE_FAIL: installed phone API is not v0.9.13 cycle-capable")
        return 2
    print("ACCEPTANCE_PASS: installed phone exposes native autonomous cycle endpoints")
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print("ACCEPTANCE_ERROR:"+type(e).__name__+":"+str(e)[:160])
        sys.exit(3)
