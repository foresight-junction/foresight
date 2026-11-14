set -eu

python -c 'import secrets; print(secrets.token_urlsafe(32))' > /run/uf-verifier-token
chmod 600 /run/uf-verifier-token
read -r UF_VERIFIER_TOKEN < /run/uf-verifier-token
export UF_VERIFIER_TOKEN
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
