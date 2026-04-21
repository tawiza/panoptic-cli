# panoptic

*un regard sur l'agrivoltaïsme français.*

416 projets. 133 contestations. 4 registres publics croisés.
Une commande sur ton PC, hors-ligne.

```
$ panoptic 47
  3AYNE · éveillé · data fraîche
  10 projets · 5 contestations · 454 MWc cumulés
  ● silence suspect · GLHD [score 80]
  ↗ projet latent · CONCESSION PLATIN DE GRAVE [score 65]
```

---

## Installation : 3 choix, du plus simple au plus solide

Python 3.10+ requis. **Important** : n'installe jamais dans ton Python
système. Toujours dans un environnement isolé. Trois façons :

### 1. pipx (recommandé)

pipx installe une CLI Python dans un environnement dédié, invisible pour le
reste de ton système. Zéro conflit avec les autres paquets Python.

```bash
# installe pipx si pas déjà là
sudo apt install pipx        # Debian, Ubuntu
brew install pipx            # macOS
pipx ensurepath

# installe panoptic directement depuis le repo
pipx install panoptic-tawiza
```

La base de données SQLite est embarquée dans le paquet (372 KB décompressés,
124 KB en wheel). Tu peux lancer `panoptic 47` hors-ligne immédiatement.

Mise à jour plus tard : `pipx upgrade panoptic-tawiza` ou
`pipx reinstall panoptic-tawiza`.

### 2. venv à la main

Si tu préfères tout gérer toi-même :

```bash
python -m venv ~/.panoptic-venv
~/.panoptic-venv/bin/pip install panoptic-tawiza
~/.panoptic-venv/bin/panoptic 47
```

Tu peux ajouter un alias `alias panoptic='~/.panoptic-venv/bin/panoptic'`
dans ton shell pour raccourcir.

### 3. Depuis le repo GitHub (pour les versions dev, fork)

```bash
pipx install git+https://github.com/tawiza/panoptic-cli
```

Utile si tu veux tester une PR non publiée ou ta propre branche.

### 4. Bientôt : Docker

*En v0.2.* Pour ceux qui préfèrent zéro installation Python locale.

---

## À ne jamais faire

Ces commandes installent panoptic dans le Python système partagé et peuvent
casser d'autres outils. **Ne pas faire :**

- `sudo pip install ...`
- `pip install ...` sans venv actif

Utilise pipx ou venv (plus haut).

---

## Usage

```bash
panoptic 47                     # département (Lot-et-Garonne)
panoptic 47001                  # code INSEE commune
panoptic 47250                  # code postal
panoptic "Pujo-le-Plan"         # nom commune (fuzzy)

panoptic 47 --html rapport.html # export autonome partageable
panoptic update                 # sync depuis panoptic.tawiza.fr/data/
panoptic freshness              # état des sources
panoptic --help                 # aide complète
```

## Ce que panoptic détecte automatiquement

Cinq règles de détection simples, environ 200 lignes de Python, lisibles
ligne à ligne. Pas de ML, pas de LLM. Juste des seuils, des jointures,
des comparaisons.

| signal | déclenché quand |
|---|---|
| **opposition naissante** | contestation CNPrV < 60 jours + projet actif à ≤ 15 km · alarme |
| **paradoxe opérateur** | opérateur ≥ 10 % de la puissance nationale + 0 contestation |
| **projet latent MRAe** | projet visible uniquement dans un avis MRAe |
| **ceinture de résistance** | département > 60 % de contestations |
| **opacité opérateur** | projet ≥ 10 MWc sans opérateur déclaré |

Deux règles arrivent en v0.2 : divergence entre registres, hausse
d'opérateur.

---

## Sources

Quatre registres publics français, croisés après fusion inter-sources :

- [ADEME Observatoire](https://data.ademe.fr/) · projets raccordés
- [projets-environnement.gouv.fr](https://www.projets-environnement.gouv.fr/) · projets en instruction
- MRAe · avis d'autorité environnementale régionale
- [Coordination Nationale Photorévoltée](https://victoires-pv.gogocarto.fr/) · contestations victorieuses

Aucune de ces sources ne voit l'ensemble. panoptic les croise.

## Licences

- Code : **AGPL-3.0-or-later**
- Données : **CC-BY-SA-4.0**

Forkable, modifiable, redistribuable sous la même licence.

## Liens

- Site : [panoptic.tawiza.fr](https://panoptic.tawiza.fr)
- Article méthodo : [panoptic.tawiza.fr/article/](https://panoptic.tawiza.fr/article/)
- Tawiza : [tawiza.fr](https://tawiza.fr)

Un projet qu'on a raté, un opérateur mal identifié, un angle oublié :
[tawiza.v0@gmail.com](mailto:tawiza.v0@gmail.com) ou DM `@tawiza.fr`.
