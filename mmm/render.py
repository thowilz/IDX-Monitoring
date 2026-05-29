"""Static HTML dashboard renderer (non-developer friendly, zero JS deps).

Design rules straight from the anti-hallucination section:
  * every indicator shows its data AGE and its source link;
  * data older than its cadence is flagged loudly;
  * STALE / UNKNOWN / SUSPECT get distinct, obvious styling;
  * proxy indicators are labelled "PROXY", never disguised as the real thing.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, List

from jinja2 import Environment, BaseLoader

from .contract import Module
from .observation import OK, STALE, UNKNOWN, SUSPECT

# How long until a value of a given cadence is "overdue" (seconds).
CADENCE_MAX_AGE = {
    "intraday": 6 * 3600,
    "daily": 36 * 3600,
    "weekly": 9 * 86400,
    "biweekly": 18 * 86400,
    "monthly": 40 * 86400,
    "quarterly": 100 * 86400,
}


def _age(fetched_at: str):
    try:
        dt = datetime.fromisoformat(fetched_at)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds()


def _fmt_value(raw):
    """Display values without false precision (PRINSIP INTI #6).

    Round to a sensible number of significant places and strip trailing zeros,
    so 99.02400207519531 -> "99.02" and 17878.0 -> "17,878". Non-numeric or
    empty values pass through unchanged.
    """
    if raw in ("", None):
        return raw
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return raw
    av = abs(v)
    if av >= 1000:
        return f"{v:,.0f}"          # FX rates, reserves, big indices
    elif av >= 100:
        return f"{v:,.1f}".rstrip("0").rstrip(".")
    else:
        return f"{v:,.2f}".rstrip("0").rstrip(".")  # yields, DXY, small marks


def _fmt_age(sec):
    if sec is None:
        return "—"
    if sec < 3600:
        return f"{int(sec // 60)}m"
    if sec < 86400:
        return f"{int(sec // 3600)}h"
    return f"{int(sec // 86400)}d"


_TEMPLATE = """<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>IHSG Macro Monitor</title>
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:#0f1115;color:#e8e8ea}
 header{padding:18px 24px;background:#161922;border-bottom:1px solid #262b36}
 h1{margin:0;font-size:20px} .sub{color:#9aa0aa;font-size:13px;margin-top:4px}
 .wrap{padding:16px 24px;max-width:1200px} .mod{background:#161922;border:1px solid #262b36;border-radius:10px;margin:16px 0;overflow:hidden}
 .mhead{padding:12px 16px;border-bottom:1px solid #262b36;display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px}
 .mhead h2{margin:0;font-size:16px} .ver{color:#7c8696;font-size:12px}
 table{width:100%;border-collapse:collapse;font-size:13px} th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #20242e;vertical-align:top}
 th{color:#9aa0aa;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
 .badge{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;font-weight:600}
 .ok{background:#10381f;color:#5fe08a} .stale{background:#3a1414;color:#ff8a8a} .unknown{background:#2c2c10;color:#e0d35f}
 .suspect{background:#3a2410;color:#ffae5f} .lead{color:#6fb0ff} .coin{color:#7ee0c2} .lag{color:#c79bff}
 .proxy{background:#22263a;color:#9fb4ff;margin-left:6px} .overdue{color:#ff8a8a;font-weight:700}
 .val{font-variant-numeric:tabular-nums;font-weight:600} a{color:#7fb0ff;text-decoration:none} a:hover{text-decoration:underline}
 .sig{padding:10px 16px;border-bottom:1px solid #262b36;font-size:13px} .sig b{color:#fff}
 .zone-stres,.zone-stress{color:#ff8a8a} .zone-waspada{color:#ffae5f} .zone-normal{color:#5fe08a} .zone-no-data{color:#9aa0aa}
 details{padding:8px 16px;border-bottom:1px solid #20242e} summary{cursor:pointer;color:#9aa0aa;font-size:12px}
 .trans td{font-size:12px} .lim li{color:#c7ccd6;font-size:12px;margin:3px 0} .foot{color:#6b7280;font-size:11px;padding:16px 24px}
 code{background:#20242e;padding:1px 5px;border-radius:4px;font-size:12px}
 .composite{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;
   padding:14px 16px;border-bottom:1px solid #262b36;background:#12161f}
 .composite .verdict{font-size:22px;font-weight:800;letter-spacing:-.01em}
 .composite .vsub{color:#9aa0aa;font-size:12px;margin-top:2px}
 .composite .score{font-family:ui-monospace,monospace;font-size:13px;color:#9aa0aa}
 .composite .score b{font-size:26px;color:#fff}
 .vpos{color:#5fe08a} .vneg{color:#ff8a8a} .vneu{color:#ffae5f}
 .comps{display:flex;flex-wrap:wrap;gap:8px;padding:10px 16px;border-bottom:1px solid #20242e}
 .cchip{font-size:11.5px;padding:3px 9px;border-radius:8px;background:#20242e;color:#c7ccd6}
 .cchip b{margin-left:6px} .pos{color:#5fe08a} .neg{color:#ff8a8a} .neu{color:#ffae5f}
 .ladder{counter-reset:step;list-style:none;padding:6px 16px 12px}
 .ladder li{font-size:12.5px;color:#c7ccd6;margin:5px 0;padding-left:26px;position:relative}
 .ladder li::before{counter-increment:step;content:counter(step);position:absolute;left:0;top:0;
   width:18px;height:18px;border-radius:50%;background:#22263a;color:#9fb4ff;font-size:11px;
   text-align:center;line-height:18px;font-weight:700}
 .ladder li.warn{color:#ffae5f} .ladder li.warn::before{content:"!";background:#3a2410;color:#ffae5f}
</style></head><body>
<header><h1>IHSG Macro Monitoring System</h1>
<div class="sub">Generated {{ generated_at }} UTC · {{ modules|length }} active module(s) ·
taxonomy: <code>{{ taxonomy_source }}</code> · <b>not investment advice — engineering monitor</b></div>
</header>
<div class="wrap">
{% for m in modules %}
 <div class="mod">
  <div class="mhead"><h2>{{ m.domain }} <span class="ver">{{ m.id }} v{{ m.version }}</span></h2>
   <span class="ver">last refresh: {{ m.last_refresh }}</span></div>

  {% if m.composite %}
   <div class="composite">
    <div><div class="verdict v{{ m.composite.verdict_class }}">{{ m.composite.verdict }}</div>
      <div class="vsub">{{ m.composite.subtitle }}</div></div>
    <div class="score">score <b class="v{{ m.composite.verdict_class }}">{{ '%+d'|format(m.composite.score) }}</b> / ±{{ m.composite.max }}</div>
   </div>
   <div class="comps">
    {% for c in m.composite.components %}
     <span class="cchip">{{ c.label }}<b class="{{ c.cls }}">{{ c.contribution }}</b></span>
    {% endfor %}
   </div>
  {% endif %}

  {% for s in m.signals %}
   <div class="sig">Regime · <b>{{ s.indicator }}</b>:
     <span class="zone-{{ s.zone }}">{{ s.zone|upper }}</span> — {{ s.meaning }}</div>
  {% endfor %}

  <table><thead><tr>
    <th>Indicator</th><th>Class</th><th>Value</th><th>As of</th><th>Age</th>
    <th>Status</th><th>Cadence</th><th>Authority / Access</th><th>Source</th>
  </tr></thead><tbody>
  {% for r in m.rows %}
   <tr>
    <td>{{ r.label }}{% if r.is_proxy %}<span class="badge proxy">PROXY</span>{% endif %}
        {% if r.note %}<div class="ver">{{ r.note }}</div>{% endif %}</td>
    <td class="{{ r.cls_css }}">{{ r.classification }}</td>
    <td class="val">{% if r.value != '' and r.value is not none %}{{ r.value }} <span class="ver">{{ r.unit }}</span>{% else %}—{% endif %}</td>
    <td>{{ r.ts or '—' }}</td>
    <td class="{{ 'overdue' if r.overdue }}">{{ r.age }}{% if r.overdue %} ⚠{% endif %}</td>
    <td><span class="badge {{ r.status_css }}">{{ r.status }}</span></td>
    <td>{{ r.cadence }}</td>
    <td>{{ r.authority }} / {{ r.access }}</td>
    <td><a href="{{ r.source }}" target="_blank" rel="noopener">link</a></td>
   </tr>
  {% endfor %}
  </tbody></table>

  {% if m.derived %}
  <details open><summary>Derived metrics ({{ m.derived|length }}) — computed, not fetched</summary>
   <table><thead><tr><th>Metric</th><th>Class</th><th>Value</th><th>Status</th><th>Basis</th></tr></thead><tbody>
   {% for d in m.derived %}
    <tr><td>{{ d.label }}</td><td class="{{ d.cls_css }}">{{ d.classification }}</td>
        <td class="val">{% if d.value != '' and d.value is not none %}{{ d.value }} <span class="ver">{{ d.unit }}</span>{% else %}—{% endif %}</td>
        <td><span class="badge {{ d.status_css }}">{{ d.status }}</span></td>
        <td class="ver">{{ d.note }}</td></tr>
   {% endfor %}
   </tbody></table></details>
  {% endif %}

  {% if m.signal_hierarchy %}
  <details><summary>Signal hierarchy — the reversal/confirmation sequence to read</summary>
   <ol class="ladder">{% for step in m.signal_hierarchy %}
     <li class="{{ 'warn' if step.startswith('⚠') }}">{{ step.lstrip('⚠ ') }}</li>
   {% endfor %}</ol></details>
  {% endif %}

  <details><summary>Transmission map → IHSG sectors ({{ m.transmission|length }})</summary>
   <table class="trans"><thead><tr><th>Industri</th><th>Sektor</th><th>Arah</th>
     <th>Mekanisme</th><th>Emiten sensitif</th><th>Taxonomy?</th></tr></thead><tbody>
   {% for t in m.transmission %}
    <tr><td><code>{{ t.industri }}</code></td><td>{{ t.sektor }}</td><td>{{ t.direction }}</td>
        <td>{{ t.mechanism }}</td><td>{{ t.sensitive_emiten|join(', ') }}</td>
        <td>{{ '✓' if t.in_taxonomy else ('—' if not taxonomy_available else '✗ unknown code') }}</td></tr>
   {% endfor %}
   </tbody></table></details>

  <details><summary>Limitations ({{ m.limitations|length }})</summary>
   <ul class="lim">{% for l in m.limitations %}<li>{{ l }}</li>{% endfor %}</ul></details>
 </div>
{% endfor %}
</div>
<div class="foot">Anti-hallucination: every value carries a source + fetch timestamp. Failed fetches show
<span class="badge stale">STALE</span>, never a guessed number. Overdue (age &gt; cadence) is flagged ⚠.
Proxies are labelled and are not the paywalled ideal source.</div>
</body></html>"""

_CLS_CSS = {"LEADING": "lead", "COINCIDENT": "coin", "LAGGING": "lag"}
_STATUS_CSS = {OK: "ok", STALE: "stale", UNKNOWN: "unknown", SUSPECT: "suspect"}


def build_render(root: str, modules_payload: List[dict], taxonomy) -> str:
    env = Environment(loader=BaseLoader(), autoescape=True)
    tmpl = env.from_string(_TEMPLATE)
    html = tmpl.render(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        modules=modules_payload,
        taxonomy_source=taxonomy.source,
        taxonomy_available=taxonomy.available,
    )
    out_dir = os.path.join(root, "render")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w") as fh:
        fh.write(html)
    return out_path


def assemble_module_payload(module: Module, latest: Dict[str, dict],
                            signals: List[dict], taxonomy, last_refresh: str,
                            composite: dict = None) -> dict:
    rows = []
    for ind in module.indicators:
        row = latest.get(ind.id, {})
        fetched_at = row.get("fetched_at", "")
        age_sec = _age(fetched_at) if fetched_at else None
        max_age = CADENCE_MAX_AGE.get(ind.cadence)
        status = row.get("status", "UNKNOWN")
        overdue = bool(age_sec and max_age and age_sec > max_age and status == OK)
        rows.append({
            "label": ind.label,
            "classification": ind.classification,
            "cls_css": _CLS_CSS.get(ind.classification, ""),
            "value": _fmt_value(row.get("value", "")),
            "unit": ind.unit,
            "ts": row.get("ts", ""),
            "age": _fmt_age(age_sec),
            "overdue": overdue,
            "status": status,
            "status_css": _STATUS_CSS.get(status, "unknown"),
            "cadence": ind.cadence,
            "authority": ind.authority,
            "access": ind.access,
            "source": row.get("source", ind.url),
            "is_proxy": ind.is_proxy,
            "note": row.get("note", "") or ind.note,
        })
    # derived metrics (computed, not fetched)
    derived = []
    for dm in getattr(module, "derived", []):
        row = latest.get(dm.id, {})
        status = row.get("status", "UNKNOWN")
        derived.append({
            "label": dm.label,
            "classification": dm.classification,
            "cls_css": _CLS_CSS.get(dm.classification, ""),
            "value": _fmt_value(row.get("value", "")),
            "unit": dm.unit,
            "status": status,
            "status_css": _STATUS_CSS.get(status, "unknown"),
            "note": row.get("note", "") or dm.note,
        })
    transmission = []
    for t in module.transmission:
        transmission.append({
            "industri": t.industri, "sektor": t.sektor, "direction": t.direction,
            "mechanism": t.mechanism, "sensitive_emiten": t.sensitive_emiten,
            "in_taxonomy": taxonomy.has_industry(t.industri) if taxonomy.available else False,
        })
    return {
        "id": module.id, "version": module.version, "domain": module.domain,
        "rows": rows, "signals": signals, "transmission": transmission,
        "limitations": module.limitations, "last_refresh": last_refresh or "—",
        "derived": derived, "composite": composite,
        "signal_hierarchy": getattr(module, "signal_hierarchy", []),
    }
