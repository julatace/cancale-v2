// Obtient le refresh_token TikTok (à faire une seule fois).
// Étape 1 : node tiktok/auth.mjs url      -> affiche l'adresse à ouvrir dans le navigateur
// Étape 2 : node tiktok/auth.mjs token "<adresse de retour complète ou code>"
// Variables : TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REDIRECT_URI
const { TIKTOK_CLIENT_KEY: key, TIKTOK_CLIENT_SECRET: secret, TIKTOK_REDIRECT_URI: redirect } = process.env
const [cmd, input] = process.argv.slice(2)
if (!key || !redirect) { console.error('Définis TIKTOK_CLIENT_KEY et TIKTOK_REDIRECT_URI (et TIKTOK_CLIENT_SECRET pour "token").'); process.exit(1) }

if (cmd === 'url') {
  const q = new URLSearchParams({
    client_key: key, response_type: 'code', scope: 'user.info.basic,video.publish',
    redirect_uri: redirect, state: 'cancale',
  })
  console.log('Ouvre cette adresse dans ton navigateur :\n\nhttps://www.tiktok.com/v2/auth/authorize/?' + q)
} else if (cmd === 'token' && input) {
  if (!secret) { console.error('Définis TIKTOK_CLIENT_SECRET.'); process.exit(1) }
  // accepte l'adresse complète (https://.../callback?code=...) ou le code seul
  const code = input.includes('code=') ? new URL(input).searchParams.get('code') : decodeURIComponent(input)
  const res = await fetch('https://open.tiktokapis.com/v2/oauth/token/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ client_key: key, client_secret: secret, code, grant_type: 'authorization_code', redirect_uri: redirect }),
  })
  const j = await res.json()
  if (!j.refresh_token) { console.error('Échec :', JSON.stringify(j)); process.exit(1) }
  console.log('scope :', j.scope, '\nrefresh_token (à mettre dans le secret TIKTOK_REFRESH_TOKEN) :\n' + j.refresh_token)
} else {
  console.error('Usage : node tiktok/auth.mjs url | token "<adresse ou code>"'); process.exit(1)
}
