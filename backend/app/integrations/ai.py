"""Optional AI layer. Supports Ollama (local) and any OpenAI-compatible chat API (optional, user-configured).

Every task sends *real data from the database* as context and instructs the model to stay within it.
The platform works fully without an AI provider.
"""
from __future__ import annotations

import json

import httpx

SYSTEM_PROMPT = (
    "You are an SEO analyst inside an open-source SEO toolkit. Ground every statement in the DATA block the "
    "user message contains. Do not invent search volumes, rankings, traffic numbers, backlink counts or "
    "ranking factors. If the data is insufficient to answer, say what is missing. Be specific: reference the "
    "URLs, titles and numbers given. Write plain language a business owner understands, in concise Markdown."
)

TASKS: dict[str, dict] = {
    "explain_issue": {"label": "Explain an audit issue", "needs": "issue",
                      "instruction": "Explain this technical SEO issue in simple language: what it is, why it matters for this site, and step-by-step how to fix it. Refer to the affected URLs listed."},
    "prioritise_fixes": {"label": "Prioritise fixes", "needs": "audit",
                         "instruction": "Create a prioritised fix list from this audit summary. Order by likely impact (severity x number of affected pages) and effort. For each item give: what to do, why, and which rule it addresses. Mark impact as an estimate."},
    "action_plan": {"label": "SEO action plan", "needs": "audit",
                    "instruction": "Write a 30/60/90-day SEO action plan based strictly on this audit data (and Search Console data if included)."},
    "titles": {"label": "Title suggestions", "needs": "page",
               "instruction": "Suggest 5 SEO-friendly title tags (max 60 characters each) for this page, based on its current title, H1, headings and content summary. State the character count of each."},
    "meta_descriptions": {"label": "Meta description suggestions", "needs": "page",
                          "instruction": "Write 3 meta descriptions (120-155 characters each) for this page based on its content. State the character count of each."},
    "internal_links": {"label": "Internal link suggestions", "needs": "page_links",
                       "instruction": "From the candidate pages listed, suggest up to 8 internal links to add to the target page, each with suggested anchor text and a one-line reason. Only use URLs from the candidate list."},
    "content_gaps": {"label": "Content gap analysis", "needs": "competitors",
                     "instruction": "Compare the site's topics with the competitors' topics in the data. List content gaps (topics competitors cover that this site does not) and recommend new article topics. Only use the terms and page titles provided."},
    "content_brief": {"label": "Content brief", "needs": "serp",
                      "instruction": "Create a content brief for the keyword using the SERP analysis data: search intent, recommended structure (H2/H3 outline), topics to cover, questions to answer, suggested word-count range based on the analysed pages, and schema types to use."},
    "schema": {"label": "Schema markup suggestion", "needs": "page",
               "instruction": "Recommend the most suitable schema.org type(s) for this page and output a JSON-LD block filled only with values present in the data; use clear PLACEHOLDER markers for anything unknown."},
    "ranking_decline": {"label": "Explain a ranking decline", "needs": "gsc",
                        "instruction": "Using the Search Console comparison data and the audit findings for the affected pages, list plausible explanations for the decline, ordered by how well the data supports them. Clearly separate what the data shows from hypotheses, and say what to check next."},
    "competitor_analysis": {"label": "Competitor analysis", "needs": "competitors",
                            "instruction": "Summarise how this site compares with each competitor using the measured metrics provided, then list the 5 most actionable opportunities."},
}


class AIError(RuntimeError):
    pass


async def status(cfg: dict) -> dict:
    provider = cfg.get("provider", "none")
    if provider == "none":
        return {"provider": "none", "available": False, "message": "No AI provider configured. All non-AI features work without one."}
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            if provider == "ollama":
                r = await client.get(f"{cfg['base_url'].rstrip('/')}/api/tags")
                r.raise_for_status()
                models = [m["name"] for m in r.json().get("models", [])]
                ok = any(m.split(":")[0] == cfg.get("model", "").split(":")[0] for m in models)
                return {"provider": provider, "available": True, "models": models, "model": cfg.get("model"),
                        "message": "Ollama is reachable." if ok else f"Ollama is reachable but model '{cfg.get('model')}' is not pulled."}
            r = await client.get(f"{cfg['base_url'].rstrip('/')}/models", headers={"Authorization": f"Bearer {cfg.get('api_key', '')}"})
            return {"provider": provider, "available": r.status_code == 200, "model": cfg.get("model"),
                    "message": "API reachable." if r.status_code == 200 else f"API answered HTTP {r.status_code}"}
    except httpx.HTTPError as exc:
        return {"provider": provider, "available": False, "message": f"Could not reach the AI provider: {exc}"}


async def complete(cfg: dict, prompt: str, system: str = SYSTEM_PROMPT) -> str:
    provider = cfg.get("provider", "none")
    if provider == "none":
        raise AIError("No AI provider is configured (Settings -> AI).")
    base = (cfg.get("base_url") or "").rstrip("/")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            if provider == "ollama":
                r = await client.post(f"{base}/api/chat", json={"model": cfg.get("model"), "messages": messages, "stream": False,
                                                                 "options": {"temperature": 0.3}})
                if r.status_code != 200:
                    raise AIError(f"Ollama error {r.status_code}: {r.text[:300]}")
                return r.json().get("message", {}).get("content", "").strip()
            if provider == "openai_compatible":
                r = await client.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {cfg.get('api_key', '')}"},
                                      json={"model": cfg.get("model"), "messages": messages, "temperature": 0.3})
                if r.status_code != 200:
                    raise AIError(f"AI API error {r.status_code}: {r.text[:300]}")
                return r.json()["choices"][0]["message"]["content"].strip()
    except httpx.HTTPError as exc:
        raise AIError(f"Could not reach the AI provider: {exc}") from exc
    raise AIError(f"Unknown AI provider '{provider}'")


def build_prompt(task: str, data: dict, extra: str = "") -> str:
    spec = TASKS[task]
    payload = json.dumps(data, ensure_ascii=False, default=str)
    if len(payload) > 24_000:
        payload = payload[:24_000] + " ...[truncated]"
    return f"TASK: {spec['instruction']}\n{('NOTE FROM USER: ' + extra[:500]) if extra else ''}\n\nDATA (JSON):\n{payload}"
