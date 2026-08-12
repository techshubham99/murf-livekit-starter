import sys
import json
import os
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from src.escalation import get_all_escalations, update_escalation_status


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "update":
        ref_id = sys.argv[2]
        new_status = sys.argv[3]
        success = update_escalation_status(ref_id, new_status)
        print(json.dumps({"success": success, "reference_id": ref_id, "status": new_status}))
    else:
        escalations = get_all_escalations()
        print(json.dumps({"requests": escalations, "escalations": escalations}))


if __name__ == "__main__":
    main()
