class Logger:
    def error(msg):
        print(f"[❌] {msg}")
        exit(1)

    def ok_exit(msg):
        print(f"[✅] {msg}")
        exit(0)

    def build(msg):
        print(f"[🔨] {msg}")

    def download(msg):
        print(f"[🌍] {msg}")

    def git(msg):
        print(f"[📦] {msg}")

    def os(msg):
        print(f"[🖥] {msg}")

    def install(msg):
        print(f"[💽] {msg}")
