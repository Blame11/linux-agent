import os
import sys


LOG_LIMIT_BYTES = 1024 * 1024
TRUNCATION_MARKER = b"\n...[output log truncated at 1 MiB]\n"


def collect_output(fd, log_path):
    remaining = LOG_LIMIT_BYTES - len(TRUNCATION_MARKER)
    truncated = False

    with os.fdopen(fd, "rb", closefd=True) as source:
        with open(log_path, "wb") as output:
            while True:
                chunk = source.read(65536)
                if not chunk:
                    break

                saved = chunk[:remaining]
                if saved:
                    output.write(saved)
                    output.flush()
                    remaining -= len(saved)

                if len(chunk) > len(saved) and not truncated:
                    output.write(TRUNCATION_MARKER)
                    output.flush()
                    truncated = True


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: output_collector.py FD LOG_PATH")

    collect_output(int(sys.argv[1]), sys.argv[2])


if __name__ == "__main__":
    main()
