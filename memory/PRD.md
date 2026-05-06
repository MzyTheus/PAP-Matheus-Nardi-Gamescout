# GameScout — PRD

## Original Problem Statement (Português)
Plataforma social de jogos com:
- Autenticação (Email + Google + Steam)
- Perfis (nome, ID único, foto, bio, contas externas, preferências de jogo, plataformas, specs PC)
- Sistema social (amigos, chat, grupos, comunidades)
- Ranking/Reputação (Novato → Apreciador de Obras)
- Avaliações detalhadas (estrelas, horas, categorias, recomendação, plataforma, observação)
- Guias (apenas Explorador 50pts+)
- Pedidos de ajuda
- Interface PT-PT, paleta laranja+branco / laranja+preto

## User Choices Confirmed
- Auth: Email/password JWT + Emergent Google Login (Steam adiado)
- Stack: React + FastAPI + MongoDB
- Catálogo: seed manual de ~30 jogos
- Foto perfil: URL/base64 (sem object storage no MVP)
- Idioma: apenas Português

## Architecture
- Backend `/app/backend/server.py` — FastAPI, dual-auth (JWT cookie + Emergent session_token cookie), all endpoints under `/api`
- DB: MongoDB collections `users`, `user_sessions`, `games`, `reviews`, `guides`, `help_requests`, `friendships`, `login_attempts`
- Frontend: React Router, AuthContext, Tailwind theme (orange/black-white), Unbounded/Manrope/JetBrains Mono fonts, Shadcn UI
- All MongoDB queries exclude `_id`. Users use UUID `user_id` field.

## Implemented (2026-05-06)
- ✅ Auth: register, login, logout, /me, /me/full, refresh, Google session exchange
- ✅ Profile CRUD: bio, social links (Discord/TikTok/Insta/Twitch), prefs (favorite_game, platforms, pc_specs)
- ✅ **IGDB importer** — fetches 150–200 jogos populares + recentes na inicialização (replaces seed); endpoint admin `POST /api/admin/games/refresh` para re-importar
- ✅ Catálogo dinâmico com filtros gerados automaticamente do conteúdo (`/api/games/meta` retorna géneros + plataformas com contagens)
- ✅ Game detail with avg_rating + review_count
- ✅ Reviews: 1–10 rating, hours_played, sub-categories, recommends, platform, note
- ✅ Ranking: 5 levels with points (+50 complete review, +25 incomplete; one award per pair)
- ✅ Guides: gated to 50+ pts, 5 categories
- ✅ Help requests + replies
- ✅ Friends: search, request, accept, list
- ✅ Theme toggle (dark/light) com localStorage
- ✅ Auth callback Emergent Google OAuth
- ✅ Brute-force lockout
- ✅ CORS via regex `*.emergentagent.com` + frontend usa `window.location.origin` (resolve cross-origin entre URLs preview)

## Backlog
### P1
- Real-time chat between friends (currently friend system + UI only — chat bubbles WIP)
- Comunidades (grupos públicos)
- Upload de foto via object storage (atualmente URL)
- Edit/delete review UI button
- Steam OAuth (requer API key Steam do utilizador)

### P2
- Notificações in-app (pedidos amizade, respostas, novas avaliações em jogos favoritos)
- Listas de favoritos do utilizador (homepage seção "Jogos favoritos")
- Sistema de comentários em avaliações + likes
- Sistema de moderação (admin)
- Páginas dedicadas a categorias (Terror, Ação, etc.)
- Importação automática de catálogo (IGDB API)
- Dark/light a partir do prefers-color-scheme

## Test Credentials
Admin: `admin@gamescout.pt` / `admin123` (10000 pts → Apreciador de Obras)
