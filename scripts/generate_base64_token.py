import secrets
import base64

def generate_token_base64url(n_bytes=32):
    return base64.urlsafe_b64encode(
        secrets.token_bytes(n_bytes)
    ).rstrip(b"=").decode("ascii")

print(generate_token_base64url())