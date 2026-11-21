import json


def export_json(analysis):
    return json.dumps(analysis, indent=2, ensure_ascii=False)
