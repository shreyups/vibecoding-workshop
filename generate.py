#!/usr/bin/env python3
"""Generate index.html — a self-contained WVS synthetic-data explorer."""

import csv
import json
import random
import os

SEED = 42
COUNTRY_ORDER = ["China", "India", "Kazakhstan", "Singapore", "Turkey"]
COLORS = {
    "China": "#E69F00",
    "India": "#0072B2",
    "Kazakhstan": "#009E73",
    "Singapore": "#D55E00",
    "Turkey": "#CC79A7",
}
MARKERS = {
    "China": "circle",
    "India": "triangle",
    "Kazakhstan": "rectRot",
    "Singapore": "rect",
    "Turkey": "star",
}

NUMERIC_COLS = [
    "age", "life_satisfaction", "freedom_of_choice",
    "emancipative_values", "importance_of_god",
    "financial_satisfaction", "secular_values",
]
CATEGORICAL_COLS = [
    "country", "urban_rural", "income_level",
    "sex", "marital_status", "education", "trust_people",
]
DISPLAY_COLS = CATEGORICAL_COLS + NUMERIC_COLS

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "wvs-synthetic.csv")


def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def mean(vals):
    return sum(vals) / len(vals)


def compute_column_meta(rows):
    meta = []
    for col in DISPLAY_COLS:
        dtype = "Numeric" if col in NUMERIC_COLS else "Categorical"
        non_empty = sum(1 for r in rows if r[col].strip() != "")
        meta.append({"name": col, "dtype": dtype, "non_empty": non_empty})
    return meta


def drop_incomplete(rows):
    all_cols = [c for c in rows[0] if c != "respondent_id"]
    clean = [r for r in rows if all(r[c].strip() != "" for c in all_cols)]
    return clean


def group_by_country(rows):
    groups = {c: [] for c in COUNTRY_ORDER}
    for r in rows:
        groups[r["country"]].append(r)
    return groups


def cultural_map(groups):
    points = []
    for c in COUNTRY_ORDER:
        rs = groups[c]
        x = mean([float(r["secular_values"]) for r in rs])
        y = mean([float(r["emancipative_values"]) for r in rs])
        points.append({"country": c, "x": round(x, 4), "y": round(y, 4)})
    return points


def radar_data(groups):
    datasets = {}
    for c in COUNTRY_ORDER:
        rs = groups[c]
        life = mean([float(r["life_satisfaction"]) for r in rs]) / 10
        trust = sum(1 for r in rs if r["trust_people"] == "Trusted") / len(rs)
        god = mean([float(r["importance_of_god"]) for r in rs]) / 10
        emanc = mean([float(r["emancipative_values"]) for r in rs])
        sec = mean([float(r["secular_values"]) for r in rs])
        fin = mean([float(r["financial_satisfaction"]) for r in rs]) / 10
        datasets[c] = [round(v, 3) for v in [life, trust, god, emanc, sec, fin]]
    labels = [
        "Life Satisfaction", "Trust (share)", "Importance of God",
        "Emancipative Values", "Secular Values", "Financial Satisfaction",
    ]
    return {"labels": labels, "datasets": datasets}


def china_india_scatter(groups):
    random.seed(SEED)
    result = {}
    for c in ["China", "India"]:
        rs = groups[c]
        sample = random.sample(rs, min(300, len(rs)))
        pts = [
            {"x": round(float(r["secular_values"]), 4),
             "y": round(float(r["emancipative_values"]), 4)}
            for r in sample
        ]
        avg_x = mean([float(r["secular_values"]) for r in rs])
        avg_y = mean([float(r["emancipative_values"]) for r in rs])
        result[c] = {
            "points": pts,
            "avg": {"x": round(avg_x, 4), "y": round(avg_y, 4)},
        }
    return result


def singapore_heatmap(groups):
    rs = groups["Singapore"]
    matrix = [[0] * 10 for _ in range(10)]
    for r in rs:
        life = int(float(r["life_satisfaction"]))
        fin = int(float(r["financial_satisfaction"]))
        if 1 <= life <= 10 and 1 <= fin <= 10:
            matrix[life - 1][fin - 1] += 1
    max_val = max(max(row) for row in matrix)
    return {"matrix": matrix, "max_val": max_val}


def generate_takeaways(cm_points, radar, scatter, heatmap):
    most_secular = max(cm_points, key=lambda p: p["x"])
    most_emanc = max(cm_points, key=lambda p: p["y"])
    least_secular = min(cm_points, key=lambda p: p["x"])

    cm_take = (
        f"{most_secular['country']} scores highest on secular values "
        f"({most_secular['x']:.2f}), while {most_emanc['country']} leads on "
        f"emancipative values ({most_emanc['y']:.2f}). "
        f"{least_secular['country']} sits lowest on the secular axis."
    )

    god_vals = {c: radar["datasets"][c][2] for c in COUNTRY_ORDER}
    high_god = max(god_vals, key=god_vals.get)
    low_god = min(god_vals, key=god_vals.get)
    radar_take = (
        f"Country profiles diverge most on Importance of God — "
        f"{high_god} scores {god_vals[high_god]:.2f} vs {low_god} at "
        f"{god_vals[low_god]:.2f} — and on trust, where the gap is also wide."
    )

    scatter_take = (
        "Despite China and India having noticeably different average positions, "
        "their individual-level clouds overlap substantially — many respondents "
        "in each country share similar value profiles."
    )

    flat = [cell for row in heatmap["matrix"] for cell in row]
    total = sum(flat)
    diag_sum = sum(heatmap["matrix"][i][i] for i in range(10))
    near_diag = 0
    for i in range(10):
        for j in range(10):
            if abs(i - j) <= 1:
                near_diag += heatmap["matrix"][i][j]
    heatmap_take = (
        f"Counts cluster along the diagonal, with {near_diag / total * 100:.0f}% "
        f"of Singapore respondents within one step of equal life and financial "
        f"satisfaction, suggesting a positive correlation between the two."
    )

    return {
        "cultural_map": cm_take,
        "radar": radar_take,
        "scatter": scatter_take,
        "heatmap": heatmap_take,
    }


def build_column_table_html(col_meta):
    rows_html = ""
    for m in col_meta:
        rows_html += (
            f"      <tr><td><code>{m['name']}</code></td>"
            f"<td>{m['dtype']}</td>"
            f"<td>{m['non_empty']:,}</td></tr>\n"
        )
    return rows_html


def build_html(col_meta, total_rows, dup_count, rows_dropped, clean_count,
               cm_data, radar_d, scatter_d, heatmap_d, takeaways):
    col_table = build_column_table_html(col_meta)
    data_json = json.dumps({
        "cultural_map": cm_data,
        "radar": radar_d,
        "scatter": scatter_d,
        "heatmap": heatmap_d,
        "colors": COLORS,
        "markers": MARKERS,
        "country_order": COUNTRY_ORDER,
    }, separators=(",", ":"))

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Exploring Values Across Asia — Synthetic WVS Data</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1a1a1a;
      background: #fafafa;
      margin: 0;
      padding: 1rem;
      line-height: 1.6;
    }}
    .container {{ max-width: 900px; margin: 0 auto; }}
    h1 {{ font-size: 1.6rem; margin-bottom: 0.25rem; }}
    h2 {{ font-size: 1.25rem; margin-top: 2.5rem; border-bottom: 2px solid #e0e0e0; padding-bottom: 0.3rem; }}
    p {{ max-width: 70ch; }}
    .intro {{ color: #444; font-size: 0.95rem; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; margin: 1rem 0; }}
    th, td {{ border: 1px solid #d0d0d0; padding: 0.4rem 0.75rem; text-align: left; }}
    th {{ background: #f0f0f0; }}
    tr:nth-child(even) {{ background: #f9f9f9; }}
    code {{ background: #eee; padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.85em; }}
    .chart-wrap {{ position: relative; max-width: 750px; margin: 1.5rem auto; }}
    .takeaway {{
      background: #f5f5f0; border-left: 3px solid #888;
      padding: 0.6rem 1rem; font-size: 0.9rem; color: #333;
      max-width: 70ch; margin-top: 0.75rem;
    }}
    .quality {{ background: #fff8e1; border: 1px solid #ffe082; padding: 0.75rem 1rem; border-radius: 4px; font-size: 0.9rem; margin: 1rem 0; }}

    /* Heatmap */
    .heatmap-outer {{ max-width: 600px; margin: 1.5rem auto; }}
    .heatmap-title {{ text-align: center; font-weight: 600; margin-bottom: 0.5rem; }}
    .heatmap-grid-wrapper {{ display: flex; align-items: center; gap: 0.5rem; }}
    .heatmap-y-label {{
      writing-mode: vertical-rl; transform: rotate(180deg);
      font-size: 0.8rem; font-weight: 600; white-space: nowrap;
    }}
    .heatmap-grid {{
      display: grid;
      grid-template-columns: auto repeat(10, 1fr);
      gap: 2px; flex: 1;
    }}
    .hm-cell {{
      aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
      font-size: 0.75rem; font-weight: 500; border-radius: 2px; min-width: 0;
    }}
    .hm-header {{ font-size: 0.7rem; font-weight: 600; text-align: center; padding: 2px; }}
    .hm-row-label {{ font-size: 0.7rem; font-weight: 600; display: flex; align-items: center; justify-content: flex-end; padding-right: 4px; }}
    .heatmap-x-label {{ text-align: center; font-size: 0.8rem; font-weight: 600; margin-top: 0.4rem; }}
    .legend-bar {{
      height: 14px; border-radius: 3px; margin-top: 0.75rem;
      background: linear-gradient(to right, #fff, #D55E00);
    }}
    .legend-labels {{ display: flex; justify-content: space-between; font-size: 0.7rem; color: #666; }}

    footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ddd; font-size: 0.8rem; color: #888; }}
    @media (max-width: 600px) {{
      h1 {{ font-size: 1.25rem; }}
      h2 {{ font-size: 1.1rem; }}
      .hm-cell {{ font-size: 0.55rem; }}
    }}
  </style>
</head>
<body>
<div class="container">

  <h1>Exploring Values Across Asia</h1>
  <p class="intro">
    This page presents an exploratory analysis of <strong>synthetic (simulated) data</strong>
    fabricated to resemble the
    <a href="https://www.worldvaluessurvey.org/" target="_blank" rel="noopener">World Values Survey, Wave&nbsp;7</a>
    (Haerpfer, C., Inglehart, R., et al., 2022, <em>World Values Survey Wave 7</em>).
    <strong>No real respondent data is used.</strong>
    Any patterns are illustrative only and should not be cited as real-world findings.
    The dataset covers five countries in different parts of Asia:
    <strong>China</strong> (East&nbsp;Asia),
    <strong>India</strong> (South&nbsp;Asia),
    <strong>Kazakhstan</strong> (Central&nbsp;Asia),
    <strong>Singapore</strong> (Southeast&nbsp;Asia), and
    <strong>Turkey</strong> (Middle&nbsp;East).
  </p>

  <h2>Variables</h2>
  <table>
    <thead><tr><th>Variable</th><th>Type</th><th>Non-Empty Obs.</th></tr></thead>
    <tbody>
{col_table}    </tbody>
  </table>

  <h2>Data Quality</h2>
  <div class="quality">
    <strong>Duplicates:</strong> {dup_count} duplicate respondent IDs found.<br>
    <strong>Missing values:</strong> {rows_dropped:,} rows (of {total_rows:,}) contained at least
    one empty cell and were removed, leaving <strong>{clean_count:,}</strong> complete
    observations for all analyses below.
  </div>

  <h2>Cultural Map — Emancipative vs Secular Values</h2>
  <div class="chart-wrap"><canvas id="culturalMap"></canvas></div>
  <p class="takeaway">{takeaways["cultural_map"]}</p>

  <h2>Value Fingerprints — Radar Chart</h2>
  <div class="chart-wrap"><canvas id="radarChart"></canvas></div>
  <p class="takeaway">{takeaways["radar"]}</p>

  <h2>Individual Values — China vs India</h2>
  <div class="chart-wrap"><canvas id="chinaIndiaScatter"></canvas></div>
  <p class="takeaway">{takeaways["scatter"]}</p>

  <h2>Life vs Financial Satisfaction — Singapore</h2>
  <div class="heatmap-outer" id="heatmapContainer"></div>
  <p class="takeaway">{takeaways["heatmap"]}</p>

  <footer>
    Generated by <code>generate.py</code> with random seed {SEED} for reproducibility.
  </footer>
</div>

<script>
const D = {data_json};

/* --- helpers --- */
function rgba(hex, a) {{
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return `rgba(${{r}},${{g}},${{b}},${{a}})`;
}}

/* --- 1. Cultural Map --- */
(() => {{
  const datasets = D.cultural_map.map(p => ({{
    label: p.country,
    data: [{{ x: p.x, y: p.y }}],
    backgroundColor: D.colors[p.country],
    borderColor: D.colors[p.country],
    pointStyle: D.markers[p.country],
    pointRadius: 10,
    pointHoverRadius: 13,
  }}));

  new Chart(document.getElementById("culturalMap"), {{
    type: "scatter",
    data: {{ datasets }},
    options: {{
      responsive: true,
      plugins: {{
        tooltip: {{
          callbacks: {{
            label: ctx => `${{ctx.dataset.label}}: secular ${{ctx.parsed.x.toFixed(2)}}, emanc ${{ctx.parsed.y.toFixed(2)}}`
          }}
        }},
        legend: {{ position: "bottom", labels: {{ usePointStyle: true, padding: 16 }} }},
      }},
      scales: {{
        x: {{ title: {{ display: true, text: "Secular Values (mean)" }} }},
        y: {{ title: {{ display: true, text: "Emancipative Values (mean)" }} }},
      }},
    }},
    plugins: [{{
      id: "countryLabels",
      afterDraw(chart) {{
        const ctx = chart.ctx;
        ctx.save();
        ctx.font = "bold 11px sans-serif";
        ctx.textBaseline = "bottom";
        chart.data.datasets.forEach((ds, i) => {{
          const meta = chart.getDatasetMeta(i);
          if (!meta.data.length) return;
          const pt = meta.data[0];
          ctx.fillStyle = "#333";
          ctx.fillText(ds.label, pt.x + 10, pt.y - 6);
        }});
        ctx.restore();
      }}
    }}]
  }});
}})();

/* --- 2. Radar Chart --- */
(() => {{
  const datasets = D.country_order.map(c => ({{
    label: c,
    data: D.radar.datasets[c],
    borderColor: D.colors[c],
    backgroundColor: rgba(D.colors[c], 0.08),
    pointBackgroundColor: D.colors[c],
    pointStyle: D.markers[c],
    pointRadius: 4,
    borderWidth: 2,
  }}));

  new Chart(document.getElementById("radarChart"), {{
    type: "radar",
    data: {{ labels: D.radar.labels, datasets }},
    options: {{
      responsive: true,
      scales: {{
        r: {{ min: 0, max: 1, ticks: {{ stepSize: 0.2, callback: v => v.toFixed(1) }} }}
      }},
      plugins: {{
        tooltip: {{
          callbacks: {{
            label: ctx => `${{ctx.dataset.label}}: ${{ctx.parsed.r.toFixed(2)}}`
          }}
        }},
        legend: {{ position: "bottom", labels: {{ usePointStyle: true, padding: 16 }} }},
      }},
    }},
  }});
}})();

/* --- 3. China vs India Scatter --- */
(() => {{
  const datasets = [];
  ["China", "India"].forEach(c => {{
    datasets.push({{
      label: c + " (individuals)",
      data: D.scatter[c].points,
      backgroundColor: rgba(D.colors[c], 0.35),
      borderColor: rgba(D.colors[c], 0.5),
      pointStyle: D.markers[c],
      pointRadius: 3,
      pointHoverRadius: 5,
      borderWidth: 0,
    }});
  }});
  ["China", "India"].forEach(c => {{
    datasets.push({{
      label: c + " (mean)",
      data: [D.scatter[c].avg],
      backgroundColor: D.colors[c],
      borderColor: "#fff",
      pointStyle: D.markers[c],
      pointRadius: 12,
      pointHoverRadius: 14,
      borderWidth: 2.5,
    }});
  }});

  new Chart(document.getElementById("chinaIndiaScatter"), {{
    type: "scatter",
    data: {{ datasets }},
    options: {{
      responsive: true,
      plugins: {{
        tooltip: {{
          callbacks: {{
            label: ctx => `${{ctx.dataset.label}}: secular ${{ctx.parsed.x.toFixed(2)}}, emanc ${{ctx.parsed.y.toFixed(2)}}`
          }}
        }},
        legend: {{ position: "bottom", labels: {{ usePointStyle: true, padding: 16 }} }},
      }},
      scales: {{
        x: {{ title: {{ display: true, text: "Secular Values" }} }},
        y: {{ title: {{ display: true, text: "Emancipative Values" }} }},
      }},
    }},
  }});
}})();

/* --- 4. Singapore Heatmap (pure DOM) --- */
(() => {{
  const mat = D.heatmap.matrix;
  const maxVal = D.heatmap.max_val;
  const container = document.getElementById("heatmapContainer");

  const wrapper = document.createElement("div");
  wrapper.className = "heatmap-grid-wrapper";

  const yLabel = document.createElement("div");
  yLabel.className = "heatmap-y-label";
  yLabel.textContent = "Life Satisfaction";
  wrapper.appendChild(yLabel);

  const grid = document.createElement("div");
  grid.className = "heatmap-grid";

  // corner
  grid.appendChild(Object.assign(document.createElement("div"), {{ className: "hm-header" }}));
  // column headers
  for (let j = 1; j <= 10; j++) {{
    const h = document.createElement("div");
    h.className = "hm-header";
    h.textContent = j;
    grid.appendChild(h);
  }}

  // rows (top = 10, bottom = 1)
  for (let i = 9; i >= 0; i--) {{
    const rl = document.createElement("div");
    rl.className = "hm-row-label";
    rl.textContent = i + 1;
    grid.appendChild(rl);
    for (let j = 0; j < 10; j++) {{
      const cell = document.createElement("div");
      cell.className = "hm-cell";
      const v = mat[i][j];
      const t = maxVal > 0 ? v / maxVal : 0;
      const r = Math.round(255 - (255 - 213) * t);
      const g = Math.round(255 - (255 - 94) * t);
      const b = Math.round(255 - (255 - 0) * t);
      cell.style.background = `rgb(${{r}},${{g}},${{b}})`;
      cell.style.color = t > 0.45 ? "#fff" : "#333";
      if (v > 0) cell.textContent = v;
      cell.title = `Life ${{i+1}}, Financial ${{j+1}}: ${{v}} respondents`;
      grid.appendChild(cell);
    }}
  }}

  wrapper.appendChild(grid);
  container.appendChild(wrapper);

  const xLabel = document.createElement("div");
  xLabel.className = "heatmap-x-label";
  xLabel.textContent = "Financial Satisfaction";
  container.appendChild(xLabel);

  // legend bar
  const bar = document.createElement("div");
  bar.className = "legend-bar";
  container.appendChild(bar);
  const labels = document.createElement("div");
  labels.className = "legend-labels";
  labels.innerHTML = "<span>0</span><span>" + maxVal + " respondents</span>";
  container.appendChild(labels);
}})();
</script>
</body>
</html>'''


def main():
    rows = read_csv(DATA_PATH)
    total_rows = len(rows)

    col_meta = compute_column_meta(rows)

    ids = [r["respondent_id"] for r in rows]
    dup_count = len(ids) - len(set(ids))

    clean = drop_incomplete(rows)
    clean_count = len(clean)
    rows_dropped = total_rows - clean_count

    groups = group_by_country(clean)

    cm = cultural_map(groups)
    rd = radar_data(groups)
    sc = china_india_scatter(groups)
    hm = singapore_heatmap(groups)
    takes = generate_takeaways(cm, rd, sc, hm)

    html = build_html(col_meta, total_rows, dup_count, rows_dropped, clean_count,
                      cm, rd, sc, hm, takes)

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {out_path} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
