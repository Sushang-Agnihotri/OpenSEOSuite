"""schema.org JSON-LD validation and template generation.

Required/recommended properties follow Google's public rich-result documentation where a rich
result exists for the type, and otherwise sensible schema.org practice. This is a pragmatic
validator, not a full schema.org vocabulary checker (see KNOWN_LIMITATIONS.md).
"""
from __future__ import annotations

import json
from typing import Any

# type -> (required, recommended, parent type used when the type itself has no entry)
SPECS: dict[str, dict[str, Any]] = {
    "Organization": {"required": ["name"], "recommended": ["url", "logo", "sameAs", "contactPoint"]},
    "LocalBusiness": {"required": ["name", "address"], "recommended": ["telephone", "openingHoursSpecification", "geo", "url", "image", "priceRange"]},
    "Product": {"required": ["name"], "recommended": ["image", "description", "offers", "brand", "sku", "aggregateRating", "review"],
                "any_of": [["offers", "review", "aggregateRating"]]},
    "Offer": {"required": ["price", "priceCurrency"], "recommended": ["availability", "url", "priceValidUntil"]},
    "AggregateRating": {"required": ["ratingValue"], "recommended": ["bestRating"], "any_of": [["reviewCount", "ratingCount"]]},
    "Review": {"required": ["author", "reviewRating"], "recommended": ["datePublished", "reviewBody"]},
    "Article": {"required": ["headline"], "recommended": ["image", "datePublished", "dateModified", "author", "publisher"]},
    "BlogPosting": {"required": ["headline"], "recommended": ["image", "datePublished", "dateModified", "author", "publisher"]},
    "NewsArticle": {"required": ["headline"], "recommended": ["image", "datePublished", "dateModified", "author", "publisher"]},
    "BreadcrumbList": {"required": ["itemListElement"], "recommended": []},
    "ListItem": {"required": ["position"], "recommended": ["name", "item"]},
    "FAQPage": {"required": ["mainEntity"], "recommended": []},
    "Question": {"required": ["name", "acceptedAnswer"], "recommended": []},
    "Answer": {"required": ["text"], "recommended": []},
    "WebSite": {"required": ["name", "url"], "recommended": ["potentialAction", "publisher"]},
    "WebPage": {"required": ["name"], "recommended": ["url", "description", "isPartOf"]},
    "Service": {"required": ["name"], "recommended": ["provider", "description", "areaServed", "serviceType"]},
    "Person": {"required": ["name"], "recommended": ["url", "jobTitle", "sameAs", "image"]},
    "Event": {"required": ["name", "startDate", "location"], "recommended": ["endDate", "description", "image", "offers", "organizer", "eventStatus"]},
    "PostalAddress": {"required": [], "recommended": ["streetAddress", "addressLocality", "postalCode", "addressCountry"]},
    "VideoObject": {"required": ["name", "thumbnailUrl", "uploadDate"], "recommended": ["description", "contentUrl", "duration"]},
    "Recipe": {"required": ["name", "image"], "recommended": ["author", "recipeIngredient", "recipeInstructions", "totalTime"]},
    "JobPosting": {"required": ["title", "description", "datePosted", "hiringOrganization", "jobLocation"], "recommended": ["validThrough", "employmentType", "baseSalary"]},
    "HowTo": {"required": ["name", "step"], "recommended": ["image", "totalTime"]},
    "SoftwareApplication": {"required": ["name"], "recommended": ["offers", "aggregateRating", "applicationCategory", "operatingSystem"]},
}
# Subtypes validated with their parent's spec.
PARENTS = {
    "Restaurant": "LocalBusiness", "Store": "LocalBusiness", "Dentist": "LocalBusiness", "MedicalBusiness": "LocalBusiness",
    "ProfessionalService": "LocalBusiness", "LegalService": "LocalBusiness", "AutoRepair": "LocalBusiness",
    "Hotel": "LocalBusiness", "LodgingBusiness": "LocalBusiness", "HomeAndConstructionBusiness": "LocalBusiness",
    "RealEstateAgent": "LocalBusiness", "TechArticle": "Article", "Corporation": "Organization",
    "NGO": "Organization", "EducationalOrganization": "Organization", "OnlineStore": "Organization",
    "AboutPage": "WebPage", "ContactPage": "WebPage", "CollectionPage": "WebPage", "ItemPage": "WebPage",
    "ProfilePage": "WebPage", "FAQPage": "FAQPage", "MusicEvent": "Event", "BusinessEvent": "Event",
    "Festival": "Event", "ProductGroup": "Product",
}
LOCAL_TYPES = {"LocalBusiness"} | {k for k, v in PARENTS.items() if v == "LocalBusiness"}


def _types(item: dict) -> list[str]:
    t = item.get("@type")
    if isinstance(t, str):
        return [t.rsplit("/", 1)[-1]]
    if isinstance(t, list):
        return [x.rsplit("/", 1)[-1] for x in t if isinstance(x, str)]
    return []


def _present(item: dict, prop: str) -> bool:
    v = item.get(prop)
    return v not in (None, "", [], {})


def validate_item(item: Any, path: str = "", top_level: bool = True, depth: int = 0) -> list[dict]:
    """Return findings: {level: error|warning|structure, type, path, message, properties}."""
    findings: list[dict] = []
    if not isinstance(item, dict):
        return [{"level": "structure", "type": None, "path": path or "$", "message": "JSON-LD item is not an object"}]
    types = _types(item)
    if top_level:
        ctx = item.get("@context")
        ctx_text = json.dumps(ctx) if ctx is not None else ""
        if not ctx:
            findings.append({"level": "structure", "type": ",".join(types) or None, "path": path or "$",
                             "message": "Missing @context (expected https://schema.org)"})
        elif "schema.org" not in ctx_text:
            findings.append({"level": "structure", "type": ",".join(types) or None, "path": path or "$",
                             "message": f"Unexpected @context {ctx_text[:80]}"})
    if not types:
        if top_level or any(k for k in item if not k.startswith("@")):
            if top_level:
                findings.append({"level": "structure", "type": None, "path": path or "$", "message": "Item has no @type"})
        return findings
    for t in types:
        spec = SPECS.get(t) or SPECS.get(PARENTS.get(t, ""))
        if not spec:
            continue
        missing = [p for p in spec["required"] if not _present(item, p)]
        if missing:
            findings.append({"level": "error", "type": t, "path": path or "$", "properties": missing,
                             "message": f"{t}: missing required {', '.join(missing)}"})
        for group in spec.get("any_of", []):
            if not any(_present(item, p) for p in group):
                findings.append({"level": "error", "type": t, "path": path or "$", "properties": group,
                                 "message": f"{t}: needs at least one of {', '.join(group)}"})
        rec = [p for p in spec["recommended"] if not _present(item, p)] if top_level else []
        if rec:
            findings.append({"level": "warning", "type": t, "path": path or "$", "properties": rec,
                             "message": f"{t}: missing recommended {', '.join(rec)}"})
    if depth < 6:
        for key, value in item.items():
            if key.startswith("@"):
                continue
            children = value if isinstance(value, list) else [value]
            for i, child in enumerate(children[:50]):
                if isinstance(child, dict) and child.get("@type"):
                    findings.extend(validate_item(child, f"{path or '$'}.{key}[{i}]" if isinstance(value, list) else f"{path or '$'}.{key}", False, depth + 1))
    return findings


def validate_jsonld(items: list) -> dict:
    """Validate parsed JSON-LD items; return {types, findings, errors, warnings}."""
    findings: list[dict] = []
    types: list[str] = []
    for i, item in enumerate(items):
        if isinstance(item, dict):
            types.extend(_types(item))
        findings.extend(validate_item(item, f"$[{i}]"))
    return {
        "types": list(dict.fromkeys(types)),
        "findings": findings,
        "errors": sum(1 for f in findings if f["level"] in ("error", "structure")),
        "warnings": sum(1 for f in findings if f["level"] == "warning"),
    }


def all_types(items: list) -> list[str]:
    out: list[str] = []

    def walk(node, depth=0):
        if isinstance(node, dict) and depth < 6:
            out.extend(_types(node))
            for v in node.values():
                walk(v, depth + 1)
        elif isinstance(node, list):
            for v in node[:50]:
                walk(v, depth + 1)

    walk(items)
    return list(dict.fromkeys(out))


TEMPLATES: dict[str, dict] = {
    "Organization": {"@type": "Organization", "name": "", "url": "", "logo": "", "sameAs": [""],
                     "contactPoint": {"@type": "ContactPoint", "telephone": "", "contactType": "customer service"}},
    "LocalBusiness": {"@type": "LocalBusiness", "name": "", "image": "", "url": "", "telephone": "", "priceRange": "",
                      "address": {"@type": "PostalAddress", "streetAddress": "", "addressLocality": "", "addressRegion": "", "postalCode": "", "addressCountry": ""},
                      "geo": {"@type": "GeoCoordinates", "latitude": "", "longitude": ""},
                      "openingHoursSpecification": [{"@type": "OpeningHoursSpecification", "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "opens": "09:00", "closes": "17:00"}]},
    "Product": {"@type": "Product", "name": "", "image": [""], "description": "", "sku": "", "brand": {"@type": "Brand", "name": ""},
                "offers": {"@type": "Offer", "url": "", "priceCurrency": "USD", "price": "", "availability": "https://schema.org/InStock"}},
    "Article": {"@type": "Article", "headline": "", "image": [""], "datePublished": "", "dateModified": "",
                "author": {"@type": "Person", "name": "", "url": ""}, "publisher": {"@type": "Organization", "name": "", "logo": {"@type": "ImageObject", "url": ""}}},
    "BlogPosting": {"@type": "BlogPosting", "headline": "", "image": [""], "datePublished": "", "dateModified": "",
                    "author": {"@type": "Person", "name": "", "url": ""}, "publisher": {"@type": "Organization", "name": "", "logo": {"@type": "ImageObject", "url": ""}}},
    "BreadcrumbList": {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": ""}, {"@type": "ListItem", "position": 2, "name": "", "item": ""}]},
    "FAQPage": {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": "", "acceptedAnswer": {"@type": "Answer", "text": ""}}]},
    "WebSite": {"@type": "WebSite", "name": "", "url": "",
                "potentialAction": {"@type": "SearchAction", "target": {"@type": "EntryPoint", "urlTemplate": "https://example.com/search?q={search_term_string}"}, "query-input": "required name=search_term_string"}},
    "WebPage": {"@type": "WebPage", "name": "", "url": "", "description": "", "isPartOf": {"@type": "WebSite", "name": "", "url": ""}},
    "Service": {"@type": "Service", "name": "", "serviceType": "", "description": "", "provider": {"@type": "Organization", "name": ""}, "areaServed": ""},
    "Person": {"@type": "Person", "name": "", "url": "", "image": "", "jobTitle": "", "worksFor": {"@type": "Organization", "name": ""}, "sameAs": [""]},
    "Event": {"@type": "Event", "name": "", "startDate": "", "endDate": "", "eventStatus": "https://schema.org/EventScheduled",
              "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
              "location": {"@type": "Place", "name": "", "address": {"@type": "PostalAddress", "streetAddress": "", "addressLocality": "", "postalCode": "", "addressCountry": ""}},
              "description": "", "image": [""], "organizer": {"@type": "Organization", "name": "", "url": ""},
              "offers": {"@type": "Offer", "url": "", "price": "", "priceCurrency": "USD", "availability": "https://schema.org/InStock"}},
}


def _fill(template: Any, values: dict[str, Any]) -> Any:
    if isinstance(template, dict):
        out = {}
        for k, v in template.items():
            if k in values and values[k] not in (None, ""):
                out[k] = values[k]
            else:
                out[k] = _fill(v, values.get(k, {}) if isinstance(values.get(k), dict) else {})
        return out
    return template


def generate_template(schema_type: str, values: dict[str, Any] | None = None) -> dict:
    if schema_type not in TEMPLATES:
        raise KeyError(schema_type)
    doc = {"@context": "https://schema.org"}
    doc.update(_fill(TEMPLATES[schema_type], values or {}))
    return doc


def recommend_types(page: dict) -> list[dict]:
    """Suggest schema types from observable page signals. ``page`` needs url, title, depth, types, text flags."""
    have = set(page.get("types", []))
    recs: list[dict] = []
    url = (page.get("url") or "").lower()
    if page.get("depth") == 0:
        if not have & {"Organization", "LocalBusiness", "Corporation"}:
            recs.append({"type": "Organization", "reason": "Home page without Organization markup"})
        if "WebSite" not in have:
            recs.append({"type": "WebSite", "reason": "Home page without WebSite markup"})
    elif "BreadcrumbList" not in have and (page.get("depth") or 0) >= 1:
        recs.append({"type": "BreadcrumbList", "reason": "Inner page without breadcrumb markup"})
    if any(s in url for s in ("/blog/", "/news/", "/article", "/post")) and not have & {"Article", "BlogPosting", "NewsArticle"}:
        recs.append({"type": "BlogPosting", "reason": "URL looks like an article"})
    if any(s in url for s in ("/product", "/shop/", "/item/")) and "Product" not in have:
        recs.append({"type": "Product", "reason": "URL looks like a product page"})
    if page.get("question_headings", 0) >= 3 and "FAQPage" not in have:
        recs.append({"type": "FAQPage", "reason": f"{page['question_headings']} headings are phrased as questions"})
    if any(s in url for s in ("/contact", "/location", "/store")) and not have & LOCAL_TYPES:
        recs.append({"type": "LocalBusiness", "reason": "Contact/location page without LocalBusiness markup"})
    if any(s in url for s in ("/service",)) and "Service" not in have:
        recs.append({"type": "Service", "reason": "URL looks like a service page"})
    if any(s in url for s in ("/event",)) and "Event" not in have:
        recs.append({"type": "Event", "reason": "URL looks like an event page"})
    return recs
