# 🎯 Guide Utilisation - Scripts Power Query dans Power BI Desktop

## 📦 Vous avez 5 scripts .pq prêts à importer !

**Dossier :** `migration_test_output\`

```
✅ Cities.pq
✅ Customers.pq  
✅ Item_master.pq
✅ Sales.pq
✅ Sales_rep.pq
```

---

## 🚀 Étape par Étape (10 minutes)

### ÉTAPE 1 : Ouvrir Power BI Desktop

1. Lancer **Power BI Desktop**
2. Si page d'accueil : cliquer **"Obtenir des données"**
3. Ou : Ruban → **Accueil** → **Obtenir des données** → **Plus...**

---

### ÉTAPE 2 : Créer Requête Vide

1. Dans la fenêtre "Obtenir des données"
2. Rechercher : **"Requête vide"** ou **"Blank Query"**
3. Sélectionner → **Connecter**

**L'Éditeur Power Query s'ouvre**

---

### ÉTAPE 3 : Importer Premier Script (Sales.pq)

1. **Dans l'Éditeur Power Query** :
   - Ruban → **Accueil** → **Éditeur avancé** (ou **Advanced Editor**)

2. **Une fenêtre de code s'ouvre** avec :
   ```m
   let
       Source = ""
   in
       Source
   ```

3. **Tout sélectionner et supprimer**

4. **Ouvrir le fichier** `migration_test_output\Sales.pq` avec Bloc-notes :
   - Clic droit sur **Sales.pq** → Ouvrir avec → Bloc-notes
   - **Ctrl+A** (tout sélectionner)
   - **Ctrl+C** (copier)

5. **Dans l'Éditeur avancé Power BI** :
   - **Ctrl+V** (coller)
   - Vous devriez voir le script complet qui commence par `let`
   - Cliquer **OK**

6. **Renommer la requête** :
   - Dans le panneau de gauche "Requêtes"
   - Clic droit sur **Query1** → **Renommer**
   - Taper : **Sales**
   - Appuyer sur **Entrée**

7. **Vérifier les données** :
   - L'aperçu des données Sales.xlsx devrait s'afficher
   - ✅ Si vous voyez des colonnes et données → **Succès !**

---

### ÉTAPE 4 : Répéter pour les Autres Scripts

**Répéter l'ÉTAPE 3 pour chaque fichier :**

| Fichier .pq | Renommer Requête en | Ordre |
|-------------|---------------------|-------|
| ✅ Sales.pq | **Sales** | 1 (fait) |
| Cities.pq | **Cities** | 2 |
| Customers.pq | **Customers** | 3 |
| Item_master.pq | **Item Master** | 4 |
| Sales_rep.pq | **Sales Rep** | 5 |

**Pour chaque nouveau script :**
1. Éditeur Power Query → **Nouvelle Source** → **Requête vide**
2. **Éditeur avancé**
3. **Copier-coller** le contenu du fichier .pq
4. **OK**
5. **Renommer** la requête

---

### ÉTAPE 5 : Fermer et Appliquer

1. **Vérifier** que les 5 requêtes sont dans le panneau gauche :
   ```
   📊 Requêtes
   ├── Cities
   ├── Customers
   ├── Item Master
   ├── Sales
   └── Sales Rep
   ```

2. **Ruban** → **Accueil** → **Fermer et appliquer**

3. **Power BI charge les données** → Patience (Sales.xlsx = 11 MB)

4. **✅ Retour à la vue Rapport** avec données chargées !

---

## 🔗 Créer les Relations (5 minutes)

### Passer en Vue Modèle

1. **Barre de gauche** → Icône **Vue Modèle** 🔲🔲 (2ème icône)

Vous voyez maintenant vos 5 tables sous forme de boîtes

---

### Créer Relations Automatiquement

**Power BI peut détecter certaines relations automatiquement**

1. Ruban → **Accueil** → **Gérer les relations**
2. Cliquer **Détection automatique**
3. Power BI cherche colonnes avec noms similaires
4. **Valider** les relations trouvées

---

### Créer Relations Manuelles

**Si détection auto ne trouve pas tout, créer manuellement :**

#### Relation 1 : Sales → Customers

1. **Glisser** le champ **Customer ID** de la table **Sales**
2. **Déposer** sur le champ **ID** (ou **Customer ID**) de la table **Customers**
3. Fenêtre "Créer une relation" s'ouvre :
   - Table : **Sales**
   - Colonne : **Customer ID**
   - Table associée : **Customers**
   - Colonne associée : **ID**
   - Cardinalité : **Plusieurs-à-un** (∞:1)
   - Direction filtre croisé : **Unique**
4. Cliquer **OK**

#### Relation 2 : Sales → Item Master

1. **Glisser** **Item ID** (ou **Product ID**) de **Sales**
2. **Déposer** sur **ID** de **Item Master**
3. **OK**

#### Relation 3 : Sales → Sales Rep

1. **Glisser** **Sales Rep ID** de **Sales**
2. **Déposer** sur **ID** de **Sales Rep**
3. **OK**

#### Relation 4 : Sales → Cities (Optionnel)

1. **Glisser** **City ID** de **Sales**
2. **Déposer** sur **ID** de **Cities**
3. **OK**

---

### Vérifier le Modèle

**Votre modèle devrait ressembler à :**

```
    Cities
       |
       ↓
    Sales ← Customers
       ↓
   Item Master
       ↓
   Sales Rep
```

**Ou en étoile (recommandé) :**

```
        Cities
           ↘
Customers → Sales ← Item Master
           ↗
      Sales Rep
```

---

## 📊 Créer les Mesures (10 minutes)

### Passer en Vue Données ou Rapport

1. Barre gauche → **Vue Rapport** 📊 (1ère icône)

---

### Créer Mesures DAX

1. **Clic droit** sur la table **Sales** (panneau Champs à droite)
2. **Nouvelle mesure**
3. **Copier-coller** les mesures suivantes :

#### Mesure 1 : Total Sales

```dax
Total Sales = SUM(Sales[Sales Amount])
```

ou si colonne s'appelle différemment :

```dax
Total Sales = SUM(Sales[Amount])
```

**Appuyer sur Entrée** → Mesure créée ✅

#### Mesure 2 : Total Quantity

```dax
Total Quantity = SUM(Sales[Quantity])
```

#### Mesure 3 : Average Sale

```dax
Average Sale = AVERAGE(Sales[Sales Amount])
```

#### Mesure 4 : Number of Transactions

```dax
Number of Transactions = COUNTROWS(Sales)
```

#### Mesure 5 : YoY Growth

```dax
YoY Growth % = 
VAR CurrentYear = [Total Sales]
VAR PreviousYear = CALCULATE(
    [Total Sales],
    SAMEPERIODLASTYEAR('Sales'[Date])
)
RETURN
DIVIDE(CurrentYear - PreviousYear, PreviousYear, 0) * 100
```

**Note :** Ajuster si colonne Date s'appelle différemment

---

### Vérifier Mesures

Dans le panneau **Champs** (droite), sous **Sales**, vous devriez voir :

```
📊 Sales
├── 📅 Date
├── 💰 Sales Amount
├── 📦 Quantity
├── ...
└── 📏 Mesures :
    ├── Σ Total Sales
    ├── Σ Total Quantity
    ├── Σ Average Sale
    ├── Σ Number of Transactions
    └── Σ YoY Growth %
```

---

## 🎨 Créer les Visualisations (15 minutes)

### Visual 1 : KPI - Total Sales

1. **Cliquez** sur un espace vide du canevas
2. **Panneau Visualisations** (droite) → Icône **Carte** (Card) 📇
3. **Panneau Champs** → Glisser **Total Sales** dans **Champs**
4. Visual créé ! **Redimensionner** et **Déplacer** en haut à gauche

---

### Visual 2 : KPI - Total Quantity

1. Nouvel espace → **Carte**
2. Glisser **Total Quantity**
3. Placer à côté du premier KPI

---

### Visual 3 : Graphique en Courbes - Sales Trends

1. Nouvel espace → **Graphique en courbes** 📈
2. **Axe X** : Glisser **Date** (depuis table Sales)
3. **Axe Y** : Glisser **Total Sales**
4. Visual affiche l'évolution des ventes dans le temps

---

### Visual 4 : Graphique à Barres - Top Products

1. Nouvel espace → **Graphique à barres groupées** 📊
2. **Axe Y** : Glisser **Product Name** (depuis Item Master)
3. **Axe X** : Glisser **Total Sales**
4. Trier : Clic sur **...** (3 points) → **Trier par Total Sales**

---

### Visual 5 : Carte - Sales by City

1. Nouvel espace → **Carte** (Map) 🌍
2. **Emplacement** : Glisser **City** (depuis Cities)
3. **Taille** : Glisser **Total Sales**
4. Les bulles apparaissent sur la carte

---

### Visual 6 : Table - Top Customers

1. Nouvel espace → **Table** 📋
2. **Colonnes** : 
   - Glisser **Customer Name** (depuis Customers)
   - Glisser **Total Sales**
   - Glisser **Number of Transactions**
3. Trier par **Total Sales** décroissant

---

## 🎯 Résultat Final

**Vous avez maintenant un rapport Power BI complet !**

```
┌─────────────────────────────────────────────────────┐
│  💰 Total Sales    📦 Total Quantity               │
│     $1.2M               45,678                      │
├─────────────────────────────────────────────────────┤
│  📈 Sales Trends                                    │
│  (Graphique en courbes par mois)                    │
├──────────────────────┬──────────────────────────────┤
│  📊 Top Products     │  🌍 Sales by City            │
│  (Barres)            │  (Carte géographique)        │
├──────────────────────┴──────────────────────────────┤
│  📋 Top Customers                                   │
│  (Table avec Name, Sales, Transactions)             │
└─────────────────────────────────────────────────────┘
```

---

## ✅ Checklist Finale

- [ ] 5 scripts .pq importés
- [ ] 5 tables chargées (Sales, Customers, Cities, Item Master, Sales Rep)
- [ ] 4+ relations créées
- [ ] 4+ mesures DAX créées
- [ ] 6+ visualisations créées
- [ ] Rapport interactif fonctionnel

**Temps total : ~40 minutes** ⏱️

---

## 💾 Sauvegarder

**Menu Fichier** → **Enregistrer sous** → Nom : **Demo Sales Report (from Qlik)**

---

## 🚀 Publier (Optionnel)

**Menu Fichier** → **Publier** → **Publier sur Power BI** → Sélectionner Workspace

---

## 🆘 Problèmes Fréquents

### ❌ "Impossible de charger les données"

**Cause :** Chemin fichier invalide dans script .pq

**Solution :**
1. Ouvrir **Éditeur Power Query**
2. Sélectionner requête en erreur
3. **Éditeur avancé**
4. Vérifier ligne `File.Contents("C:\\Users\\...")`
5. Corriger le chemin si fichiers déplacés

---

### ❌ "Type incompatible"

**Cause :** Détection automatique types incorrecte

**Solution :**
1. **Éditeur Power Query** → Sélectionner requête
2. Clic sur en-tête de colonne
3. Ruban → **Transformer** → **Type de données** → Choisir type correct

---

### ❌ "Relation circulaire"

**Cause :** Relations créent une boucle

**Solution :**
1. **Vue Modèle**
2. Identifier relation en trop
3. Supprimer relation problématique
4. Le modèle en étoile (Sales au centre) évite ce problème

---

## 📞 Support

**Documentation :**
- [MIGRATION_QLIK_CLOUD.md](MIGRATION_QLIK_CLOUD.md) - Guide complet
- [TEST_RESUME.md](TEST_RESUME.md) - Résumé test

**Outils :**
```bash
python diagnose_qvf.py <fichier.qvf>
python generate_pq_from_sources.py <dossier>
```

---

**✨ Félicitations ! Votre migration Qlik → Power BI est complète !**

*Guide créé : 13 février 2026*  
*Fichiers sources : Demo App - Qlik Cloud Reporting*  
*Résultat : Rapport Power BI interactif fonctionnel*
