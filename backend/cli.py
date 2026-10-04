from .context import get_static_context


def ai():
    from .ai_client import main as ai_main

    ai_main()


def ai_context():
    context = get_static_context()

    print("Linux AI Context")
    print("----------------")

    for key, value in context.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    ai()
