<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# 🚀 Démarrage Rapide - Migration Hybride

## ⚡ En 3 Commandes

### 1️⃣ Migrer votre QVF (2 minutes)

```bash
cd "c:\Users\pidoudet\OneDrive - Microsoft\Boulot\PBI SME\OracleToPostgre\fabric-deployment"

python migrate_qvf.py "CHEMIN\VERS\VOTRE\APP.qvf" "migration_output"
```

**Exemple concret :**
```bash
python migrate_qvf.py "C:\Data\Ventes.qvf" "ventes_migree"
```

**Résultat :**
```
✓ ventes_migree/powerquery_scripts/script.pq    ← Script Power Query
✓ ventes_migree/powerbi_models/model.bim       ← Modèle tabulaire
✓ ventes_migree/powerbi_reports/report.json    ← Visualisations
```

---

### 2️⃣ Dans Power BI Desktop (15 minutes)

#### A. Importer le Modèle

1. **Ouvrir Power BI Desktop**
2. **Fichier → Importer → Modèle de données**
3. Sélectionner : `ventes_migree\powerbi_models\model.bim`
4. ✓ Tables et relations importées !

#### B. Ajouter les Données

1. **Transformer les données** (ouvre Power Query Editor)
2. **Nouvelle source → Requête vide**
3. **Clic droit sur "Requête1" → Éditeur avancé**
4. **Ouvrir** (dans Notepad) : `ventes_migree\powerquery_scripts\script.pq`
5. **Copier tout** le contenu
6. **Coller** dans l'Éditeur avancé (remplacer le contenu)
7. **OK** puis **Fermer et appliquer**

#### C. Créer les Visuels

1. **Ouvrir** (dans Notepad) : `ventes_migree\powerbi_reports\report.json`
2. Pour chaque visualisation listée :
   - Sélectionner le type de visuel (graphique à barres, courbes, etc.)
   - Glisser-déposer les champs indiqués
   - Configurer le titre

**Exemple :**
```json
{
  "type": "barchart",
  "dimensions": ["Product"],
  "measures": ["Sales"]
}
```
→ Créer un **Graphique à barres**, ajouter **Product** en Axe, **Sales** en Valeurs

---

### 3️⃣ Sauvegarder

1. **Fichier → Enregistrer**
2. Nom : `Ventes_Final.pbix`
3. **Terminé ! 🎉**

---

## 📋 Checklist Rapide

- [ ] Migration automatique : `python migrate_qvf.py ...`
- [ ] 3 fichiers créés : `.pq`, `.bim`, `.json` ✓
- [ ] Power BI Desktop ouvert
- [ ] Modèle importé (`Importer → Modèle de données`)
- [ ] Script Power Query copié (Power Query Editor)
- [ ] Données chargées (sans erreurs)
- [ ] Visuels créés (selon le JSON)
- [ ] Fichier sauvegardé

---

## ⏱️ Temps Total

- **Migration auto** : 2 min
- **Import modèle** : 2 min
- **Power Query** : 5 min
- **Visualisations** : 10-15 min
- **Total** : **~20-25 minutes**

---

## 💡 Astuces

### Si le Power Query échoue

Vos **sources de données** Qlik (QVD, SQL) doivent être adaptées :

```powerquery
// Dans le fichier .pq, remplacer :
Source = Expression.Evaluate("data.qvd")

// Par votre source réelle :
Source = Sql.Database("MonServeur", "MaBase")
```

### Si le modèle est vide

Vérifiez que vous avez bien :
1. Importé le `.bim` (Importer → **Modèle de données**, pas Importer → Données)
2. Les relations apparaissent dans l'onglet **Modèle** (icône à gauche)

---

## 📚 Documentation Complète

Pour plus de détails, consultez :
- **[MIGRATION_HYBRIDE_GUIDE.md](MIGRATION_HYBRIDE_GUIDE.md)** - Guide complet pas à pas
- **[README.md](README.md)** - Documentation du projet

---

## ✅ Validation

Pour tester le système, exécutez :

```bash
# Test avec des données exemple
python qvf_examples.py
```

---

**🎯 Vous êtes prêt ! La migration Qlik → Power BI est maintenant à portée de main.**

