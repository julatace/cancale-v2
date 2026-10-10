# Message à coller à l'autre agent (la fabrique de vidéos)

Bonjour. Voici comment ton travail s'enchaîne avec l'agent de publication (« clips »). Tu n'as RIEN d'autre à faire que fabriquer tes vidéos et les déposer ; la publication est entièrement automatique.

## Réponses à tes questions
1. **Le dossier est bien `~/Desktop/Clips`** (= `/Users/<utilisateur>/Desktop/Clips`). Il est créé par `./p.sh instance-init clips …`. Son chemin exact est affiché dans l'onglet « Mes vidéos » de la page de l'agent clips.
2. **Programmation native TikTok : NON vérifiée sur la vraie page à ce jour.** YouTube est programmé nativement et vérifié. Si TikTok ne programme pas, l'agent met la vidéo en brouillon (jamais perdue) et le dit dans son journal. Ne promets pas « programmé TikTok » avant d'avoir vu une vraie vidéo programmée dans TikTok Studio.
3. **Nombre de vidéos par jour et heures : c'est l'utilisateur qui les choisit** dans la page de l'agent clips (agenda ou pilote automatique). Pas toi.

## Ce que tu dois faire pour chaque vidéo
- Écris le fichier sous `Clips/nom.mp4.part`, puis **renomme** en `Clips/nom.mp4` une fois terminé (les `.part` sont ignorés).
- `.mp4` H.264 + AAC. Vertical 1080×1920 ≤ 180 s = TikTok + YouTube Short. Horizontal = YouTube normal.
- Ajoute `Clips/nom.txt` (UTF-8) : ligne 1 = titre accrocheur (≤ 95 caractères) ; une ligne de `#hashtags` (≤ 8, pertinents pour la vidéo) ; puis une courte description. Sans `.txt`, le titre vient du nom de fichier.
- Un nom de fichier unique par vidéo, jamais le même contenu deux fois (les doublons sont écartés automatiquement).
- Ne supprime rien dans `Clips/` : l'agent prend le fichier en charge, le publie puis le supprime du Mac.

## Autre façon de publier : la commande `post`
Au lieu du dossier, tu peux appeler directement (depuis `~/cancale-v2/piano-studio-ai`) :
`./p.sh --instance clips post /chemin/video.mp4 --title "..." --hashtags "#a #b" --description "..." --at "2026-10-12 19:00"`
→ envoi TikTok puis YouTube, programmé dans leurs plannings à cette date. Code retour 0 = tout est bon. Sans `--at` ni `--now`, rien ne part.

## Ce que tu peux faire seul, sans rien demander
Fabriquer à l'avance (ex. 7 à 14 vidéos), les déposer au fur et à mesure, garder un stock, varier les titres et hashtags. L'agent clips les programme à la cadence de l'agenda, une à la fois, TikTok puis YouTube, en public, depuis SON profil Chrome (séparé de celui du piano).

## Ce qui ne dépend pas de toi
Connexion Chrome aux comptes, activation du pilote automatique, démarrage de l'agent clips (`./p.sh --instance clips ui` ou `autostart`) : c'est l'utilisateur qui le fait une fois. Si le dossier reste plein et que rien n'est publié, dis à l'utilisateur de vérifier que l'agent clips tourne et que son pilote automatique est activé.
