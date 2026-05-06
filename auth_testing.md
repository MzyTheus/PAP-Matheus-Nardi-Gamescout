# GameScout Auth Testing Playbook

## Auth Flows
1. **JWT Email/Password**: `/api/auth/register`, `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`. Sets `access_token` + `refresh_token` httpOnly cookies.
2. **Emergent Google**: Frontend redirects to `https://auth.emergentagent.com/?redirect={origin}/auth/callback`. Returns with `#session_id={id}` in URL fragment. Frontend POSTs `session_id` to `/api/auth/google/session`. Backend exchanges with Emergent, sets `session_token` httpOnly cookie (7d).

## get_current_user
Backend checks (in order): `session_token` cookie → `access_token` cookie → Authorization Bearer header.

## Test Users
See `/app/memory/test_credentials.md`.

## Sample curl
```
curl -c /tmp/cookies.txt -X POST $BACKEND/api/auth/login -H "Content-Type: application/json" -d '{"email":"admin@gamescout.pt","password":"admin123"}'
curl -b /tmp/cookies.txt $BACKEND/api/auth/me
```

## MongoDB sanity
```
mongosh test_database --eval 'db.users.findOne({role:"admin"}, {password_hash:1, user_id:1, email:1})'
```
Verify bcrypt hash starts with `$2b$`.
