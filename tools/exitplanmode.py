import os, json, uuid
WORKDIR = os.getcwd()
DB = os.path.join(WORKDIR, "db")
os.makedirs(DB, exist_ok=True)
def call(plan=None, **kwargs):
    plan = plan or kwargs.get("plan")
    if not plan or not isinstance(plan, str):
        return {"success": False, "output":"Parameter 'plan' required", "meta": {}}
    pid = uuid.uuid4().hex[:8]
    path = os.path.join(DB, f"plan_{pid}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"id":pid,"plan":plan}, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return {"success": False, "output": f"Save error: {e}", "meta": {}}
    return {"success": True, "output": "Plan saved awaiting approval", "meta": {"plan_id":pid,"path":path}}
