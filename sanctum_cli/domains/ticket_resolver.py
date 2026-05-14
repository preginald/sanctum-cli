"""Ticket create resolver — resolves names/UUIDs, infers ownership from intent."""

from __future__ import annotations

import builtins
import re

import click

from sanctum_cli.display import print_warning
from sanctum_client.client import get as api_get

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_RESOLUTION_WARNINGS = "_resolution_warnings"

_DIGITAL_SANCTUM_HQ_ACCOUNT = "dbc2c7b9-d8c2-493f-a6ed-527f7d191068"


class AmbiguousEntity(click.ClickException):
    """Raised when entity resolution has multiple candidates."""

    def __init__(self, message: str, candidates: list[dict], entity_type: str):
        super().__init__(message)
        self.candidates = candidates
        self.entity_type = entity_type


class TicketCreateResolver:
    """Resolves ticket creation fields, inferring project/account/product from intent.

    Resolution order:
    1. UUID values pass through unchanged.
    2. Non-UUID values are treated as entity names and resolved via API.
    3. Missing project/milestone/product is inferred from subject/description.
    4. Missing account_id is inferred from resolved project or product.
    """

    def __init__(self, ctx: click.Context):
        self.ctx = ctx
        self.output_json = bool(ctx.obj.get("output_json"))

    def resolve(
        self,
        *,
        account_id: str | None,
        project_id: str | None,
        milestone_id: str | None,
        product_ids: str | None,
        subject: str,
        description: str,
    ) -> dict:
        """Resolve all ticket creation fields.

        Returns a dict suitable for the ticket create payload:
          account_id, project_id, milestone_id, product_ids.

        May include _RESOLUTION_WARNINGS for advisory display.
        """
        warnings: list[str] = []
        result: dict = {
            "account_id": account_id,
            "project_id": project_id,
            "milestone_id": milestone_id,
            "product_ids": product_ids,
        }

        result["project_id"] = self._resolve_project(project_id, warnings)
        result["milestone_id"] = self._resolve_milestone(
            milestone_id, result.get("project_id"), warnings, result
        )
        result["product_ids"] = self._resolve_products(
            product_ids, subject, description, result.get("project_id"), warnings, result
        )
        result["account_id"] = self._resolve_account(
            account_id, result.get("project_id"), result.get("product_ids"), warnings
        )

        if warnings:
            result[_RESOLUTION_WARNINGS] = warnings
        return result

    # ------------------------------------------------------------------
    # Project resolution
    # ------------------------------------------------------------------

    def _resolve_project(self, project_id: str | None, warnings: list[str]) -> str | None:
        if not project_id:
            return None
        if UUID_RE.match(project_id):
            return project_id
        project = self._find_project_by_name(project_id)
        if project:
            pid = project.get("id") or project.get("uuid")
            if pid:
                warnings.append(f"Resolved project {project_id!r} → {pid}")
                return pid
        raise click.ClickException(f"Project not found: {project_id}")

    def _find_project_by_name(self, name: str) -> dict | None:
        try:
            result = api_get("/search", params={"q": name, "type": "project", "limit": "10"})
            results = result if isinstance(result, builtins.list) else result.get("results", [])
            projects = [r for r in results if r.get("type") in ("project", None)]
            exact = [
                p
                for p in projects
                if (p.get("title") or p.get("name") or "").lower() == name.lower()
            ]
            if exact:
                return exact[0]
            if len(projects) == 1:
                return projects[0]
            if len(projects) > 1:
                candidates = [
                    {
                        "id": p.get("id") or p.get("uuid"),
                        "name": p.get("title") or p.get("name", ""),
                    }
                    for p in projects[:5]
                ]
                raise AmbiguousEntity(
                    f"Multiple projects match {name!r}",
                    candidates=candidates,
                    entity_type="project",
                )
        except AmbiguousEntity:
            raise
        except Exception:
            pass
        return self._find_project_by_list(name)

    def _find_project_by_list(self, name: str) -> dict | None:
        seen = 0
        page = 1
        page_size = 100
        while page <= 50:
            result = api_get(
                "/projects",
                params={"limit": str(page_size), "offset": str((page - 1) * page_size)},
            )
            items = result if isinstance(result, builtins.list) else result.get("projects", [])
            exact = [p for p in items if p.get("name", "").lower() == name.lower()]
            if exact:
                return exact[0]
            seen += len(items)
            if len(items) < page_size:
                break
            page += 1
        return None

    # ------------------------------------------------------------------
    # Milestone resolution
    # ------------------------------------------------------------------

    def _resolve_milestone(
        self,
        milestone_id: str | None,
        current_project_id: str | None,
        warnings: list[str],
        result: dict,
    ) -> str | None:
        if not milestone_id:
            return None
        if UUID_RE.match(milestone_id):
            if not current_project_id:
                try:
                    m = api_get(f"/milestones/{milestone_id}")
                    if isinstance(m, dict) and m.get("project_id"):
                        result["project_id"] = m["project_id"]
                        warnings.append(f"Inferred project_id {m['project_id']} from milestone")
                except Exception:
                    pass
            return milestone_id
        pid = current_project_id
        if not pid:
            raise click.ClickException(
                "Cannot resolve milestone by name without a project. "
                "Provide --project-id or supply the milestone UUID."
            )
        result_raw = api_get("/milestones", params={"project_id": pid})
        mlist = (
            result_raw
            if isinstance(result_raw, builtins.list)
            else result_raw.get("milestones", [])
        )
        exact = [m for m in mlist if m.get("name", "").lower() == milestone_id.lower()]
        if exact:
            mid = exact[0]["id"]
            warnings.append(f"Resolved milestone {milestone_id!r} → {mid}")
            return mid
        raise click.ClickException(f"Milestone {milestone_id!r} not found in project {pid}")

    # ------------------------------------------------------------------
    # Product resolution & inference
    # ------------------------------------------------------------------

    def _resolve_products(
        self,
        product_ids: str | None,
        subject: str,
        description: str,
        project_id: str | None,
        warnings: list[str],
        result: dict,
    ) -> str | None:
        if product_ids:
            return self._resolve_product_refs(product_ids, warnings)
        if project_id or result.get("milestone_id"):
            return None
        inferred = self._infer_product(subject, description)
        if inferred:
            warnings.append(f"Inferred product from context → {inferred}")
            return inferred
        return None

    def _resolve_product_refs(self, raw: str, warnings: list[str]) -> str:
        refs = [r.strip() for r in raw.split(",") if r.strip()]
        resolved: list[str] = []
        for ref in refs:
            if UUID_RE.match(ref):
                resolved.append(ref)
            else:
                prod = self._find_product_by_name(ref)
                if prod:
                    pid = prod.get("id") or prod.get("uuid")
                    if pid:
                        warnings.append(f"Resolved product {ref!r} → {pid}")
                        resolved.append(pid)
                        continue
                raise click.ClickException(f"Product not found: {ref}")
        return ",".join(resolved)

    def _find_product_by_name(self, name: str) -> dict | None:
        result = api_get("/products", params={"limit": "200"})
        items = result if isinstance(result, builtins.list) else result.get("products", [])
        exact = [p for p in items if p.get("name", "").lower() == name.lower()]
        if exact:
            return exact[0]
        partial = [p for p in items if name.lower() in p.get("name", "").lower()]
        if len(partial) == 1:
            return partial[0]
        if len(partial) > 1:
            candidates = [{"id": p.get("id"), "name": p.get("name", "")} for p in partial[:5]]
            raise AmbiguousEntity(
                f"Multiple products match {name!r}",
                candidates=candidates,
                entity_type="product",
            )
        return None

    def _infer_product(self, subject: str, description: str) -> str | None:
        text = self._normalize_text(f"{subject} {description}")
        if not text:
            return None
        result = api_get("/products", params={"limit": "100"})
        prods = result if isinstance(result, builtins.list) else result.get("products", [])
        if not prods:
            return None
        scored: list[tuple[dict, float]] = []
        for p in prods:
            score = self._score_product_match(p, text)
            if score > 0.0:
                scored.append((p, score))
        if not scored:
            return None
        scored.sort(key=lambda x: -x[1])
        best, best_score = scored[0]
        if len(scored) == 1 and best_score >= 0.3:
            return best["id"]
        if best_score >= 0.7 and (len(scored) == 1 or best_score - scored[1][1] >= 0.2):
            return best["id"]
        candidates = [
            {
                "id": p["id"],
                "name": p.get("name", ""),
                "type": p.get("type", ""),
                "score": round(s, 2),
            }
            for p, s in scored[:5]
        ]
        raise AmbiguousEntity(
            "Multiple products match the ticket context",
            candidates=candidates,
            entity_type="product",
        )

    def _score_product_match(self, product: dict, text: str) -> float:
        name = (product.get("name") or "").lower()
        desc = (product.get("description") or "").lower()
        ptype = (product.get("type") or "").lower()
        score = 0.0
        name_lower = name.lower()
        if name_lower in text:
            score += 0.5
        for keyword in ptype.split():
            if keyword and keyword in text:
                score += 0.2
        desc_keywords = set(desc.split())
        text_words = set(text.split())
        common = desc_keywords & text_words
        if desc_keywords:
            overlap = len(common) / len(desc_keywords)
            score += overlap * 0.3
        return min(score, 1.0)

    # ------------------------------------------------------------------
    # Account resolution
    # ------------------------------------------------------------------

    def _resolve_account(
        self,
        account_id: str | None,
        project_id: str | None,
        product_ids: str | None,
        warnings: list[str],
    ) -> str | None:
        if account_id:
            return account_id
        if project_id:
            try:
                proj = api_get(f"/projects/{project_id}")
                if isinstance(proj, dict) and proj.get("account_id"):
                    aid = proj["account_id"]
                    if UUID_RE.match(aid):
                        warnings.append(f"Inferred account_id {aid} from project")
                        return aid
            except Exception:
                pass
        if product_ids:
            first = product_ids.split(",")[0].strip()
            try:
                prod = api_get(f"/products/{first}")
                if isinstance(prod, dict) and prod.get("account_id"):
                    aid = prod["account_id"]
                    if UUID_RE.match(aid):
                        warnings.append(f"Inferred account_id {aid} from product")
                        return aid
            except Exception:
                pass
            # Product-linked ticket without a resolvable account — default to Digital Sanctum HQ
            warnings.append(
                f"Defaulting account_id to Digital Sanctum HQ ({_DIGITAL_SANCTUM_HQ_ACCOUNT})"
            )
            return _DIGITAL_SANCTUM_HQ_ACCOUNT
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"[^a-z0-9\s]", " ", text.lower())

    @staticmethod
    def print_warnings(result: dict) -> None:
        warnings = result.get(_RESOLUTION_WARNINGS)
        if warnings:
            for w in warnings:
                print_warning(w)

    @staticmethod
    def print_ambiguous_error(exc: AmbiguousEntity) -> None:
        print_warning(f"Ambiguous {exc.entity_type}:")
        for c in exc.candidates:
            score_str = f" (score: {c.get('score')})" if "score" in c else ""
            print_warning(f"  {c['id']} — {c['name']}{score_str}")

    @staticmethod
    def print_ambiguous_json(exc: AmbiguousEntity) -> dict:
        return {
            "error": "ambiguous_entity",
            "entity_type": exc.entity_type,
            "candidates": exc.candidates,
        }
