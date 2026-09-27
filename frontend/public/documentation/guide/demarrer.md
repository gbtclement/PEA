# Démarrer

## Ce qu'il faut installer

- **Docker Desktop** : il fait tourner la base de données, l'API, le worker et le site. Il doit être **démarré** avant de lancer l'application.
- **Git**, pour récupérer le code.
- **Node.js 22** seulement si vous voulez modifier l'interface (voir [Développement et tests](technique/developpement.md)).

## Premier lancement

```bash
git clone https://github.com/gbtclement/PEA.git
cd PEA
cp .env.example .env
```

Ouvrez `.env` et remplacez `APP_SECRET=change-me` par une longue chaîne aléatoire. Par exemple, avec Node :

```bash
node -e "console.log(require('crypto').randomBytes(48).toString('base64url'))"
```

?> `APP_SECRET` chiffre votre clé API Claude dans la base. **Ne la changez plus ensuite** : la clé déjà enregistrée deviendrait illisible et il faudrait la ressaisir.

Lancez ensuite tout :

```bash
docker compose up -d --build
```

Puis ouvrez **http://localhost:8095**.

## Ce qui se passe au premier démarrage

Le **worker** remplit la base tout seul, dans cet ordre :

| Étape | Durée approximative |
|---|---|
| Liste des titres (Euronext, grands indices, ETF) | moins d'une minute |
| 5 ans d'historique de cours pour tous les titres | une dizaine de minutes |
| Premiers scores et premières prévisions | une à deux minutes |
| Données fondamentales (PER, dividende, dette…) | environ une heure |

Pendant ce temps, l'application fonctionne mais certaines pages sont vides ou partielles. En bas de la barre latérale, l'état du marché indique l'heure de la dernière mise à jour.

?> Des messages `possibly delisted` dans les journaux du worker sont normaux : ce sont des titres radiés de la cote que Yahoo ne connaît plus.

## Les jours suivants

- Allumez Docker Desktop : les conteneurs redémarrent automatiquement (`restart: unless-stopped`).
- Si le PC était éteint à 7 h, le worker **rattrape** au démarrage ce qui a pris du retard (liste des titres, historique, prévisions, fondamentaux).
- Pendant la séance (9 h – 17 h 35, jours ouvrés), les cours sont rafraîchis toutes les 2 à 30 minutes selon les titres.

## Commandes utiles

```bash
docker compose ps                  # état des conteneurs
docker compose logs -f worker      # suivre le travail du worker
docker compose stop                # tout arrêter (les données sont conservées)
docker compose up -d --build       # relancer après une mise à jour du code
```

!> `docker compose down -v` **efface la base de données** (volume `pgdata`) : ordres, favoris, conversations et réglages compris. Ne l'utilisez que pour repartir de zéro.
