import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = BASE_DIR
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "clean")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def pad_code_dept(df):
    df["code_dept"] = (
        df["code_dept"]
        .astype(str)
        .str.strip()
        .apply(lambda x: x.zfill(2) if x.isdigit() else x)
    )
    return df


def save(df, name):
    path = os.path.join(OUTPUT_DIR, f"{name}.csv")
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"[OK] {name}.csv — {len(df)} lignes, {len(df.columns)} colonnes")


# ── 1. departement (référentiel) ──────────────────────────────────────────────
dept = pd.read_csv(os.path.join(INPUT_DIR, "departement_clean.csv"), sep=";", dtype=str)
dept.columns = dept.columns.str.lower().str.strip()
dept = pad_code_dept(dept)
save(dept, "departement")

valid_codes = set(dept["code_dept"])

# ── 2. chomage ────────────────────────────────────────────────────────────────
chomage = pd.read_csv(
    os.path.join(INPUT_DIR, "chomage_dept_annuel_clean.csv"), dtype={"code_dept": str}
)
chomage = pad_code_dept(chomage)
chomage = chomage.drop(columns=["libelle_dept"])
chomage = chomage[chomage["code_dept"].isin(valid_codes)]
save(chomage, "chomage")

# ── 3. demographie ────────────────────────────────────────────────────────────
demo = pd.read_csv(
    os.path.join(INPUT_DIR, "demographie_2018_2021_clean.csv"),
    sep=";",
    dtype={"code_dept": str},
)
demo.columns = demo.columns.str.lower().str.strip()
demo = pad_code_dept(demo)
demo = demo.drop(columns=["libelle_dept"])
demo["nb_canton"] = demo["nb_canton"].astype("Int64")
demo = demo[demo["code_dept"].isin(valid_codes)]
save(demo, "demographie")

# ── 4. entreprises ────────────────────────────────────────────────────────────
ent = pd.read_csv(
    os.path.join(INPUT_DIR, "entreprises_dept_annuel_clean.csv"),
    dtype={"code_dept": str},
)
ent = pad_code_dept(ent)
ent = ent.drop(columns=["nom_dept"])
ent = ent[ent["code_dept"].isin(valid_codes)]
save(ent, "entreprises")

# ── 5. criminalite ────────────────────────────────────────────────────────────
crim = pd.read_csv(
    os.path.join(INPUT_DIR, "criminalite_dept_long_clean.csv"),
    dtype={"code_dept": str},
)
crim = pad_code_dept(crim)
crim = crim.drop(columns=["nom_dept"])
crim = crim[crim["code_dept"].isin(valid_codes)]
save(crim, "criminalite")

# ── 6. election ───────────────────────────────────────────────────────────────
elec = pd.read_csv(
    os.path.join(INPUT_DIR, "election_pres_2021_t1_long.csv"),
    encoding="utf-8",
    dtype={"code_dept": str},
)
elec = pad_code_dept(elec)
elec = elec.drop(columns=["libelle_dept", "etat_saisie"])

elec = elec.rename(
    columns={
        "Inscrits": "inscrits",
        "Abstentions": "abstentions",
        "Votants": "votants",
        "Blancs": "blancs",
        "% Blancs/Ins": "pct_blancs_ins",
        "% Blancs/Vot": "pct_blancs_vot",
        "Nuls": "nuls",
        "% Nuls/Ins": "pct_nuls_ins",
        "% Nuls/Vot": "pct_nuls_vot",
        "Exprimés": "exprimes",
    }
)

filtered_out = elec[~elec["code_dept"].isin(valid_codes)]["code_dept"].unique()
if len(filtered_out):
    print(f"  [INFO] election — codes filtrés (hors référentiel) : {sorted(filtered_out)}")

elec = elec[elec["code_dept"].isin(valid_codes)]
save(elec, "election")

print("\nFichiers propres dans :", OUTPUT_DIR)
