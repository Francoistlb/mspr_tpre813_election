import os
import sqlite3
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEAN_DIR = os.path.join(BASE_DIR, "data", "clean")
DB_PATH   = os.path.join(BASE_DIR, "db", "mspr.db")

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")

SCHEMA = """
CREATE TABLE departement (
    code_dept    TEXT PRIMARY KEY,
    libelle_dept TEXT NOT NULL
);

CREATE TABLE chomage (
    code_dept          TEXT    NOT NULL REFERENCES departement(code_dept),
    annee              INTEGER NOT NULL,
    taux_chomage_moyen REAL,
    taux_chomage_min   REAL,
    taux_chomage_max   REAL,
    nb_trimestres      INTEGER,
    PRIMARY KEY (code_dept, annee)
);

CREATE TABLE demographie (
    code_dept         TEXT    NOT NULL REFERENCES departement(code_dept),
    annee             INTEGER NOT NULL,
    nb_arrondissement INTEGER,
    nb_canton         INTEGER,
    nb_commune        INTEGER,
    pop_municipale    INTEGER,
    pop_totale        INTEGER,
    PRIMARY KEY (code_dept, annee)
);

CREATE TABLE criminalite (
    code_dept        TEXT    NOT NULL REFERENCES departement(code_dept),
    annee            INTEGER NOT NULL,
    indicateur       TEXT,
    indicateur_clean TEXT    NOT NULL,
    unite_de_compte  TEXT,
    nombre           INTEGER,
    taux_pour_mille  REAL,
    insee_pop        INTEGER,
    PRIMARY KEY (code_dept, annee, indicateur_clean)
);

CREATE TABLE election (
    code_dept      TEXT    NOT NULL REFERENCES departement(code_dept),
    inscrits       INTEGER,
    abstentions    INTEGER,
    pct_abs_ins    REAL,
    votants        INTEGER,
    pct_vot_ins    REAL,
    blancs         INTEGER,
    pct_blancs_ins REAL,
    pct_blancs_vot REAL,
    nuls           INTEGER,
    pct_nuls_ins   REAL,
    pct_nuls_vot   REAL,
    exprimes       INTEGER,
    pct_exp_ins    REAL,
    pct_exp_vot    REAL,
    sexe           TEXT,
    nom            TEXT NOT NULL,
    prenom         TEXT,
    voix           INTEGER,
    pct_voix_ins   REAL,
    pct_voix_exp   REAL,
    PRIMARY KEY (code_dept, nom)
);

CREATE TABLE entreprises (
    code_dept                                              TEXT    NOT NULL REFERENCES departement(code_dept),
    annee                                                  INTEGER NOT NULL,
    bure__activites_financieres__autres_formes             INTEGER,
    bure__activites_financieres__entrepreneur_individuel   INTEGER,
    bure__activites_financieres__sarl                      INTEGER,
    bure__activites_financieres__sas_sasu                  INTEGER,
    bure__activites_financieres__total                     INTEGER,
    bure__administration_sante_education__autres_formes    INTEGER,
    bure__administration_sante_education__entrepreneur_individuel INTEGER,
    bure__administration_sante_education__sarl             INTEGER,
    bure__administration_sante_education__sas_sasu         INTEGER,
    bure__administration_sante_education__total            INTEGER,
    bure__autres_services__autres_formes                   INTEGER,
    bure__autres_services__entrepreneur_individuel         INTEGER,
    bure__autres_services__sarl                            INTEGER,
    bure__autres_services__sas_sasu                        INTEGER,
    bure__autres_services__total                           INTEGER,
    bure__commerce_transport_hebergement__autres_formes    INTEGER,
    bure__commerce_transport_hebergement__entrepreneur_individuel INTEGER,
    bure__commerce_transport_hebergement__sarl             INTEGER,
    bure__commerce_transport_hebergement__sas_sasu         INTEGER,
    bure__commerce_transport_hebergement__total            INTEGER,
    bure__construction__autres_formes                      INTEGER,
    bure__construction__entrepreneur_individuel            INTEGER,
    bure__construction__sarl                               INTEGER,
    bure__construction__sas_sasu                           INTEGER,
    bure__construction__total                              INTEGER,
    bure__immobilier__autres_formes                        INTEGER,
    bure__immobilier__entrepreneur_individuel              INTEGER,
    bure__immobilier__sarl                                 INTEGER,
    bure__immobilier__sas_sasu                             INTEGER,
    bure__immobilier__total                                INTEGER,
    bure__industrie_extractive_energie__autres_formes      INTEGER,
    bure__industrie_extractive_energie__entrepreneur_individuel INTEGER,
    bure__industrie_extractive_energie__sarl               INTEGER,
    bure__industrie_extractive_energie__sas_sasu           INTEGER,
    bure__industrie_extractive_energie__total              INTEGER,
    bure__industrie_manufacturiere__autres_formes          INTEGER,
    bure__industrie_manufacturiere__entrepreneur_individuel INTEGER,
    bure__industrie_manufacturiere__sarl                   INTEGER,
    bure__industrie_manufacturiere__sas_sasu               INTEGER,
    bure__industrie_manufacturiere__total                  INTEGER,
    bure__information_communication__autres_formes         INTEGER,
    bure__information_communication__entrepreneur_individuel INTEGER,
    bure__information_communication__sarl                  INTEGER,
    bure__information_communication__sas_sasu              INTEGER,
    bure__information_communication__total                 INTEGER,
    bure__total__autres_formes                             INTEGER,
    bure__total__entrepreneur_individuel                   INTEGER,
    bure__total__sarl                                      INTEGER,
    bure__total__sas_sasu                                  INTEGER,
    bure__total__total                                     INTEGER,
    PRIMARY KEY (code_dept, annee)
);
"""

conn.executescript(SCHEMA)


def load(table, csv_name=None, pk=None):
    path = os.path.join(CLEAN_DIR, f"{csv_name or table}.csv")
    df = pd.read_csv(path, dtype={"code_dept": str})
    df.to_sql(table, conn, if_exists="append", index=False)
    print(f"[OK] {table:<15} {len(df):>6} lignes")


load("departement")
load("chomage")
load("demographie")
load("criminalite")
load("election")
load("entreprises")

conn.commit()
conn.close()
print(f"\nDB prete : {DB_PATH}")
