# panoptic

*un regard sur l'agrivoltaïsme français*

CLI citoyenne, souveraine, portable. Tu tapes `panoptic 47`, tu vois les
projets agrivoltaïques près de chez toi — qui les porte, qui les conteste,
quels micro-signaux panoptic a détectés automatiquement.

Aucun compte. Aucun cloud. Aucun GPU. Une commande.

---

## Installation

```bash
pip install panoptic-tawiza
```

Prérequis : Python 3.10+, `pip`. La base de données SQLite est embarquée
(~400 KB), donc l'outil tourne hors-ligne dès l'installation.

## Usage

### Recherche locale

```bash
panoptic 47                     # département (Lot-et-Garonne)
panoptic 47001                  # code INSEE commune
panoptic 47250                  # code postal
panoptic "Pujo-le-Plan"         # nom commune (fuzzy)
panoptic --help                 # aide
```

Chaque rapport affiche :
- l'état de **3AYNE** (dormant / attentif / éveillé / alarmé) selon la
  fraîcheur de la data et les signaux détectés
- la liste des projets recensés par commune, puissance, statut, opérateur
- les contestations documentées par la Coordination Nationale Photorévoltée
- les **micro-signaux** auto-détectés : paradoxes d'opérateurs silencieux,
  projets latents visibles dans MRAe seulement, ceintures de résistance

### Export HTML partageable

```bash
panoptic 47 --html rapport.html
```

Le fichier HTML est auto-suffisant (CSS inline, SVG embarqué) : partage
email, WhatsApp, clé USB. Il marche sur n'importe quel navigateur, hors ligne.

### Rafraîchissement des données

```bash
panoptic update                 # sync depuis panoptic.tawiza.fr/data/
panoptic update --force         # re-télécharger même si à jour
panoptic freshness              # état des sources
```

La DB distante est republiée périodiquement. Le manifest signé SHA-256
garantit l'intégrité.

---

## Sources

panoptic croise quatre registres publics français :

| Source | Rôle |
|--------|------|
| [ADEME Observatoire](https://data.ademe.fr/) | projets raccordés, métadonnées techniques |
| [projets-environnement.gouv.fr](https://www.projets-environnement.gouv.fr/) | projets en instruction |
| MRAe (autorité environnementale régionale) | avis en amont de l'autorisation |
| [Coordination Nationale Photorévoltée](https://victoires-pv.gogocarto.fr/) | contestations victorieuses de collectifs locaux |

Aucune de ces sources ne voit l'ensemble. panoptic les croise après fusion
inter-sources avec une règle éditoriale publique (cf.
[`panoptic/export/fusion.py`](https://github.com/tawiza/panoptic-cli/blob/main/../panoptic/export/fusion.py)
dans le pipeline `tawiza/panoptic-pipeline`).

## Principes

- **Souveraineté** : la DB SQLite est archivable. Si `panoptic.tawiza.fr`
  disparaît, ton binaire + ta DB continuent de marcher.
- **Transparence** : chaque résultat montre sa source, sa date de collecte,
  son score de confiance. Rien de caché.
- **Humilité** : on n'affirme pas, on rapproche. On n'appelle pas ça un
  "observatoire" — c'est un regard citoyen sur une filière opaque.
- **3AYNE non-désactivable** : l'œil Tawiza est la signature et
  l'indicateur d'état de l'outil. Pas de flag pour le retirer.

## Licences

- Code : **AGPL-3.0-or-later**
- Données : **CC-BY-SA-4.0**

Tu peux forker, modifier, redistribuer. Tu dois partager tes modifications
sous la même licence.

## Liens

- Site : [panoptic.tawiza.fr](https://panoptic.tawiza.fr)
- Tawiza : [tawiza.fr](https://tawiza.fr)
- Signaler un projet manquant, un opérateur mal identifié, un angle oublié :
  `DM @tawiza.fr` ou email via le site.
