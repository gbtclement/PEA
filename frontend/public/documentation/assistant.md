# Assistant IA

Code : `backend/app/services/assistant/`, routes dans `backend/app/api/routes/assistant.py`, interface dans `frontend/src/features/assistant/`.

## Déroulement d'une réponse

```text
Navigateur ──POST /api/assistant/conversations/{id}/messages──► api
                                                                │
              ◄──────────── flux SSE (texte mot par mot, outils) ┤
                                                                ▼
                                          boucle : Claude ⇄ outils (données de l'app)
                                                                │
                                          réponse et coût enregistrés en base
```

1. Le message de l'utilisateur est enregistré, puis `chat.py` appelle Claude (SDK `anthropic`) en streaming, avec l'historique, la consigne système (`prompt.py`) et les outils. La consigne système reçoit les enveloppes choisies par l'utilisateur : sans choix (ou avec le compte-titres), l'assistant ne suppose pas qu'il investit via un PEA ; sinon il sait que le top 10 qu'il reçoit est déjà filtré sur ces enveloppes.
2. Quand Claude demande un outil, l'API l'exécute sur **ses propres données** (`tools.py`) et renvoie le résultat. Ce tour se répète au maximum `ASSISTANT_MAX_ROUNDS` fois (8).
3. Le texte est relayé au navigateur en **Server-Sent Events** (`streaming.py`).
4. La réponse tourne dans un **fil séparé, avec sa propre session de base**. Elle est enregistrée même si le navigateur se déconnecte, et l'appel à Claude est alors interrompu pour ne pas payer une réponse que personne ne lit.

## Outils

| Outil | Rôle |
|---|---|
| `search_securities` | Recherche par nom, ticker ou ISIN |
| `get_security_overview` | Cours, score détaillé, fondamentaux, enveloppes |
| `get_price_history` | Clôtures et indicateurs sur une période (1M, 6M, 1Y, 5Y, 10Y ou MAX) |
| `get_top10` | Top 10 actuel |
| `get_portfolio` | Positions, performance, compteur d'ordres |
| `simulate_past_investment` | Gain d'un achat passé, frais inclus |
| `web_search` | Outil serveur Anthropic, 3 recherches maximum par réponse |

## Modèles

Catalogue dans `catalog.py`, avec les prix servant à estimer le coût :

| Identifiant | Libellé | Entrée / sortie ($ par million de tokens) |
|---|---|---|
| `claude-opus-5` | Opus 5 (recommandé, par défaut) | 5 / 25 |
| `claude-sonnet-5` | Sonnet 5 (plus rapide) | 3 / 15 |
| `claude-haiku-4-5` | Haiku 4.5 (économique) | 1 / 5 |
| `claude-fable-5-1` | Fable 5.1 (le plus puissant) | 10 / 50 |

- La réflexion adaptative (`thinking: {type: "adaptive"}`) est activée sauf pour Haiku 4.5.
- Le **repli côté serveur** en cas de refus n'est activé que pour Opus 5. Chaque tentative est alors comptée dans le coût.
- Coût estimé = tokens d'entrée, de sortie et de cache + 0,01 $ par recherche web. Il est enregistré par message, même quand un tour échoue.

## Clé API, Premium et limite

- La clé est lue **uniquement** dans `ANTHROPIC_API_KEY` (`.env`). Elle n'est ni en base, ni renvoyée au navigateur, ni écrite dans les journaux. L'onglet Admin indique seulement si elle est renseignée.
- Les routes de l'assistant sont réservées aux membres Premium et aux admins (`require_premium()`). Premium s'obtient par abonnement ou est offert par un admin : voir [Abonnement (Stripe)](abonnement.md).
- Le modèle et la limite mensuelle par utilisateur viennent de `app_settings` (onglet Admin). La migration a repris le modèle choisi avant les comptes (sinon `claude-opus-5`) ; `ASSISTANT_MODEL` ne sert que si cette ligne manque.
- Chaque réponse ajoute son coût dans `ai_usage` par `add_cost()`. La limite est vérifiée avant la question (`429 ai_limit_reached`). Détails dans [Comptes utilisateurs](comptes.md#assistant--premium-et-limite-de-coût).

## Erreurs

`friendly_error()` transforme les erreurs de l'API Anthropic (clé invalide, quota, surcharge, réseau) en messages français lisibles. Une réponse interrompue reste affichée avec la mention « réponse interrompue ».

## Réseau

nginx a `proxy_buffering off` pour que le texte arrive mot par mot, et `proxy_read_timeout 600s` parce que la réflexion de Claude peut rester silencieuse plus de 60 secondes.

## Tests

`tests/fake_llm.py` simule Claude. **Aucun test n'appelle Anthropic.**
