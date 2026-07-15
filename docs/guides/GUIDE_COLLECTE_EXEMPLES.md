<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# 📥 Guide - Collecter Exemples Qlik pour Tests

## 🎯 Objectif

Collecter 10-20 fichiers QVF d'exemples pour tester l'outil de migration `migrate_qvf.py`.

---

## 🔗 Sources d'Exemples Gratuits

### 1️⃣ Qlik Sense Desktop (RECOMMANDÉ)

**Applications incluses lors de l'installation :**

**📥 Installation :**
1. Télécharger : https://www.qlik.com/us/try-or-buy/download-qlik-sense
2. Installer Qlik Sense Desktop (gratuit)
3. Lancer Qlik Sense Desktop

**📂 Applications de démonstration incluses :**
- **Beginner's Tutorial** - Tutoriel débutant
- **Consumer Sales** - Analyse ventes
- **Executive Dashboard** - Tableau de bord exécutif  
- **Helpdesk Management** - Gestion support

**📁 Emplacement fichiers QVF :**
```
C:\Users\<votre_nom>\Documents\Qlik\Sense\Apps\
```

**✅ Avantages :**
- Gratuit, aucun compte requis
- QVF au format Desktop (ZIP) ✅
- Apps variées (petites, moyennes tailles)
- Immédiatement disponibles

---

### 2️⃣ Qlik Community

**📥 Télécharger apps communauté :**

**URL :** https://community.qlik.com/t5/Qlik-Sense-Documents/tkb-p/qlik-sense-documents

**Applications populaires :**
- Sales Dashboard
- Financial Analysis
- HR Analytics
- Inventory Management
- Customer 360

**Procédure :**
1. Aller sur community.qlik.com
2. Rechercher "QVF download"
3. Filtrer par "Qlik Sense" et "Sample Apps"
4. Télécharger fichiers .qvf

**✅ Avantages :**
- Grande variété d'apps
- Apps réelles créées par utilisateurs
- Différents niveaux de complexité

---

### 3️⃣ GitHub - Repositories Qlik

**🔍 Recherche GitHub :**

```
Site: github.com
Recherche: "qlik sense qvf"
          "extension:qvf"
          "qlik sample app"
```

**Repos intéressants :**

**A. Qlik-Oss (Organisation officielle) :**
- https://github.com/qlik-oss
- Exemples d'intégrations
- Applications de démonstration

**B. Exemples communauté :**
```bash
# Exemples de recherche GitHub
https://github.com/search?q=extension%3Aqvf
https://github.com/search?q=qlik+sense+demo
```

**Procédure :**
1. Chercher sur github.com
2. Filtrer fichiers .qvf
3. Télécharger (bouton "Download" ou "Raw")

**⚠️ Note :** Certains repos peuvent contenir QVF Cloud (binaire)

---

### 4️⃣ Qlik Branch (Developer Portal)

**📥 Apps développeurs :**

**URL :** https://developer.qlik.com/

**Contenu :**
- Extensions Qlik Sense
- Applications exemples
- Templates

**Procédure :**
1. Créer compte gratuit sur developer.qlik.com
2. Section "Sample Apps"
3. Télécharger QVF

**✅ Avantages :**
- Apps techniques avancées
- Extensions et visualisations custom

---

### 5️⃣ Qlik Help - Sample Data

**📥 Datasets officiels :**

**URL :** https://help.qlik.com/en-US/sense/Subsystems/Hub/Content/Sense_Hub/Samples/sample-apps.htm

**Contenu :**
- Fichiers de données (Excel, CSV)
- Apps de démonstration

**Utilisation :**
- Télécharger données
- Créer apps Qlik simples
- Tester migration données

---

## 📁 Organisation Recommandée

### Structure Dossiers

```
test_samples/
├── small/                      ← Fichiers < 1 MB
│   ├── tutorial_beginner.qvf
│   └── simple_sales.qvf
│
├── medium/                     ← Fichiers 1-10 MB
│   ├── consumer_sales.qvf
│   ├── helpdesk.qvf
│   └── executive_dashboard.qvf
│
├── large/                      ← Fichiers 10-100 MB
│   └── enterprise_analytics.qvf
│
└── cloud_format/               ← QVF Cloud (binaire)
    └── demo_app_cloud.qvf
```

### Créer Structure

```bash
# PowerShell
cd "c:\Users\pidoudet\OneDrive - Microsoft\Boulot\PBI SME\OracleToPostgre\fabric-deployment"

mkdir test_samples
mkdir test_samples\small
mkdir test_samples\medium
mkdir test_samples\large
mkdir test_samples\cloud_format
```

---

## 🚀 Quick Start - Collecter 5 Exemples (10 min)

### Option A : Depuis Qlik Sense Desktop

```powershell
# 1. Installer Qlik Sense Desktop (si pas déjà fait)
# https://www.qlik.com/us/try-or-buy/download-qlik-sense

# 2. Lancer Qlik Sense Desktop une fois (charge apps démo)

# 3. Copier apps vers test_samples
$source = "$env:USERPROFILE\Documents\Qlik\Sense\Apps"
$dest = "test_samples\medium"

# Copier tous les QVF
Copy-Item "$source\*.qvf" -Destination $dest -Force

Write-Host "✅ Apps copiées dans test_samples\medium"
Get-ChildItem $dest -Filter "*.qvf"
```

### Option B : Téléchargement Manuel

**1. Beginner Tutorial (Petit - 0.5 MB) :**
- Source : Qlik Sense Desktop inclus
- Copier vers : `test_samples\small\`

**2. Consumer Sales (Moyen - 3 MB) :**
- Source : Qlik Sense Desktop inclus
- Copier vers : `test_samples\medium\`

**3. Executive Dashboard (Moyen - 5 MB) :**
- Source : Qlik Sense Desktop inclus
- Copier vers : `test_samples\medium\`

**4. Helpdesk Management (Moyen - 2 MB) :**
- Source : Qlik Sense Desktop inclus
- Copier vers : `test_samples\medium\`

**5. Demo App Cloud (Cloud Format - 0.3 MB) :**
- Source : Déjà testé !
- `C:\Users\pidoudet\Downloads\ReportingExampleMaterials\ReportingExampleMaterials\Demo App - Qlik Cloud Reporting.qvf`
- Copier vers : `test_samples\cloud_format\`

---

## ✅  Vérification Exemples

### Script Vérification

```powershell
# Compter fichiers QVF collectés
$small = (Get-ChildItem "test_samples\small\*.qvf" -ErrorAction SilentlyContinue).Count
$medium = (Get-ChildItem "test_samples\medium\*.qvf" -ErrorAction SilentlyContinue).Count
$large = (Get-ChildItem "test_samples\large\*.qvf" -ErrorAction SilentlyContinue).Count
$cloud = (Get-ChildItem "test_samples\cloud_format\*.qvf" -ErrorAction SilentlyContinue).Count

$total = $small + $medium + $large + $cloud

Write-Host "`n📊 INVENTAIRE EXEMPLES QVF"
Write-Host "=========================="
Write-Host "Small   : $small fichier(s)"
Write-Host "Medium  : $medium fichier(s)"
Write-Host "Large   : $large fichier(s)"
Write-Host "Cloud   : $cloud fichier(s)"
Write-Host "=========================="
Write-Host "TOTAL   : $total fichier(s)`n"

if ($total -ge 5) {
    Write-Host "✅ Suffisant pour lancer tests (minimum 5)" -ForegroundColor Green
} else {
    Write-Host "⚠️ Besoin de plus d'exemples (5 minimum recommandé)" -ForegroundColor Yellow
}
```

---

## 🧪 Lancer Tests une Fois Exemples Collectés

```bash
# Vérifier exemples disponibles
python test_migration_suite.py --input test_samples --output test_results

# Ou par catégorie
python test_migration_suite.py --input test_samples/medium
```

**Résultats :**
- `test_results/test_report_YYYYMMDD.json` - Rapport JSON
- `test_results/test_report_YYYYMMDD.html` - Rapport HTML (ouvrir dans navigateur)

---

## 💡 Créer Ses Propres Apps Qlik (Optionnel)

### Avec Qlik Sense Desktop

**1. Installer Qlik Sense Desktop**

**2. Créer app simple :**
```
1. Lancer Qlik Sense Desktop
2. Créer nouvelle app
3. Ajouter données (Excel/CSV)
4. Créer quelques visualisations
5. Menu → Exporter → Enregistrer .qvf
6. Copier vers test_samples/
```

**3. Exemples de données à utiliser :**
- Fichiers dans `ReportingExampleMaterials/` (déjà disponibles)
- Datasets Kaggle (CSV)
- Vos propres données Excel

---

## 📋 Checklist Collecte

- [ ] Qlik Sense Desktop installé
- [ ] Au moins 5 fichiers QVF collectés
- [ ] Structure dossiers `test_samples/` créée
- [ ] Fichiers organisés par taille (small/medium/large)
- [ ] Au moins 1 fichier Cloud format pour tester détection
- [ ] Script vérification exécuté
- [ ] Prêt à lancer `test_migration_suite.py`

---

## 🎯 Objectif Minimum / Idéal

| Catégorie | Minimum | Idéal |
|-----------|---------|-------|
| **Small** | 2 | 5 |
| **Medium** | 3 | 10 |
| **Large** | 0 | 3 |
| **Cloud** | 1 | 2 |
| **TOTAL** | **5** | **20** |

---

## ⚡ Script Automatique de Collecte

```powershell
# Script complet de collecte depuis Qlik Sense Desktop

$qlikApps = "$env:USERPROFILE\Documents\Qlik\Sense\Apps"
$testSamples = "test_samples"

# Créer structure
@("small", "medium", "large", "cloud_format") | ForEach-Object {
    New-Item -ItemType Directory -Path "$testSamples\$_" -Force | Out-Null
}

# Copier apps Qlik Desktop si disponibles
if (Test-Path $qlikApps) {
    $qvfs = Get-ChildItem "$qlikApps\*.qvf"
    
    foreach ($qvf in $qvfs) {
        $sizeMB = $qvf.Length / 1MB
        
        $dest = if ($sizeMB -lt 1) { "small" }
                elseif ($sizeMB -lt 10) { "medium" }
                else { "large" }
        
        Copy-Item $qvf.FullName -Destination "$testSamples\$dest\" -Force
        Write-Host "✅ Copié: $($qvf.Name) → $dest/ ($([math]::Round($sizeMB, 2)) MB)"
    }
}

# Copier Demo App Cloud si disponible
$cloudDemo = "C:\Users\pidoudet\Downloads\ReportingExampleMaterials\ReportingExampleMaterials\Demo App - Qlik Cloud Reporting.qvf"
if (Test-Path $cloudDemo) {
    Copy-Item $cloudDemo -Destination "$testSamples\cloud_format\" -Force
    Write-Host "✅ Copié: Demo App Cloud → cloud_format/"
}

Write-Host "`n✅ Collecte terminée!"
Write-Host "`n📊 Lancer tests avec:"
Write-Host "python test_migration_suite.py --input test_samples --output test_results"
```

**Sauvegarder comme :** `collect_samples.ps1`

**Exécuter :**
```powershell
.\collect_samples.ps1
```

---

## 🎓 Résumé

**Pour tester rapidement (10 min) :**
1. Installer Qlik Sense Desktop
2. Copier apps incluses vers `test_samples/medium/`
3. Copier Demo App Cloud vers `test_samples/cloud_format/`
4. Lancer : `python test_migration_suite.py`

**Pour tests complets (30 min) :**
1. Télécharger 15-20 apps depuis sources variées
2. Organiser par taille
3. Exécuter script `collect_samples.ps1`
4. Lancer tests et analyser rapports HTML

---

**✨ Prêt à collecter et tester !**

📅 **Créé :** 13 février 2026  
🎯 **Objectif :** 5-20 fichiers QVF pour validation outil  
⏱️ **Temps :** 10-30 minutes selon nombre d'exemples

