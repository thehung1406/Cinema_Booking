"""Send extracted drafts to the existing authenticated knowledge owner API."""
import argparse
import json
import os
from pathlib import Path

import httpx
from ai_service.schemas import DocumentWrite


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--origin", default="http://127.0.0.1:8000")
    parser.add_argument("--token-env", default="CINEMA_ADMIN_TOKEN")
    parser.add_argument("--revision-of", type=int, help="Stage a new version of this document ID")
    parser.add_argument("--graph-release-id", default="", help="Preloaded graph release for a staged version")
    args = parser.parse_args()
    origin = httpx.URL(args.origin)
    if origin.scheme not in {"http", "https"} or origin.userinfo or origin.path != "/" or origin.query or origin.fragment:
        raise SystemExit("Use a fixed API origin without credentials or a path")
    token = os.environ.get(args.token_env, "")
    if not token:
        raise SystemExit(f"Set {args.token_env} to an authorized knowledge.manage session token")
    drafts = json.loads(Path(args.input).read_text(encoding="utf-8"))
    # Validate the entire batch before any mutation. Approval is intentionally excluded.
    payloads = [DocumentWrite.model_validate({k: v for k, v in draft.items() if k != "approved"}).model_dump(mode="json", exclude_none=True) for draft in drafts]
    if args.revision_of is not None and (args.revision_of <= 0 or len(payloads) != 1):
        parser.error("--revision-of requires a positive document ID and a single input document")
    if args.graph_release_id and args.revision_of is None:
        parser.error("--graph-release-id requires --revision-of")
    with httpx.Client(base_url=str(origin), headers={"Authorization": "Bearer " + token}, timeout=30,
                      follow_redirects=False, trust_env=False) as client:
        for payload in payloads:
            if args.revision_of is not None:
                from datetime import datetime, timezone
                document_url = f"/admin/documents/{args.revision_of}"
                current = client.get(document_url)
                current.raise_for_status()
                current_document = current.json()
                if current_document["source_id"] != payload["source_id"]:
                    raise SystemExit("The document ID and input source ID do not match")
                timestamp = datetime.fromisoformat(current_document["updated_at"])
                payload["expected_updated_at"] = (timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)).isoformat()
                response = client.post(f"{document_url}/revisions", json={
                    "document": payload, "graph_release_id": args.graph_release_id,
                })
                response.raise_for_status()
                print(json.dumps({"source_id": payload["source_id"], "revision_id": response.json()["id"], "published": False}))
                continue
            response = client.post("/admin/documents", json=payload)
            if response.status_code >= 400:
                raise SystemExit(f"Import stopped: source {payload['source_id']}, HTTP {response.status_code}; earlier drafts remain saved")
            saved = response.json()
            print(json.dumps({"source_id": payload["source_id"], "id": saved["id"], "approved": saved["approved"]}))


if __name__ == "__main__":
    main()
