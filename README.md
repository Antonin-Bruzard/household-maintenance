# Prototype local — `household_maintenance`

Prototype **local, isolé et réversible** d’une intégration de maintenance domestique. Aucun fichier de ce workspace n’est installé dans Home Assistant, aucun import de `home_maintenance` n’est effectué, et aucune donnée réelle ou secret n’est utilisé.

## Deux surfaces, deux rôles

- **Panel** (`/panel.html`) : seule interface complète. Il crée, filtre, trie, modifie le titre et réalise les tâches.
- **Carte Lovelace** (`/household-maintenance-card.js`) : affiche seulement les tâches prioritaires, les compteurs d’échéance et un bouton vers le panel. Elle ne contient aucune mutation (`POST`/`PATCH`).

Les deux appellent le même contrat local : `GET/POST /api/household_maintenance/tasks`, `PATCH /api/household_maintenance/tasks/<id>` et `POST /api/household_maintenance/tasks/<id>/complete`.

## Exécuter localement

```bash
bash verify.sh
python3 demo.py --data .demo-data/maintenance.json --port 8765
```

Ouvrir `http://127.0.0.1:8765/panel.html`. La persistance est JSON versionnée (`version: 1`) dans le chemin `--data`; la supprimer annule entièrement la démonstration. Utiliser le chemin par défaut maintient toutes les écritures de démonstration dans ce workspace.

## Démonstration vérifiable

Les tests couvrent :

1. tâche de démonstration en retard ;
2. création, filtre, tri, modification et réalisation via HTTP local ;
3. recalcul de l’échéance et conservation de l’historique après rechargement ;
4. contrat de la carte : accès panel présent, absence de mutations ;
5. syntaxe Python et JavaScript vérifiable sans dépendance externe.

## Scaffold Home Assistant

`custom_components/household_maintenance/` contient le domaine provisoire, manifest versionné, config flow minimal et enregistrement de panel. Il est fourni comme scaffold à connecter ultérieurement dans **une sandbox Home Assistant seulement**. Il n’est ni déployé, ni déclaré prêt à être copié dans l’instance de production : l’adaptateur WebSocket/Store Home Assistant et ses tests HA restent le prochain lot.

## Retour arrière

Supprimer ce workspace ou `.demo-data/maintenance.json`. Il n’existe aucun effet hors de ce répertoire.
