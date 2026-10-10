# Deuxième agent : « clips » (publie tes vidéos déjà prêtes)

Même moteur de publication que l'agent piano (TikTok + YouTube, programmation native, public, pas de doublon, suppression après publication,
pilote automatique, notifications), mais **aucune fabrication** : tu déposes des vidéos dans un dossier.

## Mise en place (une seule fois)
```
cd ~/cancale-v2/piano-studio-ai
git pull
./p.sh chrome-profiles                       # liste les profils Chrome : repère celui du 2e compte
./p.sh instance-init clips --profile "NomDuProfil"   # crée l'agent (données séparées, dossier ~/Desktop/Clips, port 8766+)
./p.sh --instance clips ui                   # lance sa page
./p.sh --instance clips autostart            # (facultatif) démarre tout seul à l'ouverture de session
```
Dans Chrome, ouvre ce profil une fois et connecte-toi à TikTok et YouTube (puis menu Présentation → Développeur → « Autoriser JavaScript dans Apple Events »).

## Utilisation
- Dépose des `.mp4` / `.mov` dans le dossier. Titre = nom du fichier (`03_mon_clip.mp4` → « Mon clip »), ou 1re ligne d'un `.txt` du même nom (le reste = description).
- Description et hashtags par défaut : onglet « Mes vidéos ». Active le pilote automatique ou remplis l'agenda.
- Un fichier est pris en charge (déplacé), publié, puis supprimé du Mac. Doublon (même contenu) = écarté dans `doublons/`. Fichier illisible = `ignorées/`.

## Contrat pour un agent qui dépose ses vidéos (ex. fabrique de vidéos)
- Dossier : `~/Desktop/Clips` (réglable dans l'onglet « Mes vidéos »).
- Écrire d'abord sous un nom provisoire (`nom.mp4.part` ou `.nom.mp4`) puis RENOMMER en `nom.mp4` quand c'est fini : les fichiers `.part` et ceux qui commencent par un point sont ignorés. (De toute façon un fichier doit rester inchangé 4 s avant d'être pris.)
- Format : `.mp4` / `.mov`, H.264 + AAC. Vertical (hauteur ≥ largeur, ≤ 180 s) = TikTok + YouTube Short ; horizontal = YouTube normal.
- Fichier texte facultatif du même nom (`nom.txt`, UTF-8) : ligne 1 = titre (95 caractères max) ; une ligne ne contenant que des `#hashtags` = hashtags de cette vidéo (8 max) ; le reste = description.
- Ne jamais redéposer le même contenu : un doublon est écarté (empreinte du fichier). Ne rien supprimer dans le dossier : l'agent le fait après publication.
- Cadence : c'est l'agenda / le pilote automatique de l'agent clips qui décide quand publier (pas le déposant). Déposer plusieurs vidéos d'avance est sans risque.

## Séparation des comptes
Chaque agent a son profil Chrome (`tiktok.chrome_profile`, `youtube.chrome_profile`), sa base, son agenda et sa page : rien n'est partagé.
Un verrou commun (`data/.send.lock`) empêche deux agents de piloter Chrome en même temps (focus, clavier) : le 2e attend son tour.

## Ce que l'agent sait déjà (hérité du code de publication)
- Un seul onglet réutilisé par site, fichier injecté directement dans la page, titre / description vérifiés après saisie, public vérifié.
- YouTube : limite de 4 envois par jour (le surplus attend), programmation « Programmer », confirmation d'envoi lente gérée.
- TikTok : « Planifier » (jusqu'à 10 jours), brouillon en secours. Jamais de renvoi automatique après un envoi incertain.
- Captures de chaque étape : `data/instances/<nom>/debug/steps/`.
