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

## Implemented (2026-05-29 — iteração 6)
- ✅ **Auth Gmail-only**: registo e login devolvem 400 para emails que não terminem em `@gmail.com`
- ✅ **Verificação de email obrigatória via Resend**:
  - `RESEND_API_KEY` configurada; email HTML com código de 6 dígitos
  - `email_verifications` collection com TTL de 30min
  - `POST /api/auth/verify-email` (com código), `POST /api/auth/resend-code`
  - Gating de 24 endpoints WRITE (review/guide/comunidade/help/wishlist/friend/DM): 403 enquanto `email_verified=false`
  - Helper `get_verified_user` (Google users já são pre-verified)
- ✅ **Admin `matheusvittore670@gmail.com` / `admin123`**:
  - Seedado ao arranque com `email_verified=true`
  - admin@gamescout.pt demovido a `user` automaticamente
- ✅ **Moderação admin** (`/api/admin/*`): stats, lista/pesquisa users, warn, suspend/unsuspend, PATCH /admin/games/{id}, feature/unfeature reviews+guias, delete qualquer mensagem
- ✅ **Página `/admin`** com tabela de utilizadores, dialogs warn/suspend, contadores globais
- ✅ **Apagar mensagem própria**: `DELETE /api/chat/messages/{id}` e `DELETE /api/communities/{cid}/messages/{id}` (sender, owner-da-comunidade ou admin); ícone "lixo" no hover sobre própria mensagem
- ✅ **Limpeza automática ao startup** (`_cleanup_test_data`): remove utilizadores TEST_/test_/tester/smoke_/qa_ + reviews/guias/comunidades associadas
- ✅ **Catálogo focado**: 500 main games (filtro `_is_main_game` exclui DLC/expansão/remaster/port/bundle/mod/episode/season). Whitelist atualizada (GTA V, Fortnite, Valorant, Helldivers 2, Baldur's Gate 3, Palworld, Marvel Rivals, etc.)
- ✅ Testes: 30/30 backend pytest (após fix `create_review` → `get_verified_user`)


## Implemented (2026-05-06 — iteração 5)
- ✅ **Bug fix**: import duplicado de `useState` em GameDetail.jsx (compile error)
- ✅ **Wishlist**:
  - Backend: `POST/DELETE/GET /api/wishlist/{game_id}`, `GET /api/wishlist`, `GET /api/users/{user_id}/wishlist`
  - User model: campo `wishlist: [game_id]` (lista preservando ordem de inserção via `$addToSet`)
  - Frontend: botão coração (♥) em todos os GameCards do catálogo, top games, descobrir; toggle no GameDetail; nova página `/wishlist` (própria) e `/wishlist/{userId}` (pública); link no perfil + entrada no menu do utilizador
  - Profile mostra contagem da wishlist com link

## Implemented (2026-05-06 — iteração 4)
- ✅ **Remover amizade** (DELETE /api/friends/{user_id}) — funciona para amizade aceite, pedido enviado (cancelar) e pedido recebido (recusar). UI no Profile e na lista de amigos.
- ✅ **Upload de avatar** com 2 opções: ficheiro do dispositivo (POST /api/users/me/avatar multipart, máx 1.5MB, JPG/PNG/WEBP/GIF → data URL) OU URL externo (PATCH /api/users/me). Componente `AvatarPicker` com tabs.
- ✅ **Ranking Bayesiano** (`GET /api/games/top`) com fórmula `(n*R + C*M) / (n + C)` (C=50, M=70). Página `/top` com filtros de género e plataforma, medalhas para top 3.
- ✅ **Editar/eliminar reviews, guias, pedidos de ajuda e respostas**:
  - PATCH/DELETE `/api/reviews/{id}` (owner ou admin)
  - PATCH/DELETE `/api/guides/{id}` (owner ou admin)
  - PATCH/DELETE `/api/help-requests/{id}` (owner)
  - PATCH/DELETE `/api/help-requests/{id}/replies/{rid}` (autor)
  - UI: dropdowns (...) com Editar/Apagar nos cards. Confirm dialogs antes de apagar.
- ✅ **Catálogo aumentado para 900 jogos** com franquias específicas: Resident Evil, FNAF, Minecraft, Terraria, No Man's Sky, Dead by Daylight + 60+ outras (Dark Souls, Halo, GTA, Bioshock, Subnautica, Among Us, Genshin Impact, etc).
- ✅ **Bug fixes propagados**: PATCH /users/me + upload avatar atualizam name/picture em reviews/guides/help_requests denormalizados (incluindo replies)
- ✅ Testing: 34/34 backend tests PASSED — auth, friendship, avatar upload, ranking, edit/delete CRUD, ownership 403s, catalog franchise checks.

## Implemented (2026-05-06 — iteração 3)
- ✅ Catálogo aumentado para **500 jogos** (10 queries IGDB diversificadas: top all-time, populares recentes, hyped, géneros específicos)
- ✅ **Re-importação automática a cada 7 dias** via background loop (configurável em `IGDB_REFRESH_HOURS`)
- ✅ **Página Descobrir** (`/descobrir`) com 4 secções: Para o teu gosto, Nas tuas plataformas, Joias escondidas, Em alta — usa avaliações + jogo favorito + plataformas do utilizador
- ✅ **Picker de jogo favorito** com autocomplete real-time contra o catálogo (`GamePicker` component) — só permite jogos válidos
- ✅ **Bug fix: botão de amizade**: GET `/users/{id}` agora devolve `friendship_status` (self/none/pending_sent/pending_received/accepted) → Profile mostra "Amigos"/"Pedido enviado"/"Aceitar"/"Adicionar"
- ✅ **Bug fix: foto de perfil cached**: helper `cacheBust(url, version)` adiciona `?v=` aos avatares; PATCH /users/me também propaga (`name, picture`) para reviews/guides/help_requests denormalizados
- ✅ **Novo formato de ID**: `U{ano}{LETRA}{4 alfanuméricos}` (ex: `U2026O7I5O`) para novos utilizadores; mostrado como `@U2026O7I5O`
- ✅ **Site totalmente em PT-PT** incluindo **descrições dos jogos** traduzidas via Claude Sonnet 4.5 (Emergent LLM key) — inserção imediata + tradução em background batch
- ✅ Indexes adicionados em `games.genres/platforms/rating/year` para queries rápidas
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
- Real-time chat via WebSocket (atualmente polling 4s — funcional mas com latência)
- Upload de foto via object storage (atualmente URL/base64)
- Steam OAuth (requer API key Steam do utilizador)
- Comunidades — moderação (banir, kick, owner-only edit), ícones de comunidade
- Notificações in-app (novas DMs, pedidos de amizade, respostas)

### P2
- Listas de favoritos do utilizador (homepage seção "Jogos favoritos")
- Sistema de comentários em avaliações + likes
- Páginas dedicadas a categorias (Terror, Ação, etc.)
- Refactor: dividir `server.py` (1561 linhas) em routers (`auth`, `users`, `games`, `reviews`, `guides`, `help`, `friends`, `chat`, `communities`, `admin`)
- Modelos `*PatchIn` para updates parciais reais (atualmente PATCH /reviews exige payload completo)
- Rate-limit em endpoints de mensagens (anti-spam)
- Paginação de mensagens (atualmente limitada a 500 por thread)
- Wishlist contagem na homepage

## Test Credentials
Admin: `admin@gamescout.pt` / `admin123` (10000 pts → Apreciador de Obras)
x `*.emergentagent.com` + frontend usa `window.location.origin` (resolve cross-origin entre URLs preview)

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
