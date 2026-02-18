"""
Migration des Webhooks et Automatisation Qlik vers Power Automate

Ce module génère des guides pour migrer les automatisations Qlik vers Power Automate flows.

Author: Migration Team
Date: 2026-02-13
"""

import json
from pathlib import Path
from typing import Dict, List
import argparse


def generate_power_automate_guide(output_dir: Path) -> str:
    """Génère un guide complet Power Automate pour webhooks et automatisation."""
    guide_path = output_dir / "POWER_AUTOMATE_MIGRATION_GUIDE.md"
    
    guide_content = """# ⚡ Guide Migration - Webhooks & Automatisation Qlik vers Power Automate

**Date de génération :** 13 février 2026

---

## 📋 Vue d'Ensemble

### Qlik → Power Automate Mapping

| Qlik | Power Automate | Type | Effort |
|------|-----------------|------|--------|
| **Webhooks** | HTTP Trigger | Natif | Moyen |
| **Alerts** | Notification Actions | Natif | Faible |
| **Scheduled Reload** | Recurrence Trigger | Natif | Faible |
| **Event Triggers** | Custom Events | Natif | Moyen |
| **Email Distribution** | Mail Actions | Natif | Faible |
| **Task Scheduler** | Recurrence + Actions | Natif | Moyen |

---

## 🪝 Webhooks - Migration

### Concept

**Qlik :** Webhook trigger → Script d'actions
**Power Automate :** HTTP Trigger → Cloud Flow

---

### Approche 1 : HTTP Request Trigger - Native

**Pour :** APIs Qlik, webhooks simples

**Créer flow :**

1. **Power Automate → Create cloud flow → Automated**
2. **Choose trigger → HTTP request received**

```json
{
  "trigger": {
    "type": "request",
    "schema": {
      "type": "object",
      "properties": {
        "app_name": {
          "type": "string"
        },
        "timestamp": {
          "type": "string"
        },
        "action": {
          "type": "string"
        },
        "data": {
          "type": "object"
        }
      }
    }
  }
}
```

**Exemple workflow :**

```json
{
  "trigger": {
    "name": "When_a_HTTP_request_is_received",
    "type": "Request",
    "kind": "Http"
  },
  "actions": [
    {
      "name": "Parse_JSON",
      "type": "ParseJson",
      "inputs": {
        "content": "@triggerBody()",
        "schema": {
          "type": "object",
          "properties": {
            "app.name": {"type": "string"},
            "action": {"type": "string"}
          }
        }
      }
    },
    {
      "name": "Send_Email_Notification",
      "type": "ApiConnectionAction",
      "inputs": {
        "host": {
          "connection": {"name": "@parameters('$connections')['office365']['connectionId']"}
        },
        "method": "post",
        "path": "/Mail",
        "body": {
          "to": "admin@company.com",
          "subject": "Qlik App Reloaded: @{body('Parse_JSON')?['app.name']}",
          "body": "Action: @{body('Parse_JSON')?['action']} at @{body('Parse_JSON')?['timestamp']}"
        }
      }
    },
    {
      "name": "Create_Item_in_SharePoint",
      "type": "ApiConnectionAction",
      "inputs": {
        "host": {
          "connection": {"name": "@parameters('$connections')['sharepoint']['connectionId']"}
        },
        "method": "post",
        "path": "/sites/{site}/lists/{list}/items",
        "body": {
          "Title": "Webhook: @{body('Parse_JSON')?['action']}",
          "AppName": "@{body('Parse_JSON')?['app.name']}",
          "Timestamp": "@{body('Parse_JSON')?['timestamp']}"
        }
      }
    }
  ],
  "outputs": {}
}
```

**Avantages :**
- ✅ Déclenché par Qlik webhook
- ✅ Actions cloud natives (email, Teams, SharePoint)
- ✅ Retry intégré
- ✅ Monitoring/historique

---

### Approche 2 : Custom Connector + Polling

**Pour :** Intégrations asynchrones complexes

```json
{
  "trigger": {
    "type": "recurrence",
    "recurrence": {
      "frequency": "minute",
      "interval": 5
    }
  },
  "actions": [
    {
      "name": "Check_Qlik_Status",
      "type": "Http",
      "inputs": {
        "method": "GET",
        "uri": "https://qlik-server/api/status",
        "headers": {
          "Authorization": "Bearer @{variables('qlik_token')}"
        }
      }
    },
    {
      "name": "If_Reload_Complete",
      "type": "If",
      "expression": {
        "and": [
          {"equals": ["@outputs('Check_Qlik_Status')['status']", 200]},
          {"equals": ["@body('Check_Qlik_Status')?['state']", 'completed'"]}
        ]
      },
      "then": {
        "actions": [
          {
            "name": "Log_Completion",
            "type": "ApiConnectionAction",
            "inputs": {
              "host": {
                "connection": {"name": "@parameters('$connections')['blob']['connectionId']"}
              },
              "path": "/datasets/files",
              "method": "put",
              "body": {
                "path": "/logs/@{body('Check_Qlik_Status')?['app_id']}_@{utcNow('yyyy-MM-dd_HH-mm-ss')}.json"
              }
            }
          }
        ]
      }
    }
  ]
}
```

**Avantages :**
- ✅ Polling automatique
- ✅ Gestion d'état
- ✅ Actions conditionnelles
- ✅ Fonctionne sans Qlik webhook

---

### Approche 3 : Message Queue - Découplé

**Pour :** Volume élevé, asynchrone fiable

```json
{
  "trigger": {
    "type": "servicebus",
    "servicebus": {
      "queue": "qlik.webhooks",
      "options": {
        "cardinality": "many",
        "checkFrequency": 60
      }
    }
  },
  "actions": [
    {
      "name": "Parse_Message",
      "type": "ParseJson",
      "inputs": {
        "content": "@triggerBody()",
        "schema": {
          "type": "object",
          "properties": {
            "app_name": {"type": "string"},
            "event_type": {"type": "string"},
            "timestamp": {"type": "string"}
          }
        }
      }
    },
    {
      "name": "Route_By_Event",
      "type": "Switch",
      "expression": "@body('Parse_Message')?['event_type']",
      "cases": [
        {
          "case": "reload_success",
          "actions": [
            {
              "name": "Log_Success",
              "type": "AppendToStringVariable",
              "inputs": {
                "name": "log_messages",
                "value": "✅ @{body('Parse_Message')?['app_name']}"
              }
            }
          ]
        },
        {
          "case": "reload_failed",
          "actions": [
            {
              "name": "Alert_Team",
              "type": "ApiConnectionAction",
              "inputs": {
                "host": {
                  "connection": {"name": "@parameters('$connections')['teams']['connectionId']"}
                },
                "method": "post",
                "path": "/teams/messages",
                "body": {
                  "channel": "#alerts",
                  "text": "❌ Reload Failed: @{body('Parse_Message')?['app_name']}"
                }
              }
            }
          ]
        }
      ]
    }
  ]
}
```

**Avantages :**
- ✅ Découplé (queue)
- ✅ Scaling automatique
- ✅ Retry garanti
- ✅ Volume élevé supporté

---

## 📧 Alerts et Notifications

### Pattern 1 : Email Triggered

**Qlik :**
```qlik
SET @EmailList = 'admin@company.com,manager@company.com';

// Reload app
...

IF @ErrorCount > 0 THEN
    // Send email alert (not native in Qlik)
END IF;
```

**Power Automate :**

```json
{
  "trigger": {
    "type": "recurrence",
    "recurrence": {
      "frequency": "day",
      "interval": 1,
      "startTime": "08:00:00"
    }
  },
  "actions": [
    {
      "name": "Check_Data_Quality",
      "type": "Http",
      "inputs": {
        "method": "GET",
        "uri": "https://powerbi-server/api/datasets/@{variables('dataset_id')}/refreshes",
        "headers": {"Authorization": "Bearer @{variables('pbi_token')}"}
      }
    },
    {
      "name": "If_Last_Refresh_Failed",
      "type": "If",
      "expression": {
        "and": [
          {"equals": ["@body('Check_Data_Quality')?['value'][0]['status']", "Failed"]},
          {"greaterOrEquals": ["@subtractFromNow('PT24H')", "@body('Check_Data_Quality')?['value'][0]['startTime']"]}
        ]
      },
      "then": {
        "actions": [
          {
            "name": "Send_Alert_Email",
            "type": "SendEmail",
            "inputs": {
              "to": ["admin@company.com", "manager@company.com"],
              "subject": "⚠️ Power BI Dataset Refresh Failed",
              "body": 
"Dataset @{variables('dataset_name')} last refresh failed.\\n\\n
Time: @{body('Check_Data_Quality')?['value'][0]['endTime']}\\n
Reason: Check Power BI Service\\n\\n
Action: Review refresh logs in Power BI Service"
            }
          }
        ]
      }
    }
  ]
}
```

---

### Pattern 2 : Teams Notification

```json
{
  "action": "Post_Adaptive_Card_to_Teams",
  "type": "ApiConnectionAction",
  "inputs": {
    "host": {
      "connection": {"name": "@parameters('$connections')['teams']['connectionId']"}
    },
    "method": "post",
    "path": "/teams/messages",
    "body": {
      "channel": "#data-alerts",
      "payload": {
        "type": "message",
        "from": {
          "name": "Data Team Bot"
        },
        "body": [
          {
            "type": "TextBlock",
            "text": "🔄 Daily Dataset Refresh Status",
            "weight": "bolder",
            "size": "large"
          },
          {
            "type": "FactSet",
            "facts": [
              {
                "name": "Dataset:",
                "value": "@{variables('dataset_name')}"
              },
              {
                "name": "Status:",
                "value": "@{body('Check_Data_Quality')?['value'][0]['status']}"
              },
              {
                "name": "Duration:",
                "value": "@{body('Check_Data_Quality')?['value'][0]['duration']}"
              }
            ]
          }
        ],
        "actions": [
          {
            "type": "Action.OpenUrl",
            "title": "View in Power BI",
            "url": "https://app.powerbi.com/groups/me/datasets"
          }
        ]
      }
    }
  }
}
```

---

## 🔄 Scheduled Tasks

### Pattern : Refresh Programmé

**Qlik (QMC) :**
```
App Reload Schedule:
- Daily at 06:00 AM
- Monday-Friday
- Notify admin@company.com if fails
```

**Power Automate :**

```json
{
  "trigger": {
    "type": "recurrence",
    "recurrence": {
      "frequency": "week",
      "interval": 1,
      "daysOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "startTime": "06:00:00",
      "timeZone": "Eastern Standard Time"
    }
  },
  "actions": [
    {
      "name": "Trigger_Dataset_Refresh",
      "type": "Http",
      "inputs": {
        "method": "POST",
        "uri": "https://api.powerbi.com/v1.0/myorg/datasets/@{variables('dataset_id')}/refreshes",
        "headers": {
          "Authorization": "Bearer @{variables('pbi_token')}",
          "Content-Type": "application/json"
        }
      }
    },
    {
      "name": "Wait_For_Refresh",
      "type": "Until",
      "inputs": {
        "actions": [
          {
            "name": "Check_Refresh_Status",
            "type": "Http",
            "inputs": {
              "method": "GET",
              "uri": "https://api.powerbi.com/v1.0/myorg/datasets/@{variables('dataset_id')}/refreshes",
              "headers": {"Authorization": "Bearer @{variables('pbi_token')}"}
            }
          },
          {
            "name": "Delay",
            "type": "Wait",
            "inputs": {"interval": {"value": 30, "unit": "Second"}}
          }
        ],
        "expression": "@not(equals(body('Check_Refresh_Status')?['value'][0]['status'], 'InProgress'))",
        "limit": {
          "count": 120,
          "timeout": "PT1H"
        }
      }
    },
    {
      "name": "If_Refresh_Failed",
      "type": "If",
      "expression": {
        "equals": ["@body('Check_Refresh_Status')?['value'][0]['status']", "Failed"]
      },
      "then": {
        "actions": [
          {
            "name": "Send_Failure_Alert",
            "type": "SendEmail",
            "inputs": {
              "to": ["admin@company.com"],
              "subject": "❌ Dataset Refresh Failed - Action Required"
            }
          }
        ]
      }
    }
  ]
}
```

---

## 📊 Data Flow Integration

### Pattern : Refresh Power BI Dataflow

```json
{
  "trigger": {"type": "recurrence", "recurrence": {"frequency": "day", "interval": 1}},
  "actions": [
    {
      "name": "Refresh_Dataflow",
      "type": "Http",
      "inputs": {
        "method": "POST",
        "uri": "https://api.powerbi.com/v1.0/myorg/groups/@{variables('workspace_id')}/dataflows/@{variables('dataflow_id')}/transactionId",
        "headers": {"Authorization": "Bearer @{variables('pbi_token')}"}
      }
    }
  ]
}
```

---

## 🔐 Security & Monitoring

### ✅ Best Practices

1. **Credentials Management**
   - ✅ Utiliser Key Vault pour stocker tokens
   - ✅ Token expiration monitoring
   - ✅ Rotation automatique

2. **Error Handling**
   - ✅ Try/catch blocks
   - ✅ Retry policies exponentielles
   - ✅ Dead letter queues

3. **Audit & Logging**
   - ✅ Tous les runs loggés
   - ✅ Flow run history (30 jours)
   - ✅ Cloud logging (Azure Monitor)

### Configuration Exemple

```json
{
  "trigger": {...},
  "actions": [
    {
      "runAfter": {},
      "type": "ApiConnectionAction",
      "inputs": {...},
      "runtimeConfiguration": {
        "contentTransfer": {
          "transferMode": "Chunked"
        },
        "timeout": "PT5M"
      }
    }
  ],
  "runAfter": {},
  "outputs": {}
}
```

---

## 📚 Migration Checklist

| Élément | Qlik | Power Automate | Effort |
|---------|------|---|--------|
| **Webhook** | ✅ | ✅ HTTP Trigger | Moyen |
| **Alert Email** | ⚠️ Script | ✅ Mail Action | Faible |
| **Teams Notification** | ❌ | ✅ Native | Faible |
| **Scheduled Refresh** | ✅ QMC | ✅ Recurrence | Faible |
| **Conditional Actions** | ✅ Script | ✅ Switch/If | Moyen |
| **Data Transformation** | ✅ Load Script | ⚠️ Minimal | Moyen |
| **Error Retry** | ⚠️ Manual | ✅ Built-in | Faible |
| **Monitoring/Logging** | ⚠️ File logs | ✅ Cloud logs | Faible |

---

## 🚀 Étapes Migration

### Phase 1 : Inventorier Webhooks Qlik

1. **QMC → Webhooks**
2. **Documenter :**
   - Trigger conditions
   - Target URLs
   - Payload structure
   - Error handling

### Phase 2 : Mapper à Power Automate

1. **Pour chaque webhook :**
   - ✅ Créer cloud flow équivalent
   - ✅ Configurer HTTP trigger
   - ✅ Implémenter actions

### Phase 3 : Tester & Valider

1. **Tests unitaires :**
   - Trigger manuellement
   - Valider actions exécutées
   - Vérifier logs
2. **Tests intégration :**
   - Qlik webhook → Power Automate
   - Valider résultat end-to-end

### Phase 4 : Déployer & Monitorer

1. **Production :**
   - Activer flow
   - Désactiver ancien webhook Qlik
   - Monitorer première semaine

---

## 💡 Exemples Réefs

### Exemple 1 : Alert sur Reload Failure

**Qlik :**
```qlik
LOAD ...;

IF @ErrorCount > 0 THEN
    // Log error somewhere
END IF;
```

**Power Automate :**
```json
{
  "trigger": {
    "type": "recurrence",
    "recurrence": {"frequency": "minute", "interval": 5}
  },
  "actions": [
    {
      "name": "Get_Latest_Reload_Status",
      "type": "Http",
      "inputs": {
        "uri": "https://qlik-api/apps/@{variables('app_id')}/reloads"
      }
    },
    {
      "name": "Send_Alert_If_Failed",
      "type": "If",
      "expression": {
        "equals": ["@body('Get_Latest_Reload_Status')?['status']", "Failed"]
      },
      "then": {
        "actions": [
          {
            "name": "Send_Alert",
            "type": "SendEmail",
            "inputs": {
              "to": "admin@company.com",
              "subject": "Reload Failed"
            }
          }
        ]
      }
    }
  ]
}
```

---

### Exemple 2 : Multi-Step Orchestration

```json
{
  "trigger": {
    "type": "servicebus",
    "queue": "data.events"
  },
  "actions": [
    {
      "name": "Parse_Event",
      "type": "ParseJson",
      "inputs": {"content": "@triggerBody()"}
    },
    {
      "name": "Execute_Dataflow",
      "type": "ApiConnectionAction",
      "inputs": {
        "method": "POST",
        "uri": "https://api.powerbi.com/v1.0/myorg/groups/@{variables('ws_id')}/dataflows/@{body('Parse_Event')?['dataflow_id']}/transactionId"
      }
    },
    {
      "name": "Wait_Completion",
      "type": "Until",
      "inputs": {"count": 120, "timeout": "PT1H"}
    },
    {
      "name": "Refresh_Dataset",
      "type": "Http",
      "inputs": {
        "method": "POST",
        "path": "/datasets/@{body('Parse_Event')?['dataset_id']}/refreshes"
      }
    },
    {
      "name": "Notify_Success",
      "type": "SendEmail",
      "inputs": {"subject": "Pipeline Complete"}
    }
  ]
}
```

---

## 📞 Dépannage

### Erreur : "400 Bad Request"

**Causes :**
- ❌ Payload mal formé
- ❌ Missing required fields
- ❌ Schema mismatch

**Solutions :**
1. Valider JSON
2. Vérifier schéma HTTP Trigger
3. Utiliser Parse JSON action

### Erreur : "401 Unauthorized"

**Causes :**
- ❌ Token expiré
- ❌ Permissions insuffisantes

**Solutions :**
1. Régénérer token
2. Vérifier permissions Power BI/Power Automate
3. Utiliser Key Vault

### Erreur : "Timeout"

**Causes :**
- ❌ Action trop lente
- ❌ External service slow

**Solutions :**
1. Augmenter timeout (PT30M max)
2. Implémenter async/polling
3. Utiliser queues

---

## 📚 Ressources

- [Power Automate Documentation](https://learn.microsoft.com/power-automate/)
- [Qlik Webhooks API](https://qlik.dev/webhooks)
- [Power BI REST API](https://learn.microsoft.com/rest/api/powerbi/)
- [HTTP Trigger Schema](https://learn.microsoft.com/azure/logic-apps/logic-apps-http-endpoint)

---

**✨ Guide généré automatiquement par migrate_power_automate.py**
"""
    
    with open(guide_path, 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    return str(guide_path)


def generate_flow_templates(output_dir: Path) -> str:
    """Génère des templates Power Automate workflows."""
    template_path = output_dir / "flow_templates.json"
    
    templates = {
        "flows": [
            {
                "name": "Webhook_Alert_Flow",
                "description": "Simple webhook trigger with email alert",
                "definition": {
                    "trigger": {
                        "type": "Request",
                        "kind": "Http",
                        "inputs": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "app_name": {"type": "string"},
                                    "status": {"type": "string"},
                                    "message": {"type": "string"}
                                }
                            }
                        }
                    },
                    "actions": {
                        "Send_Alert": {
                            "type": "SendEmail",
                            "inputs": {
                                "to": "admin@company.com",
                                "subject": "Alert from @{triggerBody()['app_name']}",
                                "body": "@{triggerBody()['message']}"
                            }
                        }
                    }
                }
            },
            {
                "name": "Scheduled_Refresh_Flow",
                "description": "Daily dataset refresh with monitoring",
                "definition": {
                    "trigger": {
                        "type": "Recurrence",
                        "recurrence": {
                            "frequency": "Day",
                            "interval": 1,
                            "startTime": "06:00:00",
                            "timeZone": "Eastern Standard Time"
                        }
                    },
                    "actions": {
                        "Trigger_Refresh": {
                            "type": "Http",
                            "method": "POST",
                            "uri": "https://api.powerbi.com/v1.0/myorg/datasets/@{variables('dataset_id')}/refreshes",
                            "headers": {"Authorization": "Bearer @{variables('pbi_token')}"}
                        },
                        "Monitor_Status": {
                            "type": "Until",
                            "limit": {"count": 120, "timeout": "PT1H"}
                        }
                    }
                }
            },
            {
                "name": "Multi_Step_Pipeline",
                "description": "Dataflow → Dataset → Report refresh",
                "definition": {
                    "trigger": {"type": "Recurrence"},
                    "actions": {
                        "Step_1_Dataflow": {"type": "Http"},
                        "Wait_Step_1": {"type": "Wait"},
                        "Step_2_Dataset": {"type": "Http"},
                        "Notify": {"type": "SendEmail"}
                    }
                }
            }
        ]
    }
    
    with open(template_path, 'w', encoding='utf-8') as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)
    
    return str(template_path)


def generate_automation_inventory(output_dir: Path) -> str:
    """Génère un template d'inventaire automatisation."""
    inventory_path = output_dir / "automation_inventory_template.json"
    
    inventory = {
        "automations": [
            {
                "name": "Daily App Reload",
                "qlik_type": "scheduled_reload",
                "trigger": "recurrence",
                "frequency": "daily",
                "time": "06:00:00",
                "actions": [
                    {
                        "type": "refresh",
                        "target": "qlik_app",
                        "app_name": "Example App"
                    },
                    {
                        "type": "email",
                        "recipients": ["admin@company.com"]
                    }
                ],
                "error_handling": "email_admin",
                "power_automate_status": "planned",
                "effort_hours": 1,
                "notes": ""
            }
        ],
        "webhooks": [
            {
                "name": "App Reload Webhook",
                "qlik_trigger": "app_reload_complete",
                "target_url": "https://external-system/webhook",
                "payload_structure": {"app": "string", "status": "string"},
                "power_automate_status": "planned",
                "effort_hours": 2
            }
        ],
        "summary": {
            "total_automations": 1,
            "total_webhooks": 1,
            "migrated": 0,
            "total_effort_hours": 3
        }
    }
    
    with open(inventory_path, 'w', encoding='utf-8') as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)
    
    return str(inventory_path)


def main():
    parser = argparse.ArgumentParser(
        description="Migrer webhooks et automatisation Qlik vers Power Automate"
    )
    parser.add_argument(
        "--output-dir",
        default="output/power_automate",
        help="Répertoire de sortie"
    )
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("⚡ Génération guides Power Automate...")
    
    guide_file = generate_power_automate_guide(output_dir)
    print(f"✅ Guide: {guide_file}")
    
    template_file = generate_flow_templates(output_dir)
    print(f"✅ Flow templates: {template_file}")
    
    inventory_file = generate_automation_inventory(output_dir)
    print(f"✅ Automation inventory: {inventory_file}")
    
    print(f"\n📊 Fichiers générés:")
    print(f"  - {guide_file}")
    print(f"  - {template_file}")
    print(f"  - {inventory_file}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
