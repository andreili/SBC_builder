
class Defconfig:
    def __init__(self, name):
        self.name = name

    def save(self, dir):
        print(f"Saving defconfigs for {self.name} to {dir}")
