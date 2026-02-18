# ⚡ Démarrage Rapide - Migration QVD

## 🎯 En 3 Étapes (10 minutes)

### Situation : Vous avez des fichiers QVD à migrer vers Power BI

---

## 📋 ÉTAPE 1 : Générer le Script d'Export (1 min)

```bash
cd "c:\Users\pidoudet\OneDrive - Microsoft\Boulot\PBI SME\OracleToPostgre\fabric-deployment"

python migrate_qvd.py --qvd-folder "C:\Chemin\Vers\QVD" --export-folder "C:\Export" --generate-qlik-script
```

**Résultat :**
```
✓ Script créé : C:\Export\01_export_qvd_to_csv.qvs
```

---

## 📋 ÉTAPE 2 : Exporter les QVD en CSV (5 min)

### A. Dans QlikView Desktop

1. **Ouvrir QlikView**
2. **Fichier → Nouveau**
3. **Ctrl+E** (Éditeur de script)
4. **Copier le contenu** de `01_export_qvd_to_csv.qvs`
5. **Coller** dans l'éditeur
6. **Ctrl+R** (Recharger)
7. ✓ Les CSV sont créés dans `C:\Export\`

### B. Ou avec Qlik Sense Desktop

1. **Ouvrir Qlik Sense**
2. **Créer une nouvelle application**
3. **Préparer → Éditeur de chargement de données**
4. **Copier-coller** le script
5. **Charger les données**

---

## 📋 ÉTAPE 3 : Charger dans Power BI (4 min)

### Option A : CSV Direct (Simple)

```bash
python migrate_qvd.py --export-folder "C:\Export" --generate-powerquery
```

**Puis dans Power BI :**
1. **Obtenir des données → Requête vide**
2. **Éditeur avancé**
3. **Copier** le contenu de `03_load_data_csv.pq`
4. **OK → Fermer et appliquer**

### Option B : Parquet (Pour Gros Volumes)

```bash
# 1. Convertir CSV → Parquet
python migrate_qvd.py --export-folder "C:\Export" --csv-to-parquet

# 2. Générer script Power Query Parquet
python migrate_qvd.py --export-folder "C:\Export" --generate-powerquery --use-parquet
```

**Puis dans Power BI** (même processus)

---

## 🚀 Workflow Complet Automatisé

```bash
python migrate_qvd.py --qvd-folder "C:\QlikData\QVD" --export-folder "C:\Export" --full-workflow
```

**Ce que fait cette commande :**
1. ✅ Génère le script Qlik
2. ⏸️ Pause (vous exécutez le script Qlik)
3. ✅ Convertit CSV → Parquet
4. ✅ Génère script Power Query

---

## 📊 Exemples Concrets

### Exemple 1 : Petits Fichiers (<100 MB total)

```bash
# Générer script pour export CSV
python migrate_qvd.py --qvd-folder "C:\Data\QVD" --export-folder "C:\Export" --generate-qlik-script

# Après export Qlik, générer Power Query
python migrate_qvd.py --export-folder "C:\Export" --generate-powerquery
```

### Exemple 2 : Gros Fichiers (>100 MB)

```bash
# Workflow complet avec Parquet
python migrate_qvd.py --qvd-folder "C:\Data\QVD" --export-folder "C:\Export" --full-workflow
```

---

## ✅ Checklist

- [ ] Python installé avec `pandas` et `pyarrow`
- [ ] QlikView ou Qlik Sense Desktop installé
- [ ] Accès aux fichiers QVD
- [ ] Dossier d'export créé
- [ ] Script `migrate_qvd.py` disponible

---

## 🔧 Installation Dépendances

```bash
pip install pandas pyarrow
```

---

## ⏱️ Temps Total

- **Génération scripts** : 1 min
- **Export Qlik** : 2-10 min (selon volume)
- **Conversion Parquet** : 1-5 min (optionnel)
- **Import Power BI** : 2-5 min

**Total : 10-20 minutes**

---

## 💡 Astuces

### Si vous avez beaucoup de QVD
Utilisez Parquet pour réduire la taille de 70-80% :
```bash
--csv-to-parquet --use-parquet
```

### Si les données sont dans SQL/Oracle
Voir [MIGRATION_QVD_GUIDE.md](MIGRATION_QVD_GUIDE.md) → Section "Reconnexion Source Originale"

### Si erreurs d'encodage
Les scripts générés utilisent UTF-8 par défaut, compatible Power BI.

---

## 📚 Documentation Complète

**Guide détaillé :** [MIGRATION_QVD_GUIDE.md](MIGRATION_QVD_GUIDE.md)

**Toutes les options du script :**
```bash
python migrate_qvd.py --help
```

---

## 🎯 Prêt !

Lancez votre première migration:
```bash
python migrate_qvd.py --qvd-folder "VotreDossierQVD" --export-folder "Export" --full-workflow
```

**🚀 C'est parti !**
