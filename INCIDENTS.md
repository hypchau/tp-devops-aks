# Journal des incidents

## Incident n°1 : application injoignable hors du conteneur

- **Partie / étape :** Partie 2, étape 2.4 (`docker run` puis `curl localhost:8080`)
- **Symptôme observé :** `docker ps` montre le conteneur `Up` avec `[::]:8080->8080/tcp`, mais `curl localhost:8080` échoue : `curl: (52) Empty reply from server`.
- **Diagnostic :**
  - `docker inspect mon-app --format '{{.Config.User}} {{json .Config.Cmd}}'` → `10001 ["gunicorn","--bind","127.0.0.1:8080","--workers","2","app:app"]`
  - `docker exec mon-app python -c "...urlopen('http://127.0.0.1:8080/health')..."` → `b'{"status":"ok"}\n'` : l'application répond depuis l'intérieur du conteneur.
  - Conclusion : l'application fonctionne. Seule l'interface d'écoute pose problème.
- **Cause racine :** la commande de démarrage fournie par l'exploitation fait écouter gunicorn sur `127.0.0.1`, la loopback *du conteneur*. Le trafic publié par `-p 8080:8080` arrive sur l'interface réseau du conteneur (`eth0`), où rien n'écoute, d'où l'« Empty reply ». Sur Kubernetes, les probes (le kubelet sonde l'IP du pod) échoueraient aussi, et les pods ne seraient jamais `Ready`.
- **Correction appliquée :** dans le `Dockerfile`, `--bind 0.0.0.0:8080` (commit `feat: conteneurisation de l'application`).
- **Comment l'éviter à l'avenir :** dans un conteneur, un serveur doit écouter sur `0.0.0.0`. Ajouter en CI un test de fumée (`docker run` puis `curl --fail localhost:8080/health`).

## Incident n°2 : le pipeline ne se déclenche pas après la fusion sur main

- **Partie / étape :** Partie 3, étape 3.4 (fusion de la PR #4, publication de l'image)
- **Symptôme observé :** après la fusion de la PR #4 dans `main`, l'onglet Actions ne montre aucun nouveau run (seulement les runs #1 à #3 de type `Pull request #4`). Aucun paquet `tp-devops-aks` dans Packages : l'image n'a jamais été construite.
- **Diagnostic :** filtre Actions « Branch = main » → aucun run. `git branch -a` → la branche par défaut est `origin/main`, il n'existe pas de `master`. `grep -A3 "^on:" .github/workflows/ci-cd.yml` → `push: branches: [master]`.
- **Cause racine :** le modèle de l'équipe déclenche le workflow sur les push vers `master`, alors que le dépôt utilise `main`. Le push produit par la fusion ne correspond à aucun déclencheur.
- **Correction appliquée :** `branches: [main]` dans `.github/workflows/ci-cd.yml` (commit `fix(ci): déclencher le pipeline sur main`).
- **Comment l'éviter à l'avenir :** relire les déclencheurs `on:` en revue de code et vérifier le nom réel de la branche par défaut. Protéger `main` en exigeant le statut « Qualité et tests » (bonus B1).

## Incident n°3 : pods en CrashLoopBackOff (OOMKilled)

- **Partie / étape :** Partie 4, étape 4.2 (Deployment avec les ressources imposées 16Mi / 32Mi)
- **Symptôme observé :** `kubectl get pods -w` montre les pods `mon-app-79cfc4c489-fn5tv` et `mon-app-79cfc4c489-6th5g` passer de `OOMKilled` à `CrashLoopBackOff` en moins de 10 s, toujours `0/1`, avec 3 redémarrages en 70 s.
- **Diagnostic :** le statut `OOMKilled` indique que le noyau a tué le conteneur pour dépassement de sa limite mémoire (`kubectl describe pod` → `Reason: OOMKilled, Exit Code: 137` = SIGKILL). Limite déclarée : `limits.memory: 32Mi`. Mesure locale de gunicorn (1 maître + 2 workers) : environ 89 Mi.
- **Cause racine :** les ressources imposées (`requests 16Mi`, `limits 32Mi`) sont inférieures à la consommation réelle de l'application dès son démarrage. L'OOM killer du cgroup tue le conteneur, que le kubelet redémarre avec un délai croissant (CrashLoopBackOff).
- **Correction appliquée :** `requests.memory: 64Mi` et `limits.memory: 128Mi` (CPU inchangé). Résultat : ReplicaSet `mon-app-6c8b7b9cc8`, 2 pods `1/1 Running`, 0 restart. Compatible avec le quota (1Gi / 64Mi = 16 pods, au-dessus de la limite de 10 pods). Commit `feat: manifestes Kubernetes`.
- **Comment l'éviter à l'avenir :** dimensionner requests et limits à partir de mesures (`kubectl top pods`) et tester en local avec la même contrainte (`docker run --memory=32m`).
