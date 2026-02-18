"""
Migration des Data Alerts Qlik vers Power BI Alerts & Power Automate

Ce module génère des guides pour migrer la gestion des alertes Qlik vers Power BI.

Author: Migration Team
Date: 2026-02-13
"""

import json
from pathlib import Path
from typing import Dict, List
import argparse


def generate_alerts_migration_guide(output_dir: Path) -> str:
    """Génère un guide complet de migration des alertes."""
    guide_path = output_dir / "ALERTS_MIGRATION_GUIDE.md"
    
    guide_content = """# 📢 Guide Migration - Data Alerts Qlik vers Power BI

**Date de génération :** 13 février 2026

---

## 📋 Vue d'Ensemble

### Qlik → Power BI Alerts Mapping

| Qlik | Power BI | Type | Effort |
|------|----------|------|--------|
| **Alert Rule** | Alert Rule | Natif | Faible |
| **Email Notification** | Email Action | Natif | Faible |
| **Dashboard Alert** | Visual Alert | Natif | Faible |
| **Custom Alert Logic** | Power Automate Flow | Custom | Moyen |
| **Threshold Monitoring** | Threshold Alert | Natif | Faible |
| **User Notification** | Mobile Push / Teams | Natif | Faible |

---

## 🚨 Alertes Power BI - Types

### Type 1 : Visual Alert (Native)

**Pour :** Monitoring simple, pas de code

**Configuration :**

1. **Power BI Service → Report**
2. **Sélectionner Visual (KPI, Gauge, Card)**
3. **Trois points → Manage alerts**

**Exemple Visual Alert :**

```
Métrique: Sales Revenue
Condition: When value exceeds threshold
Threshold: $500,000
Frequency: Check hourly
Threshold Type: The maximum value
Repeat: true
```

**Code JSON équivalent :**

```json
{
  "alert": {
    "id": "alert-001",
    "name": "Revenue Threshold Alert",
    "visualName": "Total Revenue Card",
    "condition": "exceeds",
    "threshold": 500000,
    "frequency": "hourly",
    "checkType": "Maximum",
    "notifications": {
      "email": ["manager@company.com"],
      "repeat": true,
      "repeatInterval": "once_per_hour"
    },
    "enabled": true
  }
}
```

**Avantages :**
- ✅ Pas de configuration code
- ✅ UI simple et intuitive
- ✅ Monitoring temps réel (si refresh fréquent)
- ✅ Intégré Power BI

**Limitations :**
- ❌ Limité à visuals numériques
- ❌ Pas de logique complexe
- ❌ Notification récurrente seulement

---

### Type 2 : Power Automate Alert Rule

**Pour :** Logique complexe, multi-conditions

**Configuration workflow :**

```json
{
  "trigger": {
    "type": "recurrence",
    "recurrence": {
      "frequency": "minute",
      "interval": 15
    }
  },
  "actions": [
    {
      "name": "Query_Dataset",
      "type": "Http",
      "inputs": {
        "method": "POST",
        "uri": "https://api.powerbi.com/v1.0/myorg/groups/@{variables('workspace_id')}/datasets/@{variables('dataset_id')}/executeQueries",
        "headers": {"Authorization": "Bearer @{variables('pbi_token')}"},
        "body": {
          "queries": [
            {
              "query": "EVALUATE SUMMARIZECOLUMNS('Sales'[Revenue], 'Sales'[Region])"
            }
          ]
        }
      }
    },
    {
      "name": "Parse_Results",
      "type": "ParseJson",
      "inputs": {
        "content": "@body('Query_Dataset')",
        "schema": {
          "type": "object",
          "properties": {
            "results": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "tables": {
                    "type": "array"
                  }
                }
              }
            }
          }
        }
      }
    },
    {
      "name": "Apply_Business_Logic",
      "type": "Switch",
      "expression": "@length(body('Parse_Results')?['results'][0]['tables'][0]['rows'])",
      "cases": [
        {
          "case": 0,
          "actions": [
            {
              "name": "No_Data_Alert",
              "type": "SendEmail",
              "inputs": {
                "to": "admin@company.com",
                "subject": "⚠️ Alert: No sales data available",
                "body": "Check data pipeline immediately"
              }
            }
          ]
        }
      ],
      "default": {
        "actions": [
          {
            "name": "Check_Revenue_Alert",
            "type": "Http",
            "inputs": {
              "method": "POST",
              "uri": "https://logic-functions/check-thresholds",
              "body": "@body('Parse_Results')"
            }
          },
          {
            "name": "If_Alert_Triggered",
            "type": "If",
            "expression": {
              "equals": ["@body('Check_Revenue_Alert')?['alert_triggered']", true]
            },
            "then": {
              "actions": [
                {
                  "name": "Send_Alert",
                  "type": "SendEmail",
                  "inputs": {
                    "to": "@body('Check_Revenue_Alert')?['recipients']",
                    "subject": "@body('Check_Revenue_Alert')?['subject']",
                    "body": "@body('Check_Revenue_Alert')?['message']"
                  }
                }
              ]
            }
          }
        ]
      }
    }
  ]
}
```

**Avantages :**
- ✅ Logique métier complexe
- ✅ Multi-conditions
- ✅ Actions personnalisées
- ✅ Flexible

**Limitations :**
- ❌ Plus de maintenance
- ❌ Licences Power Automate
- ❌ Latence (par polling)

---

### Type 3 : Hybrid - Visual + Flow

**Pour :** Best of both worlds

**Architecture :**

```
Power BI Visual Alert
        ↓
   (Basic detection)
        ↓
Power Automate Flow
        ↓
   (Advanced actions)
        ↓
→ Email / Teams / Mobile
→ Log to database
→ Create ticket
→ Call webhook
```

**Implémentation :**

```json
{
  "trigger": {
    "type": "request",
    "schema": {
      "type": "object",
      "properties": {
        "alertRegulated": {"type": "string"},
        "alertTitle": {"type": "string"},
        "alertMetric": {"type": "string"},
        "alertValue": {"type": "number"}
      }
    }
  },
  "actions": [
    {
      "name": "Enrich_Alert_Context",
      "type": "Http",
      "inputs": {
        "method": "GET",
        "uri": "https://api.company.com/alerts/@{triggerBody()['alertMetric']}/context"
      }
    },
    {
      "name": "Log_Alert",
      "type": "ApiConnectionAction",
      "inputs": {
        "method": "POST",
        "host": {"connection": {"name": "@parameters('$connections')['cosmosdb']['connectionId']"}},
        "body": {
          "id": "@guid()",
          "timestamp": "@utcNow()",
          "metric": "@triggerBody()['alertMetric']",
          "value": "@triggerBody()['alertValue']",
          "context": "@body('Enrich_Alert_Context')"
        }
      }
    },
    {
      "name": "Notify_Channels",
      "type": "Switch",
      "expression": "@triggerBody()['alertSeverity']",
      "cases": [
        {
          "case": "Critical",
          "actions": [
            {
              "name": "Email_Alert",
              "type": "SendEmail",
              "inputs": {"to": "critical-team@company.com"}
            },
            {
              "name": "Teams_Alert",
              "type": "ApiConnectionAction",
              "inputs": {"method": "POST", "path": "/teams/messages"}
            },
            {
              "name": "SMS_Alert",
              "type": "ApiConnectionAction",
              "inputs": {"method": "POST", "path": "/sms/send"}
            }
          ]
        },
        {
          "case": "Warning",
          "actions": [
            {
              "name": "Email_Alert",
              "type": "SendEmail"
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 🔔 Alert Patterns Courants

### Pattern 1 : Threshold Alert (Statique)

**Qlik :**
```qlik
IF Sum(Sales) > 1000000 THEN
    // Trigger alert
END IF;
```

**Power BI - Visual Alert :**

```
Condition: When the value exceeds
Threshold: 1,000,000
Metric: Sum of Sales
Frequency: Daily check
Recipients: manager@company.com
```

---

### Pattern 2 : Anomaly Detection (Dynamique)

**Qlik :**
```qlik
// Détection manuelle
IF Sales > Avg(Sales) + (2 * StdDev(Sales)) THEN
    // Alert
END IF;
```

**Power Automate avec ML :**

```json
{
  "trigger": {"type": "recurrence", "frequency": "day", "interval": 1},
  "actions": [
    {
      "name": "Get_Historical_Data",
      "type": "Http",
      "inputs": {
        "method": "POST",
        "uri": "https://api.powerbi.com/timeseries/query",
        "body": {
          "measure": "Sales",
          "period": "30days"
        }
      }
    },
    {
      "name": "Call_ML_Anomaly_Detector",
      "type": "Http",
      "inputs": {
        "method": "POST",
        "uri": "https://anomaly-detector.cognitiveservices.azure.com/timeseries/last/detect",
        "headers": {
          "Ocp-Apim-Subscription-Key": "@{variables('ml_key')}"
        },
        "body": "@body('Get_Historical_Data')"
      }
    },
    {
      "name": "If_Anomaly_Detected",
      "type": "If",
      "expression": {
        "equals": ["@body('Call_ML_Anomaly_Detector')?['isAnomaly']", true]
      },
      "then": {
        "actions": [
          {
            "name": "Alert_Team",
            "type": "SendEmail",
            "inputs": {
              "subject": "🚨 Anomaly Detected: Sales",
              "body": "Anomaly score: @{body('Call_ML_Anomaly_Detector')?['anomalyScore']}"
            }
          }
        ]
      }
    }
  ]
}
```

---

### Pattern 3 : Business Rule Alert

**Exemple : Alert si SalesTarget non atteint**

```json
{
  "trigger": {"type": "recurrence", "frequency": "week", "interval": 1},
  "actions": [
    {
      "name": "Query_This_Week_Sales",
      "type": "Http",
      "inputs": {
        "method": "POST",
        "uri": "https://api.powerbi.com/datasets/query",
        "body": {
          "query": "SELECT SUM(Sales) as Sales, MAX(Target) as Target FROM SalesData WHERE DATEPART(WEEK, Date) = DATEPART(WEEK, TODAY())"
        }
      }
    },
    {
      "name": "Check_Target",
      "type": "If",
      "expression": {
        "less": [
          "@body('Query_This_Week_Sales')?['Sales']",
          "@body('Query_This_Week_Sales')?['Target']"
        ]
      },
      "then": {
        "actions": [
          {
            "name": "Alert_Sales_Manager",
            "type": "SendEmail",
            "inputs": {
              "to": "sales.manager@company.com",
              "subject": "⚠️ Weekly Sales Target At Risk",
              "body": "Current: $@{body('Query_This_Week_Sales')?['Sales']}, Target: $@{body('Query_This_Week_Sales')?['Target']}"
            }
          }
        ]
      }
    }
  ]
}
```

---

## 📧 Notification Channels

### Channel 1 : Email

**Avantages :**
- ✅ Universel
- ✅ Audit trail
- ✅ Officiel

**Configuration :**

```json
{
  "action": "Send_Email_Alert",
  "inputs": {
    "to": "recipients@company.com",
    "cc": "manager@company.com",
    "subject": "[ALERT] @{variables('alert_name')} - @{utcNow('HH:mm')}",
    "body": "📊 Alert Summary\n\nMetric: Sales\nValue: $@{variables('current_value')}\nThreshold: $@{variables('threshold')}\nStatus: ⚠️ TRIGGERED\n\nAction: Review dashboard",
    "Importance": "High"
  }
}
```

---

### Channel 2 : Teams Message

**Avantages :**
- ✅ Collaboration
- ✅ Reactions
- ✅ Context

**Configuration :**

```json
{
  "action": "Post_to_Teams",
  "inputs": {
    "text": "$(alert_message)",
    "@type": "MessageCard",
    "@context": "https://schema.org/extensions",
    "summary": "@{variables('alert_name')}",
    "themeColor": "@if(variables('severity') = 'Critical', 'FF0000', 'FFA500')",
    "sections": [
      {
        "activityImage": "https://company.com/logo.png",
        "activityTitle": "@{variables('alert_name')}",
        "activitySubtitle": "@{variables('alert_description')}",
        "facts": [
          {"name": "Metric", "value": "@{body('Query')?['metric']}"},
          {"name": "Value", "value": "@{body('Query')?['value']}"},
          {"name": "Threshold", "value": "@{variables('threshold')}"},
          {"name": "Time", "value": "@{utcNow('g')}"}
        ]
      }
    ],
    "potentialAction": [
      {
        "@type": "OpenUri",
        "name": "View Dashboard",
        "targets": [
          {
            "os": "default",
            "uri": "https://app.powerbi.com/dashboards/@{variables('dashboard_id')}"
          }
        ]
      }
    ]
  }
}
```

---

### Channel 3 : Mobile Push

**Avantages :**
- ✅ Immediate notification
- ✅ Lock screen visible
- ✅ Mobile alert

**Configuration :**

```json
{
  "action": "Send_Mobile_Notification",
  "inputs": {
    "to_device": "@{variables('device_token')}",
    "title": "⚠️ Sales Alert",
    "message": "Revenue dropped below threshold",
    "badge": "1",
    "sound": "default",
    "priority": "high",
    "data": {
      "dashboard_id": "@{variables('dashboard_id')}",
      "metric": "Sales",
      "value": "@{body('Query')?['value']}"
    }
  }
}
```

---

## 📊 Alert Management

### Dashboard Alerts

**Configuration métrique :**

```json
{
  "metrics": [
    {
      "name": "Revenue Growth YoY",
      "type": "kpi",
      "target": "+15%",
      "actual": "+12%",
      "alert": {
        "enabled": true,
        "condition": "below_target",
        "threshold": 0.15,
        "recipients": ["manager@company.com"]
      }
    }
  ]
}
```

### Metric Settings

1. **Alert Frequency :**
   - Once: Single notification
   - Repeat hourly: Repeat chaque heure
   - Repeat daily: Repeat chaque jour

2. **Threshold Type :**
   - Exceeds: Valeur > seuil
   - Below: Valeur < seuil
   - Equals: Valeur = seuil
   - Out of range: Valeur outside min-max

---

## 📋 Migration Checklist

| Élément | Qlik | Power BI | Effort |
|---------|------|----------|--------|
| **Static Threshold** | ✅ | ✅ Visual Alert | Faible |
| **Dynamic Threshold** | ⚠️ Script | ✅ Power Automate | Moyen |
| **Email Notification** | ✅ | ✅ Native | Faible |
| **Teams Integration** | ❌ | ✅ Native | Faible |
| **Complex Logic** | ✅ QScript | ✅ Flow | Moyen |
| **Anomaly Detection** | ⚠️ Manual | ✅ ML Service | Moyen |
| **User Preferences** | ⚠️ Custom | ❌ Limited | Élevé |
| **Alert History** | ⚠️ File logs | ✅ Cloud logs | Faible |

---

## 🚀 Étapes Migration

### Phase 1 : Inventory Alerts

1. **QMC → Alerts**
2. **Documenter :**
   - Alert name & description
   - Condition & threshold
   - Recipients
   - Frequency

**Template :**

```json
{
  "alert_id": "qlik.alert.001",
  "alert_name": "Revenue Threshold",
  "metric": "Sales",
  "condition": "exceeds",
  "threshold": 500000,
  "recipients": ["manager@company.com"],
  "frequency": "once",
  "enabled": true,
  "migration_status": "planned"
}
```

### Phase 2 : Assess Complexity

1. **Per alert :**
   - ✅ Simple threshold → Visual Alert (1 hour)
   - ✅ Email notification → Power Automate (2 hours)
   - ✅ Complex logic → Custom Flow (4+ hours)

### Phase 3 : Implement

1. **Create alert :**
   - Power BI Service → Report → Visual
   - New → Alert Rule
   - Name, condition, threshold, recipients
2. **Test :**
   - Trigger manually if possible
   - Verify notification received
   - Check alert log
3. **Deploy :**
   - Enable alert
   - Disable Qlik alert
   - Monitor first week

### Phase 4 : Monitor & Tune

1. **Review:**
   - Alert frequency (too many?)
   - False positives
   - Threshold accuracy
2. **Adjust:**
   - Refine thresholds
   - Update recipients
   - Change frequency if needed

---

## 💡 Best Practices

### ✅ À Faire

1. **Consolidate Recipients :**
   - Groupe email plutôt que liste individuelle
   - Gestion centralisée

2. **Version Thresholds :**
   - Document baseline values
   - Track threshold changes
   - Justify adjustments

3. **Test Regularly :**
   - Monthly test runs
   - Validate paths
   - Confirm deliverability

4. **Monitor Alert Health :**
   - Track triggered vs actioned
   - Measure response time
   - Identify false positives

### ⚠️ À Éviter

1. ❌ Too many alerts (alert fatigue)
2. ❌ Irrelevant recipients
3. ❌ Unrealistic thresholds
4. ❌ Duplicate alerts
5. ❌ No audit trail

---

## 📚 Ressources

- [Power BI Alerts Documentation](https://learn.microsoft.com/power-bi/create-reports/service-set-data-alerts)
- [Power Automate Flows](https://learn.microsoft.com/power-automate/)
- [Qlik Alerts Reference](https://help.qlik.com/en-US/qlikview/14.0/Content/Monitoring/Alerts.htm)
- [Azure Anomaly Detector](https://learn.microsoft.com/azure/cognitive-services/anomaly-detector/)

---

**✨ Guide généré automatiquement par migrate_data_alerts.py**
"""
    
    with open(guide_path, 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    return str(guide_path)


def generate_alert_templates(output_dir: Path) -> str:
    """Génère des templates d'alertes."""
    template_path = output_dir / "alert_templates.json"
    
    templates = {
        "visual_alerts": [
            {
                "name": "Revenue Threshold Alert",
                "metric_type": "Card",
                "condition": "exceeds",
                "threshold": 500000,
                "frequency": "hourly",
                "notifications": {
                    "type": "email",
                    "recipients": ["manager@company.com"],
                    "repeat": True
                }
            },
            {
                "name": "Sales Target Alert",
                "metric_type": "Gauge",
                "condition": "below",
                "threshold": 0.8,
                "frequency": "daily",
                "notifications": {
                    "type": "email",
                    "recipients": ["sales.team@company.com"],
                    "repeat": False
                }
            }
        ],
        "flow_alerts": [
            {
                "name": "Anomaly Detection Flow",
                "trigger": "recurrence",
                "frequency": "daily",
                "actions": [
                    "query_dataset",
                    "detect_anomalies",
                    "send_alert_if_detected"
                ]
            },
            {
                "name": "Multi-Condition Alert",
                "trigger": "recurrence",
                "conditions": [
                    {"metric": "Sales", "operator": "below", "value": 100000},
                    {"metric": "Margin", "operator": "below", "value": 0.2}
                ],
                "actions": [
                    "send_email",
                    "post_teams",
                    "log_event"
                ]
            }
        ]
    }
    
    with open(template_path, 'w', encoding='utf-8') as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)
    
    return str(template_path)


def generate_alert_inventory(output_dir: Path) -> str:
    """Génère un template d'inventaire alertes."""
    inventory_path = output_dir / "alerts_inventory_template.json"
    
    inventory = {
        "alerts": [
            {
                "alert_id": "alert_001",
                "name": "High Revenue Alert",
                "metric": "Total Sales Revenue",
                "type": "threshold",
                "condition": "exceeds",
                "threshold": 500000,
                "frequency": "hourly",
                "recipients": ["manager@company.com"],
                "power_bi_equivalent": "Visual Alert",
                "migration_status": "planned",
                "effort_hours": 0.5,
                "complexity": "simple"
            },
            {
                "alert_id": "alert_002",
                "name": "Sales Target Miss",
                "metric": "Sales vs Target",
                "type": "threshold",
                "condition": "below",
                "threshold": 0.95,
                "frequency": "weekly",
                "recipients": ["sales.team@company.com"],
                "power_bi_equivalent": "Power Automate Flow",
                "migration_status": "planned",
                "effort_hours": 2,
                "complexity": "medium"
            }
        ],
        "summary": {
            "total_alerts": 2,
            "visual_alerts": 1,
            "flow_alerts": 1,
            "migrated": 0,
            "total_effort_hours": 2.5
        }
    }
    
    with open(inventory_path, 'w', encoding='utf-8') as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)
    
    return str(inventory_path)


def main():
    parser = argparse.ArgumentParser(
        description="Migrer Data Alerts Qlik vers Power BI"
    )
    parser.add_argument(
        "--output-dir",
        default="output/data_alerts",
        help="Répertoire de sortie"
    )
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("📢 Génération guides Data Alerts...")
    
    guide_file = generate_alerts_migration_guide(output_dir)
    print(f"✅ Guide: {guide_file}")
    
    template_file = generate_alert_templates(output_dir)
    print(f"✅ Alert templates: {template_file}")
    
    inventory_file = generate_alert_inventory(output_dir)
    print(f"✅ Alerts inventory: {inventory_file}")
    
    print(f"\n📊 Fichiers générés:")
    print(f"  - {guide_file}")
    print(f"  - {template_file}")
    print(f"  - {inventory_file}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
