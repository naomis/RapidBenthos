# RapidBenthos

RapidBenthos est un pipeline de traitement automatisé pour la segmentation et la classification multi-vues des communautés de récifs coralliens à partir de reconstructions photogrammétriques. Le projet combine des approches de vision par ordinateur, de géomatique et de classification supervisée pour transformer une orthomosaïque, des images aériennes et un projet Metashape en segments géographiques analysables, étiquetés et quantifiés.

Ce dépôt contient les scripts principaux, les fonctions utilitaires, les fichiers de configuration et les ressources nécessaires à l'exécution du workflow complet.

## Objectif du projet

L'objectif est de :

- segmenter automatiquement les objets visibles sur une orthomosaïque de récif corallien;
- générer des polygones et des points géoréférencés représentant les segments détectés;
- relier ces segments à des images de terrain via Metashape;
- classifier les segments ou points selon des catégories écologiques et morphologiques;
- produire des indicateurs de composition communautaire et de pourcentage de couverture.

## Workflow général

Le pipeline suit généralement ce déroulé :

1. Acquisition et préparation des données
   - orthomosaïque raster;
   - projet Metashape;
   - photos de terrain;
   - modèle SAM (Segment Anything Model) et checkpoint associé.

2. Segmentation automatique avec SAM
   - exécution de plusieurs passes de segmentation avec des paramètres adaptés aux petits et grands objets;
   - fusion des masques générés;
   - vectorisation en géométries vectorielles.

3. Traitement géospatial
   - filtrage des segments;
   - génération d'une grille hexagonale;
   - extraction de points et de centroides associés.

4. Liaison avec Metashape
   - projection des centroides dans l'espace de la reconstruction 3D;
   - extraction des coordonnées UV/caméras associées.

5. Classification et analyse
   - classification des points ou segments à partir de sorties ReefCloud ou d'étiquettes fournies;
   - calcul de pourcentage de couverture;
   - génération de graphiques de composition communautaire.

## Structure du dépôt

```text
.
├── ReadMe.md
├── config.yaml
├── docker-compose.yml
├── Dockerfile
├── entrypoint.sh
├── environment.yml
├── pyproject.toml
├── uv.lock
├── label_set_M7_compatible.csv
└── Scripts/
```

## Rôle de chaque fichier

### Fichiers racine

- ReadMe.md : documentation principale du projet. Ce fichier décrit le contexte scientifique, l'architecture du dépôt, les dépendances, le workflow et les usages principaux.
- config.yaml : configuration principale du pipeline, notamment le site, le chemin vers l'orthomosaïque, le projet Metashape, le dossier de sortie et le checkpoint SAM.
- docker-compose.yml : définition des services Docker pour exécuter le pipeline, vérifier l'environnement GPU et lancer les scripts dans un conteneur.
- Dockerfile : image de conteneur basée sur CUDA 12.8, avec Python 3.10, GDAL, GeoPandas, PyTorch (CUDA 12.8), SAM, Metashape et les dépendances géospatiales nécessaires.
- entrypoint.sh : script de démarrage utilisé par le conteneur pour activer la licence Metashape, lancer le programme principal et garantir sa désactivation propre à la fin.
- environment.yml : environnement Conda unifié (Linux/Windows/macOS) pour l'exécution locale.
- pyproject.toml : définition canonique des dépendances Python (gérées par uv).
- uv.lock : lockfile reproductible généré par uv.
- label_set_M7_compatible.csv : fichier d'étiquettes utilisé pour la classification des segments selon le protocole de terrain et les catégories du site M7.

### Dossier Scripts

- Scripts/RapidBenthos_part1.py : script principal de la partie 1 du pipeline. Il orchestre la segmentation SAM, la fusion des masques, la vectorisation, le filtrage, la génération de la grille hexagonale et éventuellement la liaison avec Metashape.
- Scripts/RapidBenthos_part1_Clean.py : version plus "propre" ou alternative du pipeline de la partie 1, adaptée à un usage Windows et avec des correctifs spécifiques pour certains composants SAM/torch.
- Scripts/RapidBenthos_part1_00_tuiles.py : script de traitement par tuiles, utilisé pour traiter une orthomosaïque découpée en plusieurs tuiles de manière organisée et progressive.
- Scripts/RapidBenthos_part1_01_metashape.py : script dédié à l'intégration avec Metashape, pour l'importation de données, la lecture d'un projet et l'extraction de données géométriques ou photogrammétriques.
- Scripts/Rapid_benthos_part3.py : script de la partie 3 du pipeline. Il combine les sorties de la partie 1 avec les résultats de classification (par exemple ReefCloud), puis produit les fichiers de pourcentage de couverture, les graphiques de composition et les segments au niveau des colonies.
- Scripts/RB_fcn_part1.py : bibliothèque de fonctions de la partie 1. Elle contient les opérations de filtrage des segments, la génération de la grille hexagonale, la transformation de coordonnées, la gestion des fichiers géospatiaux et la logique de liaison aux caméras Metashape.
- Scripts/RB_fcn_part3.py : bibliothèque de fonctions de la partie 3. Elle gère la sélection des points classés, la mise en forme des pourcentages de couverture, la génération du graphique empilé et la création des segments au niveau des colonies.
- Scripts/metashape.py : utilitaire ou script de support lié à l'interaction avec l'API Metashape.
- Scripts/test_environment.py : script de vérification de l'environnement Python, GPU, dépendances géospatiales et accès à Metashape.
- Scripts/tests.py : script de validation ou de tests de logique de classification/traitement.

## Prérequis

Le pipeline dépend de plusieurs composants :

- Python 3.10 (recommandé dans le Dockerfile);
- CUDA 12.8+ et un GPU compatible pour le modèle SAM;
- GDAL/PROJ pour les opérations géospatiales;
- GeoPandas, Rasterio, Shapely, Fiona;
- PyTorch, OpenCV, Pillow, pandas, NumPy, scikit-learn;
- Metashape (si la liaison 3D/caméra est utilisée);
- un checkpoint SAM tel que `sam_vit_h_4b8939.pth` ou un modèle équivalent.

## Installation

### Option 1 — installation locale avec Conda + uv

```bash
conda env create -f environment.yml
conda activate rapidbenthos
uv sync --extra gpu
```

### Option 2 — conteneur Docker

Le projet est prêt pour une exécution dans Docker avec GPU (CUDA 12.8) :

```bash
docker compose up --build
```

Le fichier docker-compose configure les montages de données, les dossiers de sortie et l'environnement de travail.

## Configuration

Le fichier config.yaml contient les entrées principales du pipeline.

Exemple de structure :

```yaml
site:
  plot_id: "M7"
  ortho: "/app/data/M7 tuiles.3.tif"
  out_folder: "/app/outputs"

metashape:
  project_path: "/app/data/M7_0326.psx"
  chunk_number: 0
  photo_path: "/app/photos"

sam:
  checkpoint: "/app/checkpoints/sam_vit_h_4b8939.pth"
  model_type: "vit_h"
```

Il est important de vérifier :

- le chemin vers l'orthomosaïque;
- le chemin du projet Metashape;
- le dossier contenant les photos associées;
- le chemin du checkpoint SAM;
- le dossier de sortie pour les fichiers intermédiaires et finaux.

## Utilisation rapide

### Partie 1 — segmentation et préparation des segments

La partie 1 est lancée via :

```bash
python Scripts/RapidBenthos_part1.py
```

Cette étape produit généralement :

- un ou plusieurs masques raster (`_mask1.tif`, `_mask2.tif`);
- un masque fusionné (`_combined.tif`);
- un fichier vectoriel de segments (`_combined.gpkg`);
- des shapefiles et csv de points et de segments filtrés;
- une grille hexagonale et ses sorties associées.

### Partie 3 — classification et analyse communautaire

La partie 3 s'exécute avec :

```bash
python Scripts/Rapid_benthos_part3.py
```

Elle attend principalement :

- un fichier CSV contenant les centroides ou points issus de la partie 1;
- un CSV issu de l'annotation ReefCloud;
- un fichier de labels compatible;
- un shapefile de polygones segmentés.

Elle génère ensuite :

- un fichier de segments étiquetés;
- un fichier de pourcentage de couverture;
- un graphique de composition communautaire;
- un shapefile de segments au niveau des colonies.

## Fichiers de sortie attendus

Selon la configuration, le pipeline peut produire :

- fichiers raster de masques SAM;
- fichiers GeoPackage ou shapefiles de segments;
- CSV de points et centroides;
- CSV de pourcentage de couverture;
- graphiques de composition communautaire;
- fichiers liés à Metashape pour l'association caméra/point.

## Notes importantes

- Certains scripts contiennent encore des chemins locaux Windows et peuvent nécessiter une adaptation selon votre machine ou votre infrastructure.
- La version la plus robuste pour un usage standard est le script principal de la partie 1 avec la configuration centralisée dans `config.yaml`.
- Les scripts de la partie 3 sont davantage orientés vers l'analyse post-traitement et la génération de rapports.
- Le conteneur Docker est recommandé pour un environnement reproductible, surtout lorsque l'on travaille avec GPU et Metashape.

## Références et citation

Le dépôt est associé à l'article scientifique suivant :

Remmers, T., Boutros, N., Wyatt, M., Gordon, S., Toor, T., Roelfsema, C., Fabricius, K., Grech, A., Lechene, L., Ferrari, R. 2024. RapidBenthos – Automated segmentation and multi-view classification of coral reef communities from photogrammetric reconstruction.

Si ce travail vous est utile dans vos recherches, merci de citer l'article correspondant.

## Remerciements

Cette recherche a bénéficié du soutien du Reef Restoration and Adaptation Program, du partenariat entre le gouvernement australien, le Great Barrier Reef Foundation, l'Université James Cook et l'Université du Queensland. Les auteurs reconnaissent également les peuples autochtones et leurs liens culturels et écologiques avec les zones étudiées.