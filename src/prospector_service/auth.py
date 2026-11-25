import base64
import binascii
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass

from fastapi import Request
from pydantic import TypeAdapter, ValidationError

from .errors import ServiceError
from .schemas import Cuid

ID = TypeAdapter(Cuid)
KEY = re.compile(r"[A-Za-z0-9._~-]{1,128}")
SEGMENT = re.compile(rb"[A-Za-z0-9_-]+")


@dataclass(frozen=True)
class Actor:
    solution: str
    tenant: str
    owner: str


def decode_segment(segment: bytes) -> bytes:
    if not SEGMENT.fullmatch(segment):
        raise ValueError("invalid encoding")
    return base64.b64decode(segment + b"=" * (-len(segment) % 4), altchars=b"-_", validate=True)


def unique_object(pairs):
    values = dict(pairs)
    if len(values) != len(pairs):
        raise ValueError("duplicate JSON field")
    return values


def one_header(request: Request, name: str) -> str:
    values = request.headers.getlist(name)
    if len(values) != 1:
        raise ValueError("header cardinality")
    return values[0]


def authorize(request: Request, scope: str | tuple[str, str], body: bytes, key: str = "") -> Actor:
    settings = request.app.state.settings
    if not settings.credentials_configured:
        raise ServiceError(503, "SERVICE_UNAVAILABLE", "Service credentials unavailable")
    try:
        submitted = one_header(request, "X-API-Key").encode()
        expected = settings.internal_api_key.get_secret_value().encode()
        if not hmac.compare_digest(submitted, expected):
            raise ValueError("invalid API key")
        token = one_header(request, "X-Platform-Assertion").encode("ascii")
        if len(token) > 4096:
            raise ValueError("assertion too large")
        header, payload, signature = token.split(b".")
        fields = json.loads(decode_segment(header), object_pairs_hook=unique_object)
        if fields != {"alg": "HS256", "typ": "JWT"}:
            raise ValueError("unsupported header")
        expected_signature = hmac.digest(
            settings.assertion_key.get_secret_value().encode(), header + b"." + payload, "sha256"
        )
        if not hmac.compare_digest(expected_signature, decode_segment(signature)):
            raise ValueError("invalid signature")
        claims = json.loads(decode_segment(payload), object_pairs_hook=unique_object)
        if not isinstance(claims, dict):
            raise ValueError("invalid claims")
        raw_path = request.scope.get("raw_path", request.url.path.encode("ascii")).decode("ascii")
        binding = {
            "iss": settings.assertion_issuer,
            "aud": settings.assertion_audience,
            "solutionId": settings.solution_id,
            "method": request.method,
            "path": raw_path,
            "query": request.scope["query_string"].decode("ascii"),
            "idempotencyKey": key,
            "bodySha256": hashlib.sha256(body).hexdigest(),
        }
        if any(claims.get(name) != value for name, value in binding.items()):
            raise ValueError("binding mismatch")
        issued, expires = claims.get("iat"), claims.get("exp")
        now = time.time()
        if (
            type(issued) is not int
            or type(expires) is not int
            or not now - 150 <= issued <= now + 30
            or not now < expires <= issued + 120
        ):
            raise ValueError("assertion expired or invalid")
        tenant = ID.validate_python(claims.get("tenantId"))
        owner = ID.validate_python(claims.get("sub"))
    except (ValueError, UnicodeError, binascii.Error, ValidationError, RecursionError) as exc:
        raise ServiceError(401, "UNAUTHORIZED", "Invalid service credentials or assertion") from exc

    actor_type, granted = claims.get("actorType"), claims.get("scope")
    if isinstance(scope, tuple):
        permitted = (actor_type == "owner" and granted == scope[0]) or (
            actor_type == "platform" and granted == scope[1]
        )
    else:
        delegates = {"prospecting:results:ack", "prospecting:results:purge"}
        permitted = granted == scope and (
            actor_type == "owner" or (actor_type == "platform" and scope in delegates)
        )
    if not permitted:
        raise ServiceError(403, "FORBIDDEN", "Assertion scope does not permit this operation")
    return Actor(settings.solution_id, tenant, owner)
