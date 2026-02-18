"""
Migration des Connecteurs REST/API Qlik vers Power BI

Ce module génère des guides pour migrer les connexions REST/API Qlik
vers les connecteurs Power BI / Power Query.

Author: Migration Team
Date: 2026-02-13
"""

import json
from pathlib import Path
from typing import Dict, List
import argparse


def generate_rest_api_migration_guide(output_dir: Path) -> str:
    """Génère un guide complet de migration REST/API."""
    guide_path = output_dir / "REST_API_MIGRATION_GUIDE.md"
    
    guide_content = """# 🌐 Guide Migration - REST/API Connectors Qlik vers Power BI

**Date de génération :** 13 février 2026

---

## 📋 Vue d'Ensemble

### Qlik → Power BI Mapping

| Qlik | Power BI | Type | Effort |
|------|----------|------|--------|
| **REST Connector** | Web.Contents() / Power Query | Natif | Faible |
| **Custom Connectors** | Custom Connectors / Power Query | Custom | Moyen |
| **OAuth 2.0** | OAuth 2.0 Credentials | Natif | Moyen |
| **API Keys** | Web.Contents Header | Natif | Faible |
| **Webhook Triggers** | Power Automate Flows | Alternatif | Moyen |

---

## 🔗 Connecteurs REST - Approches

### Approche 1 : Web.Contents() - Plus Simple

**Pour :** API publiques, authentification simple

```powerquery
let
    Source = Json.Document(
        Web.Contents(
            "https://api.example.com/data",
            [
                Headers = [
                    #"Authorization" = "Bearer YOUR_TOKEN"
                ]
            ]
        )
    ),
    Data = Source[data],
    Expanded = Table.ExpandRecordColumn(Data, "columns", {"id", "name"}, {"id", "name"})
in
    Expanded
```

**Avantages :**
- ✅ Intégré Power BI/Query
- ✅ Pas de code externe
- ✅ Multi-langues (JSON, XML, CSV)

**Limitations :**
- ❌ Pas de cache (lent si grosse API)
- ❌ Erreurs réseaux sans retry
- ❌ OAuth limité

---

### Approche 2 : Custom Connector - Plus Flexible

**Pour :** API propriétaires, logique complexe

**Créer extension Power BI :**

```powerquery
section REST_API_Connector;

[DataSource.Kind="REST_API_Connector", Publish="0.0.1"]
shared REST_API_Connector.Contents = Value.ReplaceType(
    RestApiConnectorImpl,
    RestApiConnectorType
);

RestApiConnectorImpl = (
    url as text,
    optional parameters as nullable record
) as table =>
let
    DefaultParameters = [
        #"timeout" = 600,
        #"retry_count" = 3
    ],
    FinalParameters = parameters & DefaultParameters,
    Response = Web.Contents(
        url,
        FinalParameters
    ),
    Json = Json.Document(Response),
    TableFromJson = Record.ToTable(Json)
in
    TableFromJson;

RestApiConnectorType = type function (
    url as (type text meta [Documentation.FieldCaption = "API URL"]),
    optional parameters as (type nullable record)
) as table;
```

**Avantages :**
- ✅ Logique réutilisable
- ✅ Gestion erreurs avancée
- ✅ Caching possible
- ✅ Versioning

**Limitations :**
- ❌ Effort développement
- ❌ Maintenance requise
- ❌ Tests nécessaires

---

### Approche 3 : Power Automate - Alternative

**Pour :** Intégrations asynchrones, webhooks

```json
{
  "name": "API Sync to Data Lake",
  "triggers": [
    {
      "type": "recurrence",
      "recurrence": {
        "frequency": "day",
        "interval": 1
      }
    }
  ],
  "actions": [
    {
      "type": "http",
      "method": "GET",
      "uri": "https://api.example.com/data",
      "headers": {
        "Authorization": "Bearer @{variables('api_token')}"
      }
    },
    {
      "type": "create_blob",
      "inputs": {
        "path": "/raw/api_data_@{utcNow('yyyy-MM-dd')}.json",
        "content": "@body('HTTP')"
      }
    }
  ]
}
```

**Avantages :**
- ✅ Pas de Power Query à écrire
- ✅ Logique métier séparée
- ✅ Retry + erreurs gérées
- ✅ Actions supplémentaires (mail, Teams, etc.)

**Limitations :**
- ❌ Latence (asynchrone)
- ❌ Dépendance Power Automate
- ❌ Coûts supplémentaires

---

## 🔐 Authentification

### Option 1 : API Key

**Qlik :**
```qlik
SET @ApiKey = 'your-api-key-here';

LOAD *
FROM [https://api.example.com/data?key=$(ApiKey)]
FOR EACH ApiKey;
```

**Power Query :**
```powerquery
let
    ApiKey = "your-api-key-here",
    Source = Json.Document(
        Web.Contents(
            "https://api.example.com/data",
            [
                Headers = [
                    #"X-API-Key" = ApiKey
                ]
            ]
        )
    )
in
    Source
```

**Alternative Native :**
- Stocker clé en Web.Contents directement
- Ou utiliser Power BI Credentials

---

### Option 2 : OAuth 2.0

**Power Query Native :**

```powerquery
let
    ClientID = "your-client-id",
    ClientSecret = "your-client-secret",
    AuthUrl = "https://api.example.com/oauth/token",
    
    GetToken = Json.Document(
        Web.Contents(
            AuthUrl,
            [
                Content = Text.ToBinary(
                    "grant_type=client_credentials&client_id=" & ClientID & 
                    "&client_secret=" & ClientSecret
                ),
                Headers = [#"Content-Type" = "application/x-www-form-urlencoded"]
            ]
        )
    ),
    
    Token = GetToken[access_token],
    
    Source = Json.Document(
        Web.Contents(
            "https://api.example.com/data",
            [
                Headers = [
                    #"Authorization" = "Bearer " & Token
                ]
            ]
        )
    )
in
    Source
```

---

### Option 3 : Basic Auth

```powerquery
let
    Username = "user@example.com",
    Password = "password123",
    Credentials = "Basic " & Binary.ToText(
        Text.ToBinary(Username & ":" & Password),
        BinaryEncoding.Base64
    ),
    
    Source = Json.Document(
        Web.Contents(
            "https://api.example.com/data",
            [
                Headers = [#"Authorization" = Credentials]
            ]
        )
    )
in
    Source
```

---

## 🛠️ Patterns API Courants

### Pattern 1 : Pagination

**Qlik avec Loop :**
```qlik
FOR i = 1 TO 100
    LOAD *
    FROM [https://api.example.com/data?page=$(i)];
NEXT i
```

**Power Query avec Loop :**
```powerquery
let
    GeneratePages = List.Generate(
        () => 1,
        each _ <= 100,
        each _ + 1
    ),
    
    FetchPages = List.Transform(
        GeneratePages,
        each Json.Document(
            Web.Contents(
                "https://api.example.com/data?page=" & Text.From(_),
                [Headers = [#"Authorization" = "Bearer TOKEN"]]
            )
        )
    ),
    
    Combine = List.Combine(
        List.Transform(FetchPages, each _[data])
    ),
    
    AsTable = Table.FromList(
        Combine,
        Splitter.SplitByNothing(),
        null,
        ExtraValues.Error
    )
in
    AsTable
```

---

### Pattern 2 : Filtrage avec Paramètres

**Qlik :**
```qlik
SET @StartDate = '2025-01-01';
SET @EndDate = '2025-12-31';

LOAD *
FROM [https://api.example.com/data?start=$(StartDate)&end=$(EndDate)];
```

**Power Query :**
```powerquery
let
    StartDate = Date.ToText(Date.From("2025-01-01"), "yyyy-MM-dd"),
    EndDate = Date.ToText(Date.From("2025-12-31"), "yyyy-MM-dd"),
    
    BaseUrl = "https://api.example.com/data",
    QueryUrl = BaseUrl & "?start=" & StartDate & "&end=" & EndDate,
    
    Source = Json.Document(
        Web.Contents(QueryUrl)
    )
in
    Source
```

---

### Pattern 3 : Gestion Erreurs + Retry

```powerquery
let
    Url = "https://api.example.com/data",
    Headers = [#"Authorization" = "Bearer TOKEN"],
    
    SafeWebContents = 
        let
            Attempt = try Web.Contents(Url, [Headers = Headers]) otherwise null
        in
            if Attempt = null then Error.Record("API Error", "Failed to fetch") else Attempt,
    
    Data = try Json.Document(SafeWebContents) otherwise [error = "JSON Parse Failed"],
    
    Result = 
        if Record.HasFields(Data, "error") then
            error Error.Record("API Error", Data[error])
        else
            Data
in
    Result
```

---

## 📊 Migration Checklist

| Élément | Qlik | Power BI | Notes |
|---------|------|----------|-------|
| **URL** | ✅ | ✅ | Directement |
| **Auth** | ✅ | ⚠️ | Dépend type |
| **Headers** | ✅ | ✅ | Via headers |
| **Pagination** | ✅ | ⚠️ | Requis loop |
| **Refresh** | Automatique | Manuel → Automatisé | Scheduling |
| **Error Handling** | Basique | ✅ | try/catch |
| **Caching** | Natif | ❌ | Via parquet |

---

## 🚀 Étapes Migration

### Étape 1 : Documenter API Qlik

1. **Lister toutes API utilisées**
2. **Noter URL, authentification, paramètres**
3. **Documenter structure réponse**

```json
{
  "api_name": "Customer API",
  "url": "https://api.example.com/customers",
  "auth_type": "Bearer Token",
  "headers": {
    "Authorization": "Bearer {{token}}",
    "X-API-Version": "v2"
  },
  "method": "GET",
  "parameters": [
    {
      "name": "page",
      "type": "integer",
      "required": false
    }
  ],
  "response_structure": {
    "type": "json",
    "root": "data"
  },
  "refresh_frequency": "daily"
}
```

### Étape 2 : Tester Connecteur Power Query

1. **Power BI Desktop → Données → Web**
2. **Paster URL API**
3. **Tester authentification**
4. **Valider structure données**

### Étape 3 : Transformer et Charger

1. **Expansion JSON/XML si nécessaire**
2. **Transformation colonnes types**
3. **Chargement modèle**

### Étape 4 : Automatiser Refresh

1. **Power BI Service → Paramètres dataset**
2. **Configurer refresh programmé**
3. **Tester alertes erreurs**

---

## 💡 Best Practices

### ✅ À Faire

1. **Stocker credentials séparement** (Azure Key Vault, Power BI Gateway)
2. **Implémenter retry logic** (exponential backoff)
3. **Monitorer quotas API** (rate limiting)
4. **Cacher réponse** (JSON/parquet)
5. **Documenter API structure**

### ⚠️ À Éviter

1. ❌ Credentials en dur dans Power Query
2. ❌ Refresh trop fréquent (quotas)
3. ❌ Pas de timeout
4. ❌ Pas de validation erreurs
5. ❌ URL non documentée

---

## 🔌 Connecteurs Power BI Préconfigurés

Pour APIs populaires, Power BI a des connectors natifs :

- ✅ **Salesforce** - Connecteur natif
- ✅ **Dynamics 365** - Connecteur natif
- ✅ **Google Analytics** - Connecteur natif
- ✅ **Stripe** - Connecteur community
- ✅ **HubSpot** - Connecteur community
- ✅ **Slack** - Connecteur natif
- ✅ **Azure Services** - Connecteurs natifs

**Préférer connecteurs natifs quand disponibles !**

---

## 📞 Dépannage

### Erreur : "403 Forbidden"

**Causes :**
- ❌ Token expiré
- ❌ API Key incorrect
- ❌ Permissions insuffisantes

**Solutions :**
1. Régénérer token/clé
2. Vérifier permissions API
3. Tester avec Postman/curl

### Erreur : "Timeout"

**Causes :**
- ❌ API lente
- ❌ Réponse trop grosse
- ❌ Rate limiting

**Solutions :**
1. Ajouter pagination
2. Ajouter filters/where
3. Augmenter timeout

### Erreur : "Rate Limited (429)"

**Causes :**
- ❌ Trop de requêtes

**Solutions :**
1. Ajouter delay entre appels
2. Réduire fréquence refresh
3. Contacter API provider

---

## 📚 Ressources

- [Web.Contents Documentation](https://docs.microsoft.com/power-query/web-contents)
- [Custom Connectors Guide](https://learn.microsoft.com/power-query/custom-connector)
- [Power Automate HTTP Actions](https://learn.microsoft.com/power-automate)
- [API Security Best Practices](https://owasp.org/www-project-api-security/)

---

**✨ Guide généré automatiquement par migrate_rest_api.py**
"""
    
    with open(guide_path, 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    return str(guide_path)


def generate_api_templates(output_dir: Path) -> str:
    """Génère des templates Power Query pour APIs courants."""
    template_path = output_dir / "api_templates.pq"
    
    templates = """// Templates Power Query pour Connecteurs REST/API

// ==========================================
// TEMPLATE 1: API Simple avec Bearer Token
// ==========================================
let
    Url = "https://api.example.com/endpoint",
    Token = "your-bearer-token-here",
    
    Source = Json.Document(
        Web.Contents(
            Url,
            [
                Headers = [
                    #"Authorization" = "Bearer " & Token,
                    #"Content-Type" = "application/json"
                ]
            ]
        )
    ),
    
    Data = Source[data],
    AsTable = Table.FromList(Data, Splitter.SplitByNothing(), null, ExtraValues.Error)
in
    AsTable


// ==========================================
// TEMPLATE 2: API avec Pagination
// ==========================================
let
    Url = "https://api.example.com/items",
    Token = "your-bearer-token-here",
    PageSize = 100,
    
    GetPage = (PageNumber as number) =>
        let
            PageUrl = Url & "?page=" & Text.From(PageNumber) & "&limit=" & Text.From(PageSize),
            Response = Json.Document(
                Web.Contents(
                    PageUrl,
                    [Headers = [#"Authorization" = "Bearer " & Token]]
                )
            ),
            Items = Response[items],
            HasMore = Response[has_more]
        in
            {Items, HasMore},
    
    PageNumbers = List.Generate(
        () => 1,
        each _[1],  // Continuer tant que HasMore = true
        each let next = _ + 1 in {next, true}
    ),
    
    AllPages = List.Transform(PageNumbers, each GetPage(_)),
    AllItems = List.Combine(List.Transform(AllPages, each _[1])),
    
    AsTable = Table.FromList(AllItems, Splitter.SplitByNothing(), null, ExtraValues.Error)
in
    AsTable


// ==========================================
// TEMPLATE 3: API avec Filtres et Paramètres
// ==========================================
let
    Url = "https://api.example.com/records",
    Token = "your-bearer-token",
    
    // Paramètres Power BI (à remplacer dynamiquement)
    StartDate = Text.From(Date.From("2025-01-01"), "yyyy-MM-dd"),
    EndDate = Text.From(Date.From("2025-12-31"), "yyyy-MM-dd"),
    Status = "active",
    
    QueryUrl = Url 
        & "?start_date=" & StartDate
        & "&end_date=" & EndDate
        & "&status=" & Status,
    
    Source = Json.Document(
        Web.Contents(
            QueryUrl,
            [
                Headers = [#"Authorization" = "Bearer " & Token],
                Timeout = #duration(0, 0, 5, 0)
            ]
        )
    ),
    
    AsTable = Table.FromList(Source[results], Splitter.SplitByNothing(), null, ExtraValues.Error)
in
    AsTable


// ==========================================
// TEMPLATE 4: API avec Gestion Erreurs
// ==========================================
let
    Url = "https://api.example.com/data",
    Token = "your-bearer-token",
    MaxRetries = 3,
    
    TryFetch = (attempt as number) =>
        let
            Result = try (
                Json.Document(
                    Web.Contents(
                        Url,
                        [
                            Headers = [#"Authorization" = "Bearer " & Token],
                            Timeout = #duration(0, 0, 1, 0)
                        ]
                    )
                )
            ) otherwise (
                if attempt < MaxRetries then TryFetch(attempt + 1) else error "API Failed"
            )
        in
            Result,
    
    Data = TryFetch(1),
    AsTable = Table.FromList(Data[items], Splitter.SplitByNothing(), null, ExtraValues.Error)
in
    AsTable


// ==========================================
// TEMPLATE 5: API OAuth 2.0
// ==========================================
let
    ClientID = "your-client-id",
    ClientSecret = "your-client-secret",
    TokenUrl = "https://api.example.com/oauth/token",
    DataUrl = "https://api.example.com/data",
    
    // Obtenir token
    TokenResponse = Json.Document(
        Web.Contents(
            TokenUrl,
            [
                Content = Text.ToBinary(
                    "grant_type=client_credentials"
                    & "&client_id=" & ClientID
                    & "&client_secret=" & ClientSecret
                ),
                Headers = [
                    #"Content-Type" = "application/x-www-form-urlencoded",
                    #"Accept" = "application/json"
                ]
            ]
        )
    ),
    
    Token = TokenResponse[access_token],
    
    // Utiliser token
    Source = Json.Document(
        Web.Contents(
            DataUrl,
            [
                Headers = [#"Authorization" = "Bearer " & Token]
            ]
        )
    ),
    
    AsTable = Table.FromList(Source[data], Splitter.SplitByNothing(), null, ExtraValues.Error)
in
    AsTable


// ==========================================
// TEMPLATE 6: API GraphQL
// ==========================================
let
    Url = "https://api.example.com/graphql",
    Token = "your-bearer-token",
    
    Query = 
        "query { 
            users { 
                id 
                name 
                email 
            } 
        }",
    
    Payload = Json.FromValue([query = Query]),
    
    Source = Json.Document(
        Web.Contents(
            Url,
            [
                Content = Payload,
                Headers = [
                    #"Authorization" = "Bearer " & Token,
                    #"Content-Type" = "application/json"
                ]
            ]
        )
    ),
    
    Data = Source[data][users],
    AsTable = Table.FromList(Data, Splitter.SplitByNothing(), null, ExtraValues.Error)
in
    AsTable


// ==========================================
// TEMPLATE 7: API CSV/TSV
// ==========================================
let
    Url = "https://api.example.com/export.csv",
    Token = "your-bearer-token",
    
    Source = Csv.Document(
        Web.Contents(
            Url,
            [
                Headers = [#"Authorization" = "Bearer " & Token]
            ]
        ),
        [
            Delimiter = ",",
            Columns = 0,
            Encoding = 65001,
            QuoteStyle = QuoteStyle.Csv
        ]
    ),
    
    PromotedHeaders = Table.PromoteHeaders(Source)
in
    PromotedHeaders


// ==========================================
// TEMPLATE 8: API XML
// ==========================================
let
    Url = "https://api.example.com/data.xml",
    Token = "your-bearer-token",
    
    Source = Xml.Tables(
        Web.Contents(
            Url,
            [
                Headers = [#"Authorization" = "Bearer " & Token]
            ]
        )
    ),
    
    Items = Source{[Name = "items"]}[Table],
    Expanded = Table.ExpandTableColumn(
        Items, 
        "item", 
        Table.ColumnNames(Items[[item]][[item]])
    )
in
    Expanded


// ==========================================
// TEMPLATE 9: Combiner Multiples API
// ==========================================
let
    Token = "your-bearer-token",
    
    ApiCall = (endpoint as text) =>
        Json.Document(
            Web.Contents(
                "https://api.example.com/" & endpoint,
                [Headers = [#"Authorization" = "Bearer " & Token]]
            )
        ),
    
    Users = ApiCall("users"),
    Orders = ApiCall("orders"),
    Products = ApiCall("products"),
    
    UserTable = Table.FromList(Users[items], Splitter.SplitByNothing(), null, ExtraValues.Error),
    OrderTable = Table.FromList(Orders[items], Splitter.SplitByNothing(), null, ExtraValues.Error),
    ProductTable = Table.FromList(Products[items], Splitter.SplitByNothing(), null, ExtraValues.Error),
    
    Combined = Table.Combine({UserTable, OrderTable, ProductTable})
in
    Combined


// ==========================================
// HELPER: Exponential Backoff Retry
// ==========================================
let
    ExponentialBackoffRetry = (
        Url as text,
        Headers as record,
        optional MaxAttempts as number,
        optional BaseDelay as number
    ) =>
        let
            Attempts = MaxAttempts ?? 5,
            Delay = BaseDelay ?? 100,  // millisecondes
            
            RetryLoop = (attempt as number) =>
                let
                    Result = try Web.Contents(Url, [Headers = Headers]) otherwise null
                in
                    if Result <> null then
                        Result
                    else if attempt < Attempts then
                        let
                            WaitTime = Delay * Number.Power(2, attempt - 1),
                            _ = Duration.From(#duration(0, 0, 0, WaitTime / 1000))
                        in
                            RetryLoop(attempt + 1)
                    else
                        error "Max retries exceeded"
        in
            RetryLoop(1)
in
    ExponentialBackoffRetry
"""
    
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(templates)
    
    return str(template_path)


def generate_api_inventory(output_dir: Path) -> str:
    """Génère un template d'inventaire API pour documenter toutes les connexions."""
    inventory_path = output_dir / "api_inventory_template.json"
    
    inventory = {
        "apis": [
            {
                "name": "Customer API",
                "qlik_usage": "LOAD * FROM [https://api.example.com/customers]",
                "power_bi_equivalent": "Web.Contents with Bearer Token",
                "frequency": "daily",
                "authentication": "bearer_token",
                "endpoints": [
                    {
                        "path": "/customers",
                        "method": "GET",
                        "parameters": ["page", "limit"]
                    }
                ],
                "response_format": "json",
                "migration_status": "planned",
                "effort_hours": 2,
                "notes": "Example API migration"
            }
        ],
        "migration_summary": {
            "total_apis": 1,
            "migrated": 0,
            "in_progress": 0,
            "planned": 1,
            "total_effort_hours": 2
        }
    }
    
    with open(inventory_path, 'w', encoding='utf-8') as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)
    
    return str(inventory_path)


def main():
    parser = argparse.ArgumentParser(
        description="Migrer connecteurs REST/API Qlik vers Power BI"
    )
    parser.add_argument(
        "--output-dir",
        default="output/rest_api",
        help="Répertoire de sortie"
    )
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("🌐 Génération guides REST/API...")
    
    guide_file = generate_rest_api_migration_guide(output_dir)
    print(f"✅ Guide: {guide_file}")
    
    template_file = generate_api_templates(output_dir)
    print(f"✅ Templates Power Query: {template_file}")
    
    inventory_file = generate_api_inventory(output_dir)
    print(f"✅ Inventaire API: {inventory_file}")
    
    print(f"\n📊 Fichiers générés:")
    print(f"  - {guide_file}")
    print(f"  - {template_file}")
    print(f"  - {inventory_file}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
