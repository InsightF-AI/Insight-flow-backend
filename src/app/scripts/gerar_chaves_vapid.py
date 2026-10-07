from app.integrations.web_push.vapid import ChaveVapid


def main() -> None:
    chave = ChaveVapid.gerar()
    print(f"WEB_PUSH_VAPID_CHAVE_PRIVADA={chave.privada_base64url()}")
    print(f"Chave publica: {chave.publica_base64url()}")


if __name__ == "__main__":
    main()
