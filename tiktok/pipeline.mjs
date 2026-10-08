// Pipeline : videos.json -> Synthesia (9:16) -> téléchargement -> publication TikTok.
// Usage : node tiktok/pipeline.mjs [--test] [--no-post] [--max N]
// Variables : SYNTHESIA_API_KEY, SYNTHESIA_AVATAR, SYNTHESIA_BACKGROUND (opt.),
//             TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN,
//             TIKTOK_PRIVACY (défaut SELF_ONLY tant que l'app TikTok n'est pas auditée)
import { readFile, writeFile, mkdir } from 'node:fs/promises'

const env = process.env
const args = process.argv.slice(2)
const TEST = args.includes('--test')       // Synthesia test = gratuit, filigrané
const NO_POST = args.includes('--no-post')
const MAX = Number(args[args.indexOf('--max') + 1]) || 1
const FILE = new URL('./videos.json', import.meta.url)
const OUT = new URL('./out/', import.meta.url)
const sleep = ms => new Promise(r => setTimeout(r, ms))

const need = k => { if (!env[k]) throw new Error(`Variable manquante : ${k}`); return env[k] }

async function api(url, opts, label) {
  const res = await fetch(url, opts)
  const text = await res.text()
  if (!res.ok) throw new Error(`${label} ${res.status}: ${text.slice(0, 300)}`)
  return text ? JSON.parse(text) : {}
}

// --- Synthesia ---
async function createVideo(v) {
  const body = {
    title: v.title,
    test: TEST,
    aspectRatio: '9:16',
    input: [{
      scriptText: v.script,
      avatar: v.avatar || need('SYNTHESIA_AVATAR'),
      background: v.background || env.SYNTHESIA_BACKGROUND || 'off_white',
    }],
  }
  const r = await api('https://api.synthesia.io/v2/videos', {
    method: 'POST',
    headers: { Authorization: need('SYNTHESIA_API_KEY'), 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, 'Synthesia create')
  return r.id
}

async function waitVideo(id) {
  for (let i = 0; i < 120; i++) {           // ~20 min max
    const r = await api(`https://api.synthesia.io/v2/videos/${id}`, {
      headers: { Authorization: need('SYNTHESIA_API_KEY') },
    }, 'Synthesia status')
    if (r.status === 'complete') return r.download
    if (r.status === 'failed' || r.status === 'rejected') throw new Error(`Synthesia: ${r.status}`)
    await sleep(10_000)
  }
  throw new Error('Synthesia: timeout')
}

async function download(url, name) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Téléchargement ${res.status}`)
  const buf = Buffer.from(await res.arrayBuffer())
  await mkdir(OUT, { recursive: true })
  const path = new URL(`${name}.mp4`, OUT)
  await writeFile(path, buf)
  return buf
}

// --- TikTok Content Posting API ---
async function tiktokToken() {
  const r = await api('https://open.tiktokapis.com/v2/oauth/token/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_key: need('TIKTOK_CLIENT_KEY'),
      client_secret: need('TIKTOK_CLIENT_SECRET'),
      grant_type: 'refresh_token',
      refresh_token: need('TIKTOK_REFRESH_TOKEN'),
    }),
  }, 'TikTok token')
  if (r.refresh_token && r.refresh_token !== env.TIKTOK_REFRESH_TOKEN)
    console.warn('⚠ TikTok a émis un nouveau refresh_token, mets à jour le secret :', r.refresh_token.slice(0, 6) + '…')
  return r.access_token
}

async function postTikTok(token, buf, v) {
  const size = buf.length
  const chunk = size < 64e6 ? size : 10e6
  const total = Math.ceil(size / chunk)
  const init = await api('https://open.tiktokapis.com/v2/post/publish/video/init/', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json; charset=UTF-8' },
    body: JSON.stringify({
      post_info: {
        title: v.caption.slice(0, 2200),
        privacy_level: env.TIKTOK_PRIVACY || 'SELF_ONLY',
        disable_comment: false,
      },
      source_info: { source: 'FILE_UPLOAD', video_size: size, chunk_size: chunk, total_chunk_count: total },
    }),
  }, 'TikTok init')
  const { upload_url, publish_id } = init.data
  for (let i = 0; i < total; i++) {
    const start = i * chunk
    const end = Math.min(start + chunk, size) - 1
    const res = await fetch(upload_url, {
      method: 'PUT',
      headers: { 'Content-Type': 'video/mp4', 'Content-Range': `bytes ${start}-${end}/${size}` },
      body: buf.subarray(start, end + 1),
    })
    if (!res.ok) throw new Error(`TikTok upload ${res.status}`)
  }
  for (let i = 0; i < 30; i++) {
    const s = await api('https://open.tiktokapis.com/v2/post/publish/status/fetch/', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ publish_id }),
    }, 'TikTok status')
    const st = s.data?.status
    if (st === 'PUBLISH_COMPLETE') return publish_id
    if (st === 'FAILED') throw new Error(`TikTok: ${s.data.fail_reason}`)
    await sleep(5000)
  }
  throw new Error('TikTok: timeout')
}

// --- Main ---
const videos = JSON.parse(await readFile(FILE, 'utf8'))
const todo = videos.filter(v => v.status === 'pending').slice(0, MAX)
if (!todo.length) { console.log('Rien à faire : aucune vidéo "pending".'); process.exit(0) }

const token = NO_POST ? null : await tiktokToken()
let failed = 0
for (const v of todo) {
  try {
    console.log(`▶ ${v.id}`)
    if (!v.synthesiaId) { v.synthesiaId = await createVideo(v); await writeFile(FILE, JSON.stringify(videos, null, 2)) }
    const url = await waitVideo(v.synthesiaId)
    const buf = await download(url, v.id)
    if (NO_POST) { v.status = 'rendered' }
    else { v.publishId = await postTikTok(token, buf, v); v.status = 'posted' }
    console.log(`✔ ${v.id} -> ${v.status}`)
  } catch (e) {
    failed++; v.error = e.message; console.error(`✖ ${v.id}: ${e.message}`)
  }
  await writeFile(FILE, JSON.stringify(videos, null, 2))
}
process.exit(failed ? 1 : 0)
