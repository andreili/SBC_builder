class Logger:
    def error(msg):
        print(f"[❌] {msg}")
        exit(1)

    def build(msg):
        print(f"[🔨] {msg}")

    def download(msg):
        print(f"[🌍] {msg}")

    def git(msg):
        print(f"[📦] {msg}")
