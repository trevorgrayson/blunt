
import json
import urllib.parse
import urllib.request
import time

# -------------------------
# Databricks API Functions
# -------------------------

def api_get(host, token, endpoint, params=None):
    """Helper to call Databricks REST API with bearer token."""
    url = f"{host}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"[WARN] Error calling {url}: {e}")
        return {}

def get_table_metadata(host, token, full_name):
    """Fetch owner, created_by, updated_by (if available) for a table."""
    encoded_name = urllib.parse.quote(full_name, safe="")
    details = api_get(host, token, f"/api/2.1/unity-catalog/tables/{encoded_name}")
    owner = details.get("owner")
    created_by = details.get("created_by")
    updated_by = details.get("updated_by")
    email = updated_by or created_by or owner or "N/A"
    return {"owner": owner, "created_by": created_by, "updated_by": updated_by, "email": email}

def get_downstream(host, token, full_name):
    """Return downstream tables/views using /api/2.0/lineage-tracking/table-lineage."""
    encoded_name = urllib.parse.quote(full_name, safe="")
    lineage = api_get(host, token, f"/api/2.0/lineage-tracking/table-lineage", {
        "table_name": encoded_name,
        "direction": "DOWNSTREAM"
    })
    downstream_objs = []

    # Notebooks? Views?
    for dep in lineage.get("downstreams", []):
        print(dep)
        if dep.get("tableInfo"):
            downstream_objs.append(dep["tableInfo"]["catalog_name"] + "." +\
                                   dep["tableInfo"]["schema_name"] + "." +\
                                   dep["tableInfo"]["name"])
            # lineage_timestamp NICE!

    return downstream_objs

def list_tables_in_schema(host, token, catalog, schema):
    """List all tables in the specified schema."""
    resp = api_get(host, token, "/api/2.1/unity-catalog/tables", {
        "catalog_name": catalog,
        "schema_name": schema
    })
    return [t["full_name"] for t in resp.get("tables", [])]

# -------------------------
# Recursive Traversal Logic
# -------------------------

def traverse_downstream(host, token, root_table, visited, graph, depth=0, delay=0.2):
    """Recursively walk all downstream dependencies."""
    if root_table in visited:
        return
    visited.add(root_table)

    print("  " * depth + f"↳ {root_table}")
    metadata = get_table_metadata(host, token, root_table)
    graph[root_table] = {"metadata": metadata, "downstream": []}

    downstream_objs = get_downstream(host, token, root_table)
    graph[root_table]["downstream"] = downstream_objs

    for dep in downstream_objs:
        time.sleep(delay)
        traverse_downstream(host, token, dep, visited, graph, depth + 1)
