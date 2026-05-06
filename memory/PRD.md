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
- ✅ Game catalog (31 seeded), search, genre/platform filters
- ✅ Game detail with avg_rating + review_count
- ✅ Reviews: 1–10 rating, hours_played, sub-categories (graphics/story/tutorial/gameplay), recommends, platform, note
- ✅ Ranking: 5 levels (Novato 0/Explorador 50/Aventureiro 250/Avaliador 1000/Apreciador 5000) with points
- ✅ Points: +50 complete review, +25 incomplete; one award per (user, game)
- ✅ Guides: gated to 50+ pts, 5 categories (dica/tutorial/como-zerar/estratégia/macete)
- ✅ Help requests + replies (3 kinds: ajuda, jogar-junto, dica)
- ✅ Friends: search, request, accept, list
- ✅ Theme toggle (light orange+white / dark orange+black) with localStorage persistence
- ✅ Auth callback for Emergent Google OAuth
- ✅ Brute-force lockout (5 attempts → 15min)

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
