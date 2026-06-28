"""
Génère dashboard/index.html — dashboard HTML autonome à partir de db/mspr.db
"""
import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'mspr.db')
OUT_PATH = os.path.join(os.path.dirname(__file__), 'index.html')

# ---------------------------------------------------------------------------
# Extraction données
# ---------------------------------------------------------------------------

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

def q(sql, *args):
    return conn.execute(sql, args).fetchall()

# Départements
depts = {r['code_dept']: r['libelle_dept'] for r in q('SELECT code_dept, libelle_dept FROM departement')}

# Chômage : historique complet + valeur 2024
chomage_history = {}
chomage_latest = {}
for r in q('SELECT code_dept, annee, taux_chomage_moyen FROM chomage ORDER BY annee'):
    d = r['code_dept']
    chomage_history.setdefault(d, []).append([r['annee'], r['taux_chomage_moyen']])
for r in q('SELECT code_dept, taux_chomage_moyen FROM chomage WHERE annee = (SELECT MAX(annee) FROM chomage WHERE taux_chomage_moyen IS NOT NULL)'):
    chomage_latest[r['code_dept']] = r['taux_chomage_moyen']

# Criminalité : dernière année disponible agrégée + par indicateur
crimi_latest = {}
for r in q('''
    SELECT code_dept, indicateur_clean, taux_pour_mille
    FROM criminalite
    WHERE annee = (SELECT MAX(annee) FROM criminalite)
'''):
    d = r['code_dept']
    crimi_latest.setdefault(d, {})[r['indicateur_clean']] = r['taux_pour_mille']

# Criminalité totale = somme des taux
crimi_total = {d: round(sum(v for v in ind.values() if v), 2) for d, ind in crimi_latest.items()}

# Démographie : dernière année
demographie = {}
for r in q('SELECT * FROM demographie WHERE annee = (SELECT MAX(annee) FROM demographie)'):
    demographie[r['code_dept']] = {
        'annee': r['annee'],
        'pop_municipale': r['pop_municipale'],
        'pop_totale': r['pop_totale'],
        'nb_commune': r['nb_commune'],
    }

# Entreprises : dernière année, total
entreprises = {}
for r in q('SELECT code_dept, annee, bure__total__total FROM entreprises WHERE annee = (SELECT MAX(annee) FROM entreprises)'):
    entreprises[r['code_dept']] = {'annee': r['annee'], 'total': r['bure__total__total']}

# Élections : votes par candidat par département
CANDIDATS_ORDER = ['MACRON', 'LE PEN', 'MÉLENCHON', 'ZEMMOUR', 'PÉCRESSE',
                   'JADOT', 'LASSALLE', 'ROUSSEL', 'DUPONT-AIGNAN',
                   'HIDALGO', 'ARTHAUD', 'POUTOU']

COLORS = {
    'MACRON': '#FFD700',
    'LE PEN': '#003189',
    'MÉLENCHON': '#CC0000',
    'ZEMMOUR': '#1A1A2E',
    'PÉCRESSE': '#0066CC',
    'JADOT': '#3A9B35',
    'LASSALLE': '#F97316',
    'ROUSSEL': '#B91C1C',
    'DUPONT-AIGNAN': '#6366F1',
    'HIDALGO': '#F43F5E',
    'ARTHAUD': '#7F1D1D',
    'POUTOU': '#7C3AED',
}

election_raw = {}
for r in q('SELECT code_dept, nom, prenom, voix, pct_voix_exp FROM election'):
    d = r['code_dept']
    # Normalise nom
    nom = r['nom'].strip()
    if 'LENCHON' in nom: nom = 'MÉLENCHON'
    if 'CRESSE' in nom: nom = 'PÉCRESSE'
    if 'MMOUR' in nom: nom = 'ZEMMOUR'
    election_raw.setdefault(d, {})[nom] = {
        'voix': r['voix'],
        'pct': round(r['pct_voix_exp'] or 0, 2),
        'prenom': r['prenom'],
    }

# Gagnant par département
election_winner = {}
for d, candidats in election_raw.items():
    if candidats:
        winner = max(candidats, key=lambda k: candidats[k]['pct'])
        election_winner[d] = {'nom': winner, 'pct': candidats[winner]['pct']}

# Chômage historique pour série chronologique nationale
chomage_national = {}
for r in q('SELECT annee, AVG(taux_chomage_moyen) as avg FROM chomage GROUP BY annee ORDER BY annee'):
    chomage_national[r['annee']] = round(r['avg'] or 0, 2)

# ---------------------------------------------------------------------------
# Assemblage JSON
# ---------------------------------------------------------------------------

data = {}
for code, nom in depts.items():
    data[code] = {
        'nom': nom,
        'chomage_latest': chomage_latest.get(code),
        'chomage_history': chomage_history.get(code, []),
        'criminalite': crimi_latest.get(code, {}),
        'crimi_total': crimi_total.get(code),
        'demographie': demographie.get(code, {}),
        'entreprises': entreprises.get(code, {}),
        'election': election_raw.get(code, {}),
        'winner': election_winner.get(code, {}),
    }

json_data = json.dumps(data, ensure_ascii=False)
json_candidats_colors = json.dumps(COLORS, ensure_ascii=False)
json_national_chomage = json.dumps([[k, v] for k, v in chomage_national.items()])

conn.close()

# ---------------------------------------------------------------------------
# Template HTML
# ---------------------------------------------------------------------------

HTML = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Electio-Analytics — Dashboard</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Inter', system-ui, sans-serif; background: #f4f5f7; color: #1a202c; height: 100vh; display: flex; flex-direction: column; }}

  /* ── NAV ── */
  nav {{ background: #fff; border-bottom: 1px solid #e8eaed; padding: 0 20px; display: flex; align-items: center; gap: 4px; height: 52px; flex-shrink: 0; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
  nav .logo {{ font-weight: 800; font-size: 1rem; color: #1a202c; margin-right: 20px; letter-spacing: -0.5px; }}
  nav .logo span {{ color: #2563eb; }}
  nav .logo small {{ font-weight: 500; font-size: 0.68rem; color: #9ca3af; margin-left: 6px; letter-spacing: 0; }}
  .tab-btn {{ padding: 7px 16px; border: none; background: none; color: #6b7280; cursor: pointer; border-radius: 8px; font-size: 0.82rem; font-weight: 500; transition: all .15s; font-family: inherit; }}
  .tab-btn:hover {{ background: #f3f4f6; color: #374151; }}
  .tab-btn.active {{ background: #eff6ff; color: #2563eb; font-weight: 600; }}

  /* ── TABS ── */
  .tab {{ display: none; flex: 1; overflow: hidden; flex-direction: column; }}
  .tab.active {{ display: flex; }}

  /* ── MAP TAB ── */
  #map-container {{ display: flex; flex: 1; overflow: hidden; }}
  #map {{ flex: 1; min-width: 0; background: #d1d5db; }}
  #side-panel {{ width: 22%; min-width: 240px; background: #fff; border-left: 1px solid #e8eaed; overflow-y: auto; flex-shrink: 0; display: flex; flex-direction: column; box-shadow: -2px 0 8px rgba(0,0,0,0.04); }}
  #side-panel-content {{ flex: 1; }}
  #side-panel .placeholder {{ color: #d1d5db; text-align: center; padding: 52px 20px; font-size: 0.82rem; line-height: 1.6; }}
  #side-panel .placeholder svg {{ display: block; margin: 0 auto 14px; opacity: 0.35; }}

  /* Sélecteur + légende */
  .side-toolbar {{ padding: 12px 14px 10px; border-bottom: 1px solid #f0f0f0; flex-shrink: 0; background: #fafbfc; }}
  .side-toolbar label {{ display: block; font-size: 0.63rem; color: #9ca3af; text-transform: uppercase; letter-spacing: .09em; margin-bottom: 5px; font-weight: 600; }}
  .side-toolbar select {{ width: 100%; background: #fff; color: #374151; border: 1px solid #d1d5db; border-radius: 8px; padding: 7px 10px; font-size: 0.8rem; cursor: pointer; font-family: inherit; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }}
  .side-toolbar select:focus {{ outline: 2px solid #2563eb; border-color: transparent; }}
  .legend {{ padding: 10px 14px 8px; border-bottom: 1px solid #f0f0f0; font-size: 0.72rem; flex-shrink: 0; background: #fafbfc; }}
  .legend-title {{ font-size: 0.61rem; color: #9ca3af; text-transform: uppercase; letter-spacing: .09em; font-weight: 600; margin-bottom: 6px; }}
  .legend-row {{ display: flex; align-items: center; gap: 7px; margin-bottom: 3px; color: #6b7280; }}
  .legend-color {{ width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }}

  /* ── PANEL DEPT ── */
  .panel-hero {{ padding: 16px 14px 12px; border-bottom: 1px solid #f0f0f0; }}
  .panel-hero .dept-code {{ font-size: 0.61rem; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: .12em; margin-bottom: 2px; }}
  .panel-hero .dept-name {{ font-size: 1.15rem; font-weight: 800; color: #111827; line-height: 1.2; }}
  .panel-hero .winner-row {{ margin-top: 10px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
  .winner-pill {{ display: inline-flex; align-items: center; gap: 5px; border-radius: 20px; padding: 4px 10px; font-size: 0.72rem; font-weight: 700; }}
  .winner-dot {{ width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; opacity: 0.8; }}

  .panel-block {{ padding: 12px 14px; border-bottom: 1px solid #f4f5f7; }}
  .block-title {{ font-size: 0.61rem; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 9px; display: flex; align-items: center; gap: 5px; }}

  .stat-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 7px; margin-bottom: 4px; }}
  .stat-card {{ background: #f8f9fa; border: 1px solid #e8eaed; border-radius: 10px; padding: 9px 11px; }}
  .stat-card .num {{ font-size: 1.15rem; font-weight: 800; color: #111827; line-height: 1; letter-spacing: -0.5px; }}
  .stat-card .lbl {{ font-size: 0.61rem; color: #9ca3af; margin-top: 4px; line-height: 1.3; font-weight: 500; }}
  .stat-card.c-blue   {{ border-top: 3px solid #3b82f6; }}
  .stat-card.c-green  {{ border-top: 3px solid #10b981; }}
  .stat-card.c-orange {{ border-top: 3px solid #f59e0b; }}

  .bar-list {{ display: flex; flex-direction: column; gap: 5px; }}
  .bar-item {{ display: flex; align-items: center; gap: 6px; font-size: 0.71rem; }}
  .bar-item .name {{ width: 78px; flex-shrink: 0; color: #6b7280; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; font-weight: 500; }}
  .bar-item .bar {{ flex: 1; height: 6px; border-radius: 3px; background: #e8eaed; overflow: hidden; }}
  .bar-item .bar-fill {{ height: 100%; border-radius: 3px; transition: width .35s ease; }}
  .bar-item .pct {{ width: 34px; text-align: right; color: #9ca3af; flex-shrink: 0; font-variant-numeric: tabular-nums; font-weight: 500; }}
  canvas.mini {{ width: 100% !important; height: 70px !important; margin-top: 6px; }}

  /* ── ELECTIONS TAB ── */
  #tab-elections {{ flex-direction: row; }}
  #elec-map-wrap {{ flex: 1; display: flex; flex-direction: column; }}
  #elec-map {{ flex: 1; }}
  #elec-panel {{ width: 300px; background: #fff; border-left: 1px solid #e8eaed; overflow-y: auto; padding: 16px; flex-shrink: 0; box-shadow: -2px 0 8px rgba(0,0,0,0.04); }}
  #elec-panel h3 {{ font-size: 0.61rem; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: #9ca3af; margin-bottom: 12px; }}
  .elec-toolbar {{ background: #fff; border-bottom: 1px solid #e8eaed; padding: 10px 14px; font-size: 0.82rem; display: flex; gap: 10px; align-items: center; flex-shrink: 0; }}
  .elec-toolbar label {{ color: #9ca3af; font-size: 0.73rem; font-weight: 600; letter-spacing: .04em; }}
  .elec-toolbar select {{ background: #fff; color: #374151; border: 1px solid #d1d5db; border-radius: 8px; padding: 5px 10px; font-size: 0.78rem; font-family: inherit; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }}

  /* ── CORRELATIONS TAB ── */
  #tab-correlations {{ flex-direction: column; overflow-y: auto; background: #f4f5f7; }}
  .corr-header {{ padding: 14px 24px; background: #fff; border-bottom: 1px solid #e8eaed; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; flex-shrink: 0; box-shadow: 0 1px 4px rgba(0,0,0,0.04); }}
  .corr-header h2 {{ font-size: 0.95rem; font-weight: 700; color: #111827; flex: 1; }}
  .corr-header label {{ font-size: 0.73rem; color: #9ca3af; font-weight: 600; }}
  .corr-header select {{ background: #fff; color: #374151; border: 1px solid #d1d5db; border-radius: 8px; padding: 5px 10px; font-size: 0.8rem; font-family: inherit; }}
  .corr-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 14px; padding: 16px 24px; }}
  .corr-card {{ background: #fff; border: 1px solid #e8eaed; border-radius: 12px; padding: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.04); }}
  .corr-card h4 {{ font-size: 0.77rem; color: #6b7280; margin-bottom: 10px; font-weight: 500; }}
  .corr-card canvas {{ width: 100% !important; }}

  /* ── SCROLLBAR ── */
  ::-webkit-scrollbar {{ width: 4px; }} ::-webkit-scrollbar-track {{ background: transparent; }} ::-webkit-scrollbar-thumb {{ background: #d1d5db; border-radius: 4px; }}
</style>
</head>
<body>

<nav>
  <div class="logo">Electio<span>Analytics</span></div>
  <button class="tab-btn active" onclick="showTab('carte')">🗺 Carte & Indicateurs</button>
  <button class="tab-btn" onclick="showTab('elections')">🗳 Résultats T1 2022</button>
  <button class="tab-btn" onclick="showTab('correlations')">📊 Corrélations</button>
</nav>

<!-- ══════════════════════════════════════════════════════════════
     TAB 1 — CARTE
══════════════════════════════════════════════════════════════ -->
<div id="tab-carte" class="tab active">
  <div id="map-container">
    <div id="map"></div>
    <div id="side-panel">
      <div class="side-toolbar">
        <label>Colorier la carte par</label>
        <select id="map-indicator" onchange="updateChoropleth()">
          <option value="chomage">Taux de chômage (%)</option>
          <option value="crimi">Criminalité totale (taux/1000)</option>
          <option value="pop">Population totale</option>
          <option value="entreprises">Nb entreprises</option>
        </select>
      </div>
      <div id="legend" class="legend"></div>
      <div id="side-panel-content">
        <div class="placeholder">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 16l4.553-2.276A1 1 0 0021 19.382V8.618a1 1 0 00-.553-.894L15 5m0 18V5m0 0L9 7"/></svg>
          Cliquez sur un département pour afficher ses indicateurs
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ══════════════════════════════════════════════════════════════
     TAB 2 — ÉLECTIONS
══════════════════════════════════════════════════════════════ -->
<div id="tab-elections" class="tab">
  <div id="elec-map-wrap">
    <div class="elec-toolbar">
      <label>Afficher :</label>
      <select id="elec-view" onchange="updateElecMap()">
        <option value="winner">Candidat en tête (par dept)</option>
        <option value="MACRON">% Emmanuel Macron</option>
        <option value="LE PEN">% Marine Le Pen</option>
        <option value="MÉLENCHON">% Jean-Luc Mélenchon</option>
        <option value="ZEMMOUR">% Éric Zemmour</option>
        <option value="PÉCRESSE">% Valérie Pécresse</option>
        <option value="JADOT">% Yannick Jadot</option>
      </select>
    </div>
    <div id="elec-map"></div>
  </div>
  <div id="elec-panel">
    <h3>Résultats nationaux T1 2022</h3>
    <canvas id="national-bar" height="220"></canvas>
    <div style="margin-top:16px;color:#64748b;font-size:0.75rem;">Cliquez sur un département pour afficher ses résultats détaillés.</div>
    <div id="elec-dept-detail" style="margin-top:12px;"></div>
  </div>
</div>

<!-- ══════════════════════════════════════════════════════════════
     TAB 3 — CORRÉLATIONS
══════════════════════════════════════════════════════════════ -->
<div id="tab-correlations" class="tab">
  <div class="corr-header">
    <h2>Corrélations indicateurs × résultats électoraux</h2>
    <label style="color:#94a3b8;font-size:.82rem;">Candidat :</label>
    <select id="corr-candidat" onchange="renderCorrelations()">
      <option value="MACRON">Macron</option>
      <option value="LE PEN">Le Pen</option>
      <option value="MÉLENCHON">Mélenchon</option>
      <option value="ZEMMOUR">Zemmour</option>
      <option value="PÉCRESSE">Pécresse</option>
      <option value="JADOT">Jadot</option>
    </select>
  </div>
  <div class="corr-grid" id="corr-grid"></div>
</div>

<!-- ══════════════════════════════════════════════════════════════
     DATA + JS
══════════════════════════════════════════════════════════════ -->
<script>
const DATA = {json_data};
const CAND_COLORS = {json_candidats_colors};
const NATIONAL_CHOMAGE = {json_national_chomage};

// Alias d'affichage
const CAND_LABELS = {{
  'MACRON': 'Macron', 'LE PEN': 'Le Pen', 'MÉLENCHON': 'Mélenchon',
  'ZEMMOUR': 'Zemmour', 'PÉCRESSE': 'Pécresse', 'JADOT': 'Jadot',
  'LASSALLE': 'Lassalle', 'ROUSSEL': 'Roussel', 'DUPONT-AIGNAN': 'Dupont-Aignan',
  'HIDALGO': 'Hidalgo', 'ARTHAUD': 'Arthaud', 'POUTOU': 'Poutou',
}};

// ── TABS ────────────────────────────────────────────────────────
const maps = {{}};
function showTab(id) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  document.querySelectorAll('.tab-btn')[['carte','elections','correlations'].indexOf(id)].classList.add('active');
  setTimeout(() => {{
    Object.values(maps).forEach(m => m.invalidateSize());
    if (id === 'correlations') renderCorrelations();
    if (id === 'elections') renderNationalBar();
  }}, 50);
}}

// ── GEOJSON FETCH ───────────────────────────────────────────────
let geojson = null;
fetch('https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson')
  .then(r => r.json())
  .then(g => {{
    geojson = g;
    initCarteMap();
    initElecMap();
  }});

// ── UTILS ────────────────────────────────────────────────────────
function lerp(a, b, t) {{ return a + (b - a) * t; }}
function colorScale(val, min, max, low='#0ea5e9', high='#ef4444') {{
  if (val == null) return '#334155';
  const t = Math.max(0, Math.min(1, (val - min) / (max - min || 1)));
  const c1 = hexToRgb(low), c2 = hexToRgb(high);
  return `rgb(${{Math.round(lerp(c1[0],c2[0],t))}}, ${{Math.round(lerp(c1[1],c2[1],t))}}, ${{Math.round(lerp(c1[2],c2[2],t))}})`;
}}
function hexToRgb(hex) {{
  const r = /^#?([a-f\\d]{{2}})([a-f\\d]{{2}})([a-f\\d]{{2}})$/i.exec(hex);
  return r ? [parseInt(r[1],16), parseInt(r[2],16), parseInt(r[3],16)] : [0,0,0];
}}
function fmt(n) {{ return n == null ? 'N/A' : Number(n).toLocaleString('fr-FR'); }}

// ── INDICATEUR VALUES ──────────────────────────────────────────
function getIndVal(code) {{
  const d = DATA[code]; if (!d) return null;
  const ind = document.getElementById('map-indicator').value;
  if (ind === 'chomage') return d.chomage_latest;
  if (ind === 'crimi') return d.crimi_total;
  if (ind === 'pop') return d.demographie?.pop_totale;
  if (ind === 'entreprises') return d.entreprises?.total;
  return null;
}}

// ── CARTE MAP ──────────────────────────────────────────────────
let carteLayer = null;
let currentCarteMap = null;

function initCarteMap() {{
  const map = L.map('map', {{ center: [46.5, 2.5], zoom: 6, zoomControl: true, attributionControl: false }});
  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    attribution: '© OpenStreetMap © CARTO', subdomains: 'abcd', maxZoom: 12
  }}).addTo(map);
  maps.carte = map;
  currentCarteMap = map;
  updateChoropleth();
}}

function updateChoropleth() {{
  if (!geojson || !currentCarteMap) return;
  // Calcul min/max
  const vals = Object.keys(DATA).map(getIndVal).filter(v => v != null);
  const min = Math.min(...vals), max = Math.max(...vals);

  if (carteLayer) currentCarteMap.removeLayer(carteLayer);
  carteLayer = L.geoJSON(geojson, {{
    style: feat => {{
      const code = feat.properties.code;
      const val = getIndVal(code);
      return {{
        fillColor: colorScale(val, min, max, '#bfdbfe', '#dc2626'),
        weight: 0.8, opacity: 1, color: '#fff', fillOpacity: 0.85
      }};
    }},
    onEachFeature: (feat, layer) => {{
      const code = feat.properties.code;
      layer.on('click', () => showDeptPanel(code));
      layer.on('mouseover', e => {{
        layer.setStyle({{ weight: 2, color: '#2563eb' }});
        const d = DATA[code];
        const val = getIndVal(code);
        layer.bindTooltip(`<b>${{d?.nom || code}}</b> (${{code}})<br>${{val != null ? Number(val).toLocaleString('fr-FR') : 'N/A'}}`, {{sticky:true}}).openTooltip(e.latlng);
      }});
      layer.on('mouseout', () => {{
        carteLayer.resetStyle(layer);
        layer.closeTooltip();
      }});
    }}
  }}).addTo(currentCarteMap);

  renderLegend(min, max);
}}

function renderLegend(min, max) {{
  const ind = document.getElementById('map-indicator').value;
  const labels = {{ chomage:'Chômage %', crimi:'Criminalité /1000', pop:'Population', entreprises:'Entreprises' }};
  const steps = 5;
  let html = `<div class="legend-title">${{labels[ind]}}</div>`;
  for (let i=0; i<steps; i++) {{
    const t = i/(steps-1);
    const v = min + t*(max-min);
    const c = colorScale(v, min, max, '#bfdbfe', '#dc2626');
    html += `<div class="legend-row"><div class="legend-color" style="background:${{c}}"></div>${{Math.round(v).toLocaleString('fr-FR')}}</div>`;
  }}
  document.getElementById('legend').innerHTML = html;
}}

// ── PANEL DÉPARTEMENT ──────────────────────────────────────────
let miniCharts = {{}};
function showDeptPanel(code) {{
  const d = DATA[code]; if (!d) return;
  const panel = document.getElementById('side-panel-content');

  const elec = d.election || {{}};
  const sorted = Object.entries(elec).sort((a,b) => b[1].pct - a[1].pct);
  const winner = d.winner?.nom || '';
  const winnerColor = CAND_COLORS[winner] || '#388bfd';
  const winnerPct = d.winner?.pct || 0;

  // Chômage coloré selon le niveau
  const chom = d.chomage_latest;
  const chomColor = chom == null ? '#9ca3af' : chom < 7 ? '#10b981' : chom < 10 ? '#f59e0b' : '#ef4444';

  // Top 5 criminalité
  const crimi = d.criminalite || {{}};
  const crimiSorted = Object.entries(crimi).sort((a,b) => b[1]-a[1]).slice(0,5);
  const crimiMax = crimiSorted[0]?.[1] || 1;
  const crimiHtml = crimiSorted.map(([k,v]) => {{
    const w = Math.round(v/crimiMax*100);
    const label = k.replace(/_/g,' ');
    return `<div class="bar-item">
      <div class="name" title="${{label}}">${{label}}</div>
      <div class="bar"><div class="bar-fill" style="width:${{w}}%;background:#f97316"></div></div>
      <div class="pct">${{v.toFixed(1)}}</div>
    </div>`;
  }}).join('');

  const barsHtml = sorted.map(([nom, v]) => {{
    const color = CAND_COLORS[nom] || '#484f58';
    return `<div class="bar-item">
      <div class="name" title="${{CAND_LABELS[nom]||nom}}">${{CAND_LABELS[nom]||nom}}</div>
      <div class="bar"><div class="bar-fill" style="width:${{v.pct}}%;background:${{color}}"></div></div>
      <div class="pct">${{v.pct}}%</div>
    </div>`;
  }}).join('');

  panel.innerHTML = `
    <div class="panel-hero">
      <div class="dept-code">Département · ${{code}}</div>
      <div class="dept-name">${{d.nom}}</div>
      ${{winner ? `<div class="winner-row">
        <div class="winner-pill" style="background:${{winnerColor}}18;color:${{winnerColor}};border:1px solid ${{winnerColor}}33;">
          <div class="winner-dot" style="background:${{winnerColor}}"></div>
          ${{CAND_LABELS[winner]||winner}} · ${{winnerPct}}%
        </div>
        <span style="font-size:0.62rem;color:#6e7681;">en tête T1 2022</span>
      </div>` : ''}}
    </div>

    <div class="panel-block">
      <div class="block-title"><span class="icon">👥</span> Population & territoire</div>
      <div class="stat-row">
        <div class="stat-card c-blue">
          <div class="num">${{d.demographie?.pop_totale ? (d.demographie.pop_totale/1000).toFixed(0)+'k' : 'N/A'}}</div>
          <div class="lbl">habitants</div>
        </div>
        <div class="stat-card c-blue">
          <div class="num">${{fmt(d.demographie?.nb_commune)}}</div>
          <div class="lbl">communes</div>
        </div>
      </div>
    </div>

    <div class="panel-block">
      <div class="block-title"><span class="icon">📈</span> Économie</div>
      <div class="stat-row">
        <div class="stat-card c-green">
          <div class="num" style="color:${{chomColor}}">${{chom != null ? chom.toFixed(1)+'%' : 'N/A'}}</div>
          <div class="lbl">chômage</div>
        </div>
        <div class="stat-card c-green">
          <div class="num">${{d.entreprises?.total ? (d.entreprises.total/1000).toFixed(1)+'k' : 'N/A'}}</div>
          <div class="lbl">entreprises</div>
        </div>
      </div>
      <canvas id="chomage-chart" class="mini" style="margin-top:6px;"></canvas>
    </div>

    <div class="panel-block">
      <div class="block-title"><span class="icon">🔒</span> Criminalité · top 5 (taux/1000)</div>
      <div class="bar-list">${{crimiHtml}}</div>
    </div>

    <div class="panel-block">
      <div class="block-title"><span class="icon">🗳</span> Présidentielle T1 2022</div>
      <div class="bar-list">${{barsHtml}}</div>
    </div>
  `;

  destroyChart('chomage-chart');
  const histData = (d.chomage_history || []).filter(([y]) => y >= 2010);
  miniCharts['chomage-chart'] = new Chart(document.getElementById('chomage-chart'), {{
    type: 'line',
    data: {{
      labels: histData.map(([y]) => y),
      datasets: [{{
        data: histData.map(([,v]) => v),
        borderColor: '#3b82f6', borderWidth: 1.5,
        pointRadius: 0, fill: true,
        backgroundColor: 'rgba(59,130,246,0.08)',
        tension: 0.4
      }}]
    }},
    options: {{
      plugins: {{ legend: {{ display:false }} }},
      scales: {{
        x: {{ ticks: {{ color:'#9ca3af', maxTicksLimit:4, font:{{size:8}} }}, grid: {{ color:'#f0f0f0' }} }},
        y: {{ ticks: {{ color:'#9ca3af', font:{{size:8}} }}, grid: {{ color:'#f0f0f0' }} }}
      }},
      animation: {{ duration: 250 }}
    }}
  }});
}}

function destroyChart(id) {{
  if (miniCharts[id]) {{ miniCharts[id].destroy(); delete miniCharts[id]; }}
}}

// ── ELECTIONS MAP ──────────────────────────────────────────────
let elecLayer = null;

function initElecMap() {{
  const map = L.map('elec-map', {{ center:[46.5,2.5], zoom:6, attributionControl:false }});
  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    subdomains:'abcd', maxZoom:12
  }}).addTo(map);
  maps.elec = map;
  updateElecMap();
}}

function updateElecMap() {{
  if (!geojson || !maps.elec) return;
  if (elecLayer) maps.elec.removeLayer(elecLayer);
  const view = document.getElementById('elec-view').value;

  // Si vue candidat unique : gradient blanc → couleur du candidat
  let vals = {{}};
  if (view !== 'winner') {{
    Object.keys(DATA).forEach(code => {{
      vals[code] = DATA[code]?.election?.[view]?.pct || 0;
    }});
  }}
  const vArr = Object.values(vals);
  const vMax = vArr.length ? Math.max(...vArr) : 100;

  elecLayer = L.geoJSON(geojson, {{
    style: feat => {{
      const code = feat.properties.code;
      let fillColor = '#334155';
      if (view === 'winner') {{
        const winner = DATA[code]?.winner?.nom;
        fillColor = winner ? (CAND_COLORS[winner] || '#334155') : '#334155';
      }} else {{
        const pct = vals[code] || 0;
        fillColor = colorScale(pct, 0, vMax, '#1e293b', CAND_COLORS[view] || '#0ea5e9');
      }}
      return {{ fillColor, weight:0.8, opacity:1, color:'#fff', fillOpacity:0.88 }};
    }},
    onEachFeature: (feat, layer) => {{
      const code = feat.properties.code;
      layer.on('click', () => showElecDeptDetail(code));
      layer.on('mouseover', e => {{
        layer.setStyle({{ weight:2, color:'#f8fafc' }});
        const d = DATA[code]; if (!d) return;
        let tip;
        if (view === 'winner') {{
          const w = d.winner; tip = `<b>${{d.nom}}</b><br>${{CAND_LABELS[w?.nom]||w?.nom||'?'}} — ${{w?.pct||0}}%`;
        }} else {{
          tip = `<b>${{d.nom}}</b><br>${{CAND_LABELS[view]||view}} : ${{(vals[code]||0).toFixed(1)}}%`;
        }}
        layer.bindTooltip(tip, {{sticky:true}}).openTooltip(e.latlng);
      }});
      layer.on('mouseout', () => {{ elecLayer.resetStyle(layer); layer.closeTooltip(); }});
    }}
  }}).addTo(maps.elec);
}}

// ── RÉSULTATS NATIONAUX BAR ─────────────────────────────────────
let nationalBarChart = null;
function renderNationalBar() {{
  if (nationalBarChart) return; // déjà rendu
  // Agréger les voix nationales
  const totals = {{}};
  Object.values(DATA).forEach(d => {{
    Object.entries(d.election || {{}}).forEach(([nom, v]) => {{
      totals[nom] = (totals[nom]||0) + (v.voix||0);
    }});
  }});
  const grand = Object.values(totals).reduce((s,v)=>s+v,0);
  const sorted = Object.entries(totals).sort((a,b)=>b[1]-a[1]);
  nationalBarChart = new Chart(document.getElementById('national-bar'), {{
    type: 'bar',
    data: {{
      labels: sorted.map(([n])=>CAND_LABELS[n]||n),
      datasets: [{{
        data: sorted.map(([,v]) => +(v/grand*100).toFixed(2)),
        backgroundColor: sorted.map(([n])=>CAND_COLORS[n]||'#64748b'),
        borderRadius: 4,
      }}]
    }},
    options: {{
      indexAxis: 'y',
      plugins: {{ legend:{{display:false}}, tooltip:{{ callbacks:{{ label: ctx => ctx.parsed.x.toFixed(2)+'%' }} }} }},
      scales: {{
        x: {{ ticks:{{color:'#9ca3af',font:{{size:9}}}}, grid:{{color:'#f0f0f0'}}, title:{{display:true,text:'% suffrages exprimés',color:'#9ca3af',font:{{size:9}}}} }},
        y: {{ ticks:{{color:'#374151',font:{{size:10}}}}, grid:{{display:false}} }}
      }},
      animation: {{ duration:400 }}
    }}
  }});
}}

function showElecDeptDetail(code) {{
  const d = DATA[code]; if (!d) return;
  const elec = d.election || {{}};
  const sorted = Object.entries(elec).sort((a,b)=>b[1].pct-a[1].pct);
  let html = `<h3 style="font-size:.85rem;font-weight:700;color:#f8fafc;margin-bottom:8px;">${{d.nom}} (${{code}})</h3>`;
  html += `<div class="bar-list">` + sorted.map(([nom,v]) => {{
    const color = CAND_COLORS[nom]||'#64748b';
    return `<div class="bar-item">
      <div class="name">${{CAND_LABELS[nom]||nom}}</div>
      <div class="bar"><div class="bar-fill" style="width:${{v.pct}}%;background:${{color}}"></div></div>
      <div class="pct">${{v.pct}}%</div>
    </div>`;
  }}).join('') + `</div>`;
  document.getElementById('elec-dept-detail').innerHTML = html;
}}

// ── CORRÉLATIONS ────────────────────────────────────────────────
let corrCharts = {{}};
function renderCorrelations() {{
  const candidat = document.getElementById('corr-candidat').value;
  const grid = document.getElementById('corr-grid');

  // Détruire anciens charts
  Object.values(corrCharts).forEach(c => c.destroy());
  corrCharts = {{}};
  grid.innerHTML = '';

  const indicators = [
    {{ key: 'chomage', label: 'Taux de chômage (%)', fn: d => d.chomage_latest }},
    {{ key: 'crimi', label: 'Criminalité totale (taux/1000)', fn: d => d.crimi_total }},
    {{ key: 'pop', label: 'Population totale', fn: d => d.demographie?.pop_totale }},
    {{ key: 'entreprises', label: 'Nb entreprises', fn: d => d.entreprises?.total }},
    {{ key: 'cambriolages', label: 'Cambriolages (taux/1000)', fn: d => d.criminalite?.cambriolages }},
    {{ key: 'homicides', label: 'Homicides (taux/1000)', fn: d => d.criminalite?.homicides }},
    {{ key: 'trafic', label: 'Trafic stupéfiants (taux/1000)', fn: d => d.criminalite?.trafic_stupefiants }},
    {{ key: 'vols_violence', label: 'Vols violents sans arme (taux/1000)', fn: d => d.criminalite?.vols_violents_sans_arme }},
  ];

  indicators.forEach(ind => {{
    const points = [];
    Object.entries(DATA).forEach(([code, d]) => {{
      const x = ind.fn(d);
      const y = d.election?.[candidat]?.pct;
      if (x != null && y != null) points.push({{ x, y, label: d.nom }});
    }});
    if (points.length < 5) return;

    // Calcul R²
    const r2 = calcR2(points.map(p=>p.x), points.map(p=>p.y));
    const color = CAND_COLORS[candidat] || '#38bdf8';

    const card = document.createElement('div');
    card.className = 'corr-card';
    card.innerHTML = `<h4>${{ind.label}} vs % ${{CAND_LABELS[candidat]||candidat}} <span style="color:${{color}};margin-left:6px;">R²=${{r2.toFixed(3)}}</span></h4><canvas id="corr-${{ind.key}}" height="160"></canvas>`;
    grid.appendChild(card);

    corrCharts[ind.key] = new Chart(document.getElementById('corr-'+ind.key), {{
      type: 'scatter',
      data: {{
        datasets: [{{
          data: points,
          backgroundColor: color+'99',
          borderColor: color,
          borderWidth: 1,
          pointRadius: 4,
          pointHoverRadius: 6,
        }}]
      }},
      options: {{
        plugins: {{
          legend: {{ display:false }},
          tooltip: {{ callbacks: {{ label: ctx => `${{ctx.raw.label}}: (${{ctx.raw.x.toFixed(1)}}, ${{ctx.raw.y.toFixed(1)}}%)` }} }}
        }},
        scales: {{
          x: {{ title:{{display:true,text:ind.label,color:'#9ca3af',font:{{size:9}}}}, ticks:{{color:'#9ca3af',font:{{size:9}}}}, grid:{{color:'#f4f5f7'}} }},
          y: {{ title:{{display:true,text:'% voix',color:'#9ca3af',font:{{size:9}}}}, ticks:{{color:'#9ca3af',font:{{size:9}}}}, grid:{{color:'#f4f5f7'}} }}
        }},
        animation: {{ duration:300 }}
      }}
    }});
  }});
}}

function calcR2(xs, ys) {{
  const n = xs.length;
  if (n < 2) return 0;
  const mx = xs.reduce((s,v)=>s+v,0)/n;
  const my = ys.reduce((s,v)=>s+v,0)/n;
  let ss_res=0, ss_tot=0, cov=0, varx=0;
  for (let i=0;i<n;i++) {{ cov+=(xs[i]-mx)*(ys[i]-my); varx+=(xs[i]-mx)**2; ss_tot+=(ys[i]-my)**2; }}
  if (varx===0||ss_tot===0) return 0;
  const slope = cov/varx;
  const intcpt = my - slope*mx;
  for (let i=0;i<n;i++) {{ ss_res+=(ys[i]-(slope*xs[i]+intcpt))**2; }}
  return 1 - ss_res/ss_tot;
}}
</script>
</body>
</html>"""

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, 'w', encoding='utf-8') as f:
    f.write(HTML)
print(f"Dashboard genere : {OUT_PATH}")
