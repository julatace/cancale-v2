# Après la vidéo : comment l'agent publie sur TikTok et YouTube (étape par étape)

Ce document décrit exactement ce que fait l'agent « clips » (et l'agent piano) une fois qu'une vidéo est prête. À destination de l'agent qui FABRIQUE les vidéos.

## 0. Pourquoi « il met les vidéos dans un dossier et rien après »
Déposer un fichier dans `~/Desktop/Clips` ne publie rien tout seul. Il faut que **l'agent clips tourne** et qu'il ait **de quoi programmer** :
1. **L'agent clips doit être lancé** : `./p.sh --instance clips ui` (ou double-clic « Lancer Clips », ou `./p.sh --instance clips autostart` pour qu'il démarre à l'ouverture de session). S'il ne tourne pas, le dossier se remplit et personne ne le lit.
2. **Son pilote automatique doit être activé** (activé d'office par `instance-init`) OU l'agenda rempli à la main sur sa page. Sans l'un des deux, l'agent importe les vidéos mais ne programme rien.
3. **Son profil Chrome doit être connecté** à TikTok et YouTube (compte du 2e agent) avec « Autoriser JavaScript dans Apple Events ».
4. Le Mac doit être allumé et la session ouverte pendant l'envoi.
Contrôle rapide : page de l'agent clips → onglet « Mes vidéos » : « N vidéo(s) attendent dans le dossier · M prête(s) ». Si N ne baisse pas au bout de 30 s, l'agent ne tourne pas. Si M monte sans que rien parte : pilote automatique éteint ou Chrome pas connecté (voir le journal « Détails techniques »).
Alternative immédiate sans attendre l'agenda : `./p.sh --instance clips post /chemin/video.mp4 --title "..." --at "AAAA-MM-JJ HH:MM"`.

## 1. Prise en charge (toutes les 30 s)
- Fichier `.mp4/.mov` stable depuis 4 s (les `.part` et fichiers cachés sont ignorés), lisible par ffprobe.
- Empreinte SHA-256 : même contenu déjà vu = écarté (`doublons/`). Illisible = `ignorées/`.
- Titre = 1re ligne du `.txt` sinon nom du fichier ; hashtags = ligne `#…` du `.txt` sinon réglage par défaut ; description = reste du `.txt` sinon réglage par défaut.
- Vidéo verticale ≤ 180 s = Short ; horizontale = vidéo YouTube normale. Le fichier est déplacé dans `data/instances/clips/rendered/`, ligne `videos` créée (statut READY).

## 2. Planification
- Le pilote automatique compte ce qui est déjà programmé dans les réseaux (traces `schedule` en `DONE`), calcule ce qui manque sur N jours (heures `12:30, 19:00` par défaut) et lance UNE vidéo à la fois.
- Chaque vidéo reçoit un créneau futur (≥ 20 min, ≤ 10 jours). Jamais de publication immédiate sauf `--now` demandé.
- Si aucun créneau n'est libre aujourd'hui, le surplus passe au jour suivant.

## 3. Envoi (`publish_video`) — dans cet ordre : TikTok puis YouTube
Garde-fous : un verrou par processus + un verrou entre agents (`data/.send.lock`) pour ne jamais piloter Chrome à deux ; si la plateforme a déjà un statut bon, on ne la refait pas ; `SENDING`/`UNCERTAIN` = jamais renvoyé automatiquement (peut déjà être en ligne).

### TikTok (Chrome, profil de l'agent)
1. Ouvre `tiktok.com/upload` dans UN onglet réutilisé du bon profil (`open -na … --profile-directory`), teste le réglage JavaScript.
2. Injecte le fichier directement dans l'`input[type=file]` (base64 par morceaux de 240 000 caractères) ; secours : fenêtre « Ouvrir » (jamais de frappe sans avoir vérifié la fenêtre).
3. Attend la fin du téléversement, écrit légende + hashtags (relue et vérifiée).
4. Visibilité « Tout le monde ».
5. Programmation : bascule « Planifier », règle date et heure, clique « Planifier ». **Cette étape n'est pas encore vérifiée sur la vraie page TikTok** : si elle échoue, la vidéo est enregistrée en **brouillon** (statut `DRAFT`, rien n'est perdu) et le journal l'indique. Captures dans `data/instances/clips/debug/steps/`, liste des boutons vus dans `…/debug/tiktok_planifier_page.txt`.

### YouTube Studio (même profil)
1. Ouvre le Studio (même onglet réutilisé), envoie le fichier de la même façon.
2. Attend la fin du traitement (le bouton Publier est désactivé tant que la vidéo n'est pas traitée, jusqu'à ~budget proportionnel à la taille).
3. Titre et description : saisis puis relus (jusqu'à 5 essais, YouTube pouvait écraser le titre) ; « Pas conçue pour les enfants ».
4. Visibilité « Public » vérifiée (`tp-yt-paper-radio-button[name="PUBLIC"]`).
5. Programmation : « Programmer » → date et heure au format local → confirmation ; sinon brouillon.
6. Limite : 4 envois/jour sur YouTube ; au-delà la vidéo reste `WAITING` et reprend automatiquement quand la limite se libère.

## 4. Après l'envoi
- Statuts bons : `PUBLISHED`, `SCHEDULED`, `DRAFT`. Si TOUTES les plateformes sont bonnes : fichier vidéo + copie supprimés du Mac.
- Une plateforme en échec ne bloque pas l'autre ; la vidéo est gardée pour réessayer. Une notification macOS prévient en cas de souci ou à la fin d'un lot.
- Rien n'est jamais renvoyé deux fois (table `publications`, unique par vidéo + plateforme).

## 5. Ce que l'agent fabricant doit retenir
Déposer proprement (`.part` puis renommer), des titres et hashtags soignés dans le `.txt`, ne rien supprimer dans `Clips/`, et si rien ne part : vérifier les 4 points du §0 avant d'accuser la publication.
