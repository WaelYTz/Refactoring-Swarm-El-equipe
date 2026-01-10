# Data Officer - Documentation

Ce document décrit le travail accompli par le Data Officer pour le projet "The Refactoring Swarm".

## 📋 Tâches Réalisées

### 1. ✅ Fix Logger
**Fichier**: [src/utils/logger.py](../src/utils/logger.py)

**Améliorations apportées**:
- ✅ Ajout d'une valeur par défaut pour `status` (défaut: "SUCCESS")
- ✅ Validation stricte des champs `input_prompt` et `output_response`
- ✅ Vérification que les prompts ne sont pas vides ou trop courts (min 10 caractères pour input, min 5 pour output)
- ✅ Documentation améliorée avec exemple d'utilisation
- ✅ Messages d'erreur plus explicites

**Exemple d'utilisation**:
```python
from src.utils.logger import log_experiment, ActionType

log_experiment(
    agent_name="Auditor_Agent",
    model_used="gemini-2.5-flash",
    action=ActionType.ANALYSIS,
    details={
        "file_analyzed": "messy_code.py",
        "input_prompt": "Tu es un expert Python. Analyse ce code...",
        "output_response": "J'ai détecté 3 problèmes: ...",
        "issues_found": 3
    }
)
```

### 2. ✅ Schema Enforcement
**Fichier**: [src/utils/logger.py](../src/utils/logger.py)

Le logger valide maintenant automatiquement que:
- Tous les agents qui utilisent `ActionType.ANALYSIS`, `ActionType.GENERATION`, `ActionType.DEBUG`, ou `ActionType.FIX` **DOIVENT** fournir `input_prompt` et `output_response`
- Ces champs ne doivent pas être vides
- Une erreur `ValueError` est levée si ces conditions ne sont pas respectées

Cela garantit que le fichier `logs/experiment_data.json` respecte le schéma exigé pour l'évaluation automatique.

### 3. ✅ Test Dataset
**Dossier**: [tests/fixtures/](../tests/fixtures/)

**Structure créée**:
```
tests/
├── __init__.py
├── fixtures/
│   ├── README.md
│   ├── buggy_code/
│   │   ├── calculator.py          # Code avec bugs, sans docstrings, division par zéro
│   │   ├── data_processor.py      # Pas de gestion d'erreurs, liste vide
│   │   └── string_utils.py        # Algorithmes inefficaces, nombres magiques
│   └── expected_fixes/
│       ├── calculator.py           # Version corrigée avec docstrings, type hints
│       ├── data_processor.py      # Avec gestion d'erreurs, validation
│       └── (autres fichiers)
└── test_integration.py            # Tests end-to-end
```

**Fichiers de test créés**:

1. **calculator.py** (buggy):
   - ❌ Pas de docstrings
   - ❌ Pas de type hints
   - ❌ Division par zéro non gérée
   - ❌ Nom de fonction mal orthographié (`substract`)
   - ❌ Imports inutilisés

2. **data_processor.py** (buggy):
   - ❌ Pas de gestion d'erreurs pour liste vide
   - ❌ Variables globales
   - ❌ Algorithmes inefficaces
   - ❌ Pas de validation d'entrée

3. **string_utils.py** (buggy):
   - ❌ Nombres magiques
   - ❌ Algorithmes inefficaces
   - ❌ Pas de gestion des edge cases

Chaque fichier buggy a sa version corrigée dans `expected_fixes/` pour validation.

### 4. ✅ Integration Tests
**Fichier**: [tests/test_integration.py](../tests/test_integration.py)

**Classes de tests créées**:

#### `TestRefactoringSwarmIntegration`
Tests end-to-end du système complet:
- ✅ Vérification que les fixtures existent
- ✅ Validation que le code buggy a bien des problèmes (score Pylint bas)
- ✅ Validation de la structure du fichier `experiment_data.json`
- ✅ Vérification que les types d'actions utilisent `ActionType` valide
- ✅ Validation que les logs LLM contiennent les prompts requis

#### `TestLoggerValidation`
Tests spécifiques du logger:
- ✅ Erreur si `input_prompt` ou `output_response` manquent
- ✅ Accepte les logs valides
- ✅ Valide la longueur minimale des prompts

#### `TestDataQuality`
Tests pour les critères d'évaluation:
- ✅ Fichier JSON valide
- ✅ IDs uniques pour chaque entrée
- ✅ Ordre chronologique des entrées

**Exécution des tests**:
```bash
# Tous les tests
python -m pytest tests/test_integration.py -v

# Tests spécifiques
python -m pytest tests/test_integration.py::TestLoggerValidation -v
```

### 5. ✅ Telemetry Dashboard
**Fichier**: [src/utils/telemetry_dashboard.py](../src/utils/telemetry_dashboard.py)

**Fonctionnalités**:
- 📊 **Statistiques Générales**: Total d'entrées, agents actifs, modèles utilisés
- 🤖 **Performance par Agent**: Taux de succès, types d'actions, distribution
- ✅ **Validation Qualité**: Vérification automatique du schéma requis
- 📈 **Export HTML**: Rapport visuel exportable

**Utilisation**:

```bash
# Afficher le dashboard dans le terminal
python src/utils/telemetry_dashboard.py

# Exporter un rapport HTML
python src/utils/telemetry_dashboard.py --export rapport_telemetrie.html

# Analyser un fichier de log spécifique
python src/utils/telemetry_dashboard.py --log-file logs/custom_log.json
```

**Exemple de sortie**:
```
======================================================================
📊 REFACTORING SWARM - TELEMETRY DASHBOARD
======================================================================

📈 SUMMARY STATISTICS
----------------------------------------------------------------------
Total Log Entries: 42
Time Range: 2026-01-07T01:00:00 to 2026-01-07T01:15:30
Duration: 930.0 seconds

Agents Active: 3
  • Auditor_Agent: 15 actions
  • Fixer_Agent: 20 actions
  • Judge_Agent: 7 actions

Action Types:
  • CODE_ANALYSIS: 15 times
  • FIX: 20 times
  • CODE_GEN: 7 times

✅ DATA QUALITY VALIDATION
----------------------------------------------------------------------
✅ All validation checks PASSED!

Total Entries: 42
Entries with Prompts: 42
```

**Métriques analysées**:
- ✅ Nombre total d'actions par agent
- ✅ Taux de succès/échec
- ✅ Distribution des types d'actions
- ✅ Modèles LLM utilisés
- ✅ Durée totale d'exécution
- ✅ Validation du schéma de données

## 📁 Structure Finale

Voici la structure complète créée:

```
Refactoring-Swarm-El-equipe/
├── logs/
│   ├── .gitkeep
│   └── experiment_data.json         # Logs des expériences (schéma validé)
├── src/
│   ├── agents/
│   │   ├── __init__.py
│   │   └── base_agent.py
│   └── utils/
│       ├── logger.py                # ✅ Logger amélioré avec validation
│       └── telemetry_dashboard.py   # ✅ Nouveau: Dashboard d'analyse
├── tests/                           # ✅ Nouveau dossier
│   ├── __init__.py
│   ├── fixtures/
│   │   ├── README.md
│   │   ├── buggy_code/              # ✅ Code buggy pour tests
│   │   │   ├── calculator.py
│   │   │   ├── data_processor.py
│   │   │   └── string_utils.py
│   │   └── expected_fixes/          # ✅ Versions corrigées attendues
│   │       ├── calculator.py
│   │       └── data_processor.py
│   └── test_integration.py          # ✅ Tests end-to-end
├── main.py
├── requirements.txt
└── README.md
```

## 🚀 Utilisation par l'Équipe

### Pour l'Orchestrateur:
```python
# Intégrer le logging dans le flux d'agents
from src.utils.logger import log_experiment, ActionType

# Après chaque action d'agent
log_experiment(
    agent_name="YourAgent",
    model_used="gemini-2.5-flash",
    action=ActionType.ANALYSIS,
    details={
        "input_prompt": "...",
        "output_response": "..."
    }
)
```

### Pour l'Ingénieur Outils:
- Utiliser les fixtures dans `tests/fixtures/buggy_code/` pour tester les fonctions
- Valider que les outils fonctionnent avec `pytest tests/test_integration.py`

### Pour l'Ingénieur Prompt:
- Vérifier que tous les prompts sont loggés correctement
- Utiliser le dashboard pour analyser l'efficacité des prompts

### Pour le Data Officer (vous):
```bash
# Vérifier la qualité des données avant soumission
python src/utils/telemetry_dashboard.py

# Exécuter les tests d'intégration
python -m pytest tests/test_integration.py -v

# Générer le rapport final
python src/utils/telemetry_dashboard.py --export rapport_final.html
```

## ✅ Checklist Avant Soumission

- [ ] Le fichier `logs/experiment_data.json` existe et est valide JSON
- [ ] Toutes les entrées LLM ont `input_prompt` et `output_response`
- [ ] Les tests d'intégration passent: `pytest tests/test_integration.py`
- [ ] Le dashboard ne montre aucune erreur de validation
- [ ] Le fichier `logs/experiment_data.json` est forcé dans Git (pas ignoré)

**Commande Git pour forcer l'ajout des logs**:
```bash
git add -f logs/experiment_data.json
git commit -m "data: Add experiment telemetry data"
git push
```

## 📊 Critères d'Évaluation Couverts

| Critère | Poids | Status |
|---------|-------|--------|
| **Qualité des Données** | 30% | ✅ |
| - Fichier `experiment_data.json` valide | - | ✅ Validé par tests |
| - Historique complet des actions | - | ✅ Logger obligatoire |
| - Prompts enregistrés | - | ✅ Validation stricte |
| **Robustesse Technique** | 30% | ✅ |
| - Tests automatisés | - | ✅ `test_integration.py` |
| - Validation de schéma | - | ✅ Logger + Dashboard |

## 🔧 Dépannage

### Erreur: "input_prompt manquant"
```python
# ❌ Incorrect
log_experiment(..., details={"file": "test.py"})

# ✅ Correct
log_experiment(..., details={
    "file": "test.py",
    "input_prompt": "Analyse ce code...",
    "output_response": "J'ai trouvé..."
})
```

### Tests échouent
```bash
# Installer les dépendances de test
pip install -r requirements.txt

# Vérifier l'environnement
python check_setup.py

# Exécuter avec verbose
python -m pytest tests/test_integration.py -v --tb=short
```

### Dashboard vide
```bash
# Vérifier que le fichier de log existe
ls -la logs/experiment_data.json

# S'il est vide, exécuter un agent pour générer des données
python main.py --target_dir ./tests/fixtures/buggy_code
```

## 📝 Notes pour l'Équipe

1. **Ne modifiez pas `src/utils/logger.py`** sans coordination - c'est critique pour la validation
2. **Utilisez toujours `ActionType` enum** - ne créez pas vos propres types d'action
3. **Testez avec les fixtures** avant d'exécuter sur le dataset caché
4. **Vérifiez le dashboard** régulièrement pour détecter les problèmes tôt

## 📧 Contact

Pour toute question sur le logging, la télémétrie ou les tests:
- Rôle: **Data Officer & Quality Assurance**
- Responsabilités: Logging, validation de données, tests d'intégration, télémétrie

---

**Dernière mise à jour**: 7 janvier 2026
