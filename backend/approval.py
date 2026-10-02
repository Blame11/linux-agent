def request_approval(command, classification):
    print()
    print(f"Command: {command}")
    print(f"Risk: {classification}")

    if classification == "DANGEROUS":
        print("WARNING: This command may make destructive system changes.")

    answer = input("Execute this command? [y/N]: ").strip().lower()

    return answer in ("y", "yes")