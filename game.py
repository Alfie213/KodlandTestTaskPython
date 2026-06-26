# Игровое окно на pgzero. Получает состояние с сервера и рисует котов и монетку.
# Запуск: python game.py
import requests

import config

CELL_SIZE = int(config.get("CELL_SIZE", 32))
GRID_COLS = int(config.get("GRID_COLS", 20))
GRID_ROWS = int(config.get("GRID_ROWS", 15))
SERVER_URL = config.get("SERVER_URL", "http://127.0.0.1:8000")

# Размер окна pgzero (читается библиотекой)
WIDTH = GRID_COLS * CELL_SIZE
HEIGHT = GRID_ROWS * CELL_SIZE

cats = {} # имя игрока -> объект Cat
coin_cell = [0, 0] # клетка с монеткой

# Последнее состояние с сервера и таймер опроса
_server_state = {}
_poll_timer = 0.0
POLL_INTERVAL = 0.2 # как часто опрашивать сервер, секунд


class Cat:
    """Кот: отрисовка, плавное перемещение по клеткам и спрайтовая анимация."""

    FRAMES = 4 # кадров в анимации ходьбы
    SPEED = 60 # пикселей в секунду (медленно)
    ANIM_INTERVAL = 0.15 # секунд между сменой кадров

    def __init__(self, name, cell_x, cell_y, facing):
        self.name = name
        self.cell_x = cell_x
        self.cell_y = cell_y
        self.facing = facing
        # Текущая позиция в пикселях (левый верхний угол клетки)
        self.x = cell_x * CELL_SIZE
        self.y = cell_y * CELL_SIZE
        self.target_x = self.x
        self.target_y = self.y
        self.moving = False
        self.frame = 0
        self.timer = 0.0

    def move_to(self, cell_x, cell_y, facing):
        """Задать соседнюю клетку целью — кот плавно поедет туда."""
        self.cell_x = cell_x
        self.cell_y = cell_y
        self.facing = facing
        self.target_x = cell_x * CELL_SIZE
        self.target_y = cell_y * CELL_SIZE
        self.moving = True

    def update(self, dt):
        if self.moving:
            self._step_toward_target(dt)
            self._animate(dt)
        else:
            self.frame = 0 # стоит — кадр покоя

    def _step_toward_target(self, dt):
        step = self.SPEED * dt
        if self.x < self.target_x:
            self.x = min(self.x + step, self.target_x)
        elif self.x > self.target_x:
            self.x = max(self.x - step, self.target_x)
        if self.y < self.target_y:
            self.y = min(self.y + step, self.target_y)
        elif self.y > self.target_y:
            self.y = max(self.y - step, self.target_y)
        if self.x == self.target_x and self.y == self.target_y:
            self.moving = False

    def _animate(self, dt):
        self.timer += dt
        if self.timer >= self.ANIM_INTERVAL:
            self.timer -= self.ANIM_INTERVAL
            self.frame = (self.frame + 1) % self.FRAMES

    def _image_name(self):
        # У ходьбы 4 кадра, у покоя — один (кадр 0)
        if self.moving:
            return f"cat_walk_{self.facing}_{self.frame}"
        return f"cat_wait_{self.facing}_0"

    def draw(self):
        screen.blit(self._image_name(), (self.x, self.y))
        # Никнейм владельца над котом
        screen.draw.text(
            self.name,
            midbottom=(self.x + CELL_SIZE / 2, self.y - 2),
            color="white", fontsize=16, owidth=1, ocolor="black",
        )


def _poll_server():
    """Забирает состояние игры с сервера (локальный запрос — быстрый)."""
    global _server_state
    try:
        response = requests.get(f"{SERVER_URL}/api/state", timeout=1)
        _server_state = response.json()
    except requests.RequestException:
        pass


def update(dt):
    global _poll_timer
    # Опрашиваем сервер не каждый кадр, а раз в POLL_INTERVAL секунд
    _poll_timer += dt
    if _poll_timer >= POLL_INTERVAL:
        _poll_timer = 0.0
        _poll_server()

    data = _server_state
    coin = data.get("coin")
    if coin:
        coin_cell[0] = coin["cell_x"]
        coin_cell[1] = coin["cell_y"]

    for p in data.get("players", []):
        name = p["name"]
        if name not in cats:
            cats[name] = Cat(name, p["cell_x"], p["cell_y"], p["facing"])
        else:
            cat = cats[name]
            # Сервер сообщил новую клетку — едем туда
            if (p["cell_x"], p["cell_y"]) != (cat.cell_x, cat.cell_y):
                cat.move_to(p["cell_x"], p["cell_y"], p["facing"])

    for cat in cats.values():
        cat.update(dt)


def _draw_grid():
    for col in range(GRID_COLS + 1):
        x = col * CELL_SIZE
        screen.draw.line((x, 0), (x, HEIGHT), (55, 60, 70))
    for row in range(GRID_ROWS + 1):
        y = row * CELL_SIZE
        screen.draw.line((0, y), (WIDTH, y), (55, 60, 70))


def draw():
    screen.fill((40, 44, 52))
    _draw_grid()
    # Монетка — жёлтый круг в центре клетки
    cx = coin_cell[0] * CELL_SIZE + CELL_SIZE // 2
    cy = coin_cell[1] * CELL_SIZE + CELL_SIZE // 2
    screen.draw.filled_circle((cx, cy), CELL_SIZE // 3, "gold")
    screen.draw.circle((cx, cy), CELL_SIZE // 3, "orange")
    for cat in cats.values():
        cat.draw()


import pgzrun # noqa: E402 (запуск pgzero как обычного скрипта)
pgzrun.go()
