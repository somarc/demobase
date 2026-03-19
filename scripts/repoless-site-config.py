#!/usr/bin/env python3
"""Inspect and repair repoless AEM site config via admin.hlx.page."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://admin.hlx.page/config"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)
TOKEN_ENV_CANDIDATES = ("AEM_ADMIN_TOKEN", "DA_TOKEN", "IMS_TOKEN")


@dataclass
class ResponseData:
    status: int
    body: bytes
    headers: dict[str, str]


def resolve_token(explicit_token: str | None) -> str:
    if explicit_token:
        return explicit_token.strip()
    for env_name in TOKEN_ENV_CANDIDATES:
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    joined = ", ".join(f"${name}" for name in TOKEN_ENV_CANDIDATES)
    raise SystemExit(f"Missing access token. Pass --token or set one of: {joined}")


def request(
    method: str,
    url: str,
    token: str | None = None,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> ResponseData:
    req_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if token:
        req_headers["x-auth-token"] = token
    if headers:
        req_headers.update(headers)

    req = Request(url=url, method=method, headers=req_headers, data=body)
    try:
        with urlopen(req) as resp:
            return ResponseData(
                status=resp.status,
                body=resp.read(),
                headers={k.lower(): v for k, v in resp.headers.items()},
            )
    except HTTPError as exc:
        return ResponseData(
            status=exc.code,
            body=exc.read(),
            headers={k.lower(): v for k, v in exc.headers.items()},
        )
    except URLError as exc:
        raise SystemExit(f"{method} {url} failed: {exc.reason}") from exc


def site_config_url(org: str, site: str) -> str:
    return f"{BASE_URL}/{org}/sites/{site}.json"


def query_index_url(org: str, site: str) -> str:
    return f"{BASE_URL}/{org}/sites/{site}/content/query.yaml"


def public_site_url(org: str, site: str) -> str:
    return f"https://main--{site}--{org}.aem.page/"


def decode_json(label: str, payload: bytes) -> dict[str, Any]:
    text = payload.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{label} returned invalid JSON:\n{text}") from exc


def fetch_site_config(token: str, org: str, site: str) -> tuple[int, dict[str, Any] | None, str]:
    resp = request("GET", site_config_url(org, site), token=token)
    text = resp.body.decode("utf-8", errors="replace")
    if resp.status == 404:
        return resp.status, None, text
    if resp.status != 200:
        raise SystemExit(f"GET {site_config_url(org, site)} failed: {resp.status} {text}")
    return resp.status, decode_json("site config", resp.body), text


def fetch_query_index(token: str, org: str, site: str) -> tuple[int, str]:
    resp = request("GET", query_index_url(org, site), token=token)
    return resp.status, resp.body.decode("utf-8", errors="replace")


def build_site_config(
    code_owner: str,
    code_repo: str,
    content_url: str,
    baseline_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": {
            "owner": code_owner,
            "repo": code_repo,
        },
        "content": {
            "source": {
                "url": content_url,
            },
        },
    }

    if baseline_config:
        version = baseline_config.get("version")
        if version is not None:
            payload["version"] = version

        sidekick = baseline_config.get("sidekick")
        if isinstance(sidekick, dict) and sidekick:
            payload["sidekick"] = sidekick

        headers = baseline_config.get("headers")
        if isinstance(headers, dict) and headers:
            payload["headers"] = headers

    return payload


def put_site_config(token: str, org: str, site: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    resp = request(
        "PUT",
        site_config_url(org, site),
        token=token,
        body=body,
        headers={"Content-Type": "application/json"},
    )
    text = resp.body.decode("utf-8", errors="replace")
    if resp.status not in {200, 201}:
        raise SystemExit(f"PUT {site_config_url(org, site)} failed: {resp.status} {text}")


def put_query_index(token: str, org: str, site: str, yaml_text: str) -> None:
    body = yaml_text.encode("utf-8")
    resp = request(
        "PUT",
        query_index_url(org, site),
        token=token,
        body=body,
        headers={"Content-Type": "text/yaml"},
    )
    if resp.status == 409:
        resp = request(
            "POST",
            query_index_url(org, site),
            token=token,
            body=body,
            headers={"Content-Type": "text/yaml"},
        )
    text = resp.body.decode("utf-8", errors="replace")
    if resp.status not in {200, 201, 204}:
        raise SystemExit(f"PUT/POST {query_index_url(org, site)} failed: {resp.status} {text}")


def verify_public(org: str, site: str) -> int:
    resp = request("HEAD", public_site_url(org, site))
    error = resp.headers.get("x-error", "")
    print(f"Public URL: {public_site_url(org, site)}")
    print(f"Status: {resp.status}")
    if error:
        print(f"x-error: {error}")
    return resp.status


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--org", required=True)
    parser.add_argument("--site", required=True)
    parser.add_argument("--token", help="Access token. Falls back to env vars if omitted.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect and repair repoless site config.")
    sub = parser.add_subparsers(dest="command", required=True)

    show_parser = sub.add_parser("show", help="Fetch and print the current site config.")
    add_common_args(show_parser)

    verify_parser = sub.add_parser("verify", help="Check whether the public site URL resolves.")
    add_common_args(verify_parser)

    put_parser = sub.add_parser("put", help="Create or replace a repoless site config.")
    add_common_args(put_parser)
    put_parser.add_argument("--code-owner")
    put_parser.add_argument("--code-repo")
    put_parser.add_argument("--content-url")
    put_parser.add_argument("--baseline-site", help="Existing site to copy safe settings from.")
    put_parser.add_argument(
        "--copy-query-index",
        action="store_true",
        help="Also copy query.yaml from --baseline-site when present.",
    )
    put_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the payload without sending the PUT.",
    )
    return parser


def cmd_show(args: argparse.Namespace) -> int:
    token = resolve_token(args.token)
    status, config, raw = fetch_site_config(token, args.org, args.site)
    print(f"Status: {status}")
    if config is None:
        print(raw.strip() or "Not found")
        return 1
    print(json.dumps(config, indent=2, sort_keys=True))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    status = verify_public(args.org, args.site)
    return 0 if status == 200 else 1


def cmd_put(args: argparse.Namespace) -> int:
    baseline_config = None

    if args.baseline_site:
        token = resolve_token(args.token)
        _, baseline_config, _ = fetch_site_config(token, args.org, args.baseline_site)
        if baseline_config is None:
            raise SystemExit(
                f"Baseline site {args.org}/{args.baseline_site} has no config; cannot clone settings from it."
            )

    code_owner = args.code_owner or (
        baseline_config.get("code", {}).get("owner") if baseline_config else None
    )
    code_repo = args.code_repo or (
        baseline_config.get("code", {}).get("repo") if baseline_config else None
    )
    if not code_owner:
        code_owner = args.org
    if not code_repo:
        raise SystemExit("Missing --code-repo. Pass it explicitly or use --baseline-site.")

    content_url = args.content_url or f"https://content.da.live/{args.org}/{args.site}/"
    payload = build_site_config(code_owner, code_repo, content_url, baseline_config)

    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    token = resolve_token(args.token)
    put_site_config(token, args.org, args.site, payload)
    print(f"Created site config for {args.org}/{args.site}")
    print(json.dumps(payload, indent=2, sort_keys=True))

    if args.copy_query_index:
        if not args.baseline_site:
            raise SystemExit("--copy-query-index requires --baseline-site")
        status, query_yaml = fetch_query_index(token, args.org, args.baseline_site)
        if status == 200 and query_yaml.strip():
            put_query_index(token, args.org, args.site, query_yaml)
            print(f"Copied query index from {args.org}/{args.baseline_site}")
        elif status == 404:
            print(f"No baseline query index found on {args.org}/{args.baseline_site}; skipping.")
        else:
            raise SystemExit(
                f"GET {query_index_url(args.org, args.baseline_site)} failed: {status} {query_yaml}"
            )

    verify_public(args.org, args.site)
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "show":
        return cmd_show(args)
    if args.command == "verify":
        return cmd_verify(args)
    if args.command == "put":
        return cmd_put(args)
    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
