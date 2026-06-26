# Игровой сервер: Flask + SQLAlchemy (sqlite).
# Хранит игроков и монетку, отдаёт состояние боту и игровому окну.
import random
import time

from flask import Flask, jsonify, request, render_template
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

import config

CELL_SIZE = int(config.get("CELL_SIZE", 32))
GRID_COLS = int(config.get("GRID_COLS", 20))
GRID_ROWS = int(config.get("GRID_ROWS", 15))
DB_PATH = config.get("DATABASE_PATH", "game.db")

# Соответствие направления и смещения по клеткам
DELTAS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

app = Flask(__name__)
Base = declarative_base()
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
Session = sessionmaker(bind=engine)


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)  # Telegram-никнейм
    cell_x = Column(Integer)  # позиция кота на клеточном поле
    cell_y = Column(Integer)
    map_x = Column(Integer)  # позиция игрока на карте (пиксели)
    map_y = Column(Integer)
    facing = Column(String, default="down")  # направление взгляда
    joined_at = Column(Float)  # время добавления в игру
    coins = Column(Integer, default=0)  # количество собранных монет


class Coin(Base):
    __tablename__ = "coin"

    id = Column(Integer, primary_key=True)
    cell_x = Column(Integer)
    cell_y = Column(Integer)


Base.metadata.create_all(engine)


def free_cells(session, extra_occupied=()):
    """Список свободных клеток (без котов и переданных дополнительных)."""
    occupied = {(p.cell_x, p.cell_y) for p in session.query(Player).all()}
    occupied.update(extra_occupied)
    return [(x, y) for x in range(GRID_COLS) for y in range(GRID_ROWS)
            if (x, y) not in occupied]


def move_coin(session):
    """Переносит монетку на случайную свободную клетку."""
    coin = session.query(Coin).first()
    if coin is None:
        coin = Coin()
        session.add(coin)
    cells = free_cells(session)
    coin.cell_x, coin.cell_y = random.choice(cells) if cells else (0, 0)
    return coin


def ensure_coin():
    """При старте сервера гарантирует наличие монетки на поле."""
    session = Session()
    try:
        if session.query(Coin).first() is None:
            move_coin(session)
            session.commit()
    finally:
        session.close()


def player_to_dict(player):
    return {
        "name": player.name,
        "cell_x": player.cell_x,
        "cell_y": player.cell_y,
        "map_x": player.map_x,
        "map_y": player.map_y,
        "facing": player.facing,
        "coins": player.coins,
    }


# --- Маршрут 1: API для бота и игрового окна ---

@app.post("/api/join")
def api_join():
    """Создаёт игрока (если ещё нет) и его запись в базе данных."""
    name = (request.json or {}).get("name")
    if not name:
        return jsonify({"error": "name required"}), 400

    session = Session()
    try:
        player = session.query(Player).filter_by(name=name).first()
        if player is None:
            coin = session.query(Coin).first()
            avoid = [(coin.cell_x, coin.cell_y)] if coin else []
            cells = free_cells(session, avoid)
            cell_x, cell_y = random.choice(cells) if cells else (0, 0)
            player = Player(
                name=name,
                cell_x=cell_x, cell_y=cell_y,
                map_x=cell_x * CELL_SIZE, map_y=cell_y * CELL_SIZE,
                facing="down",
                joined_at=time.time(),
                coins=0,
            )
            session.add(player)
            session.commit()
        return jsonify(player_to_dict(player))
    finally:
        session.close()


@app.post("/api/move")
def api_move():
    """Двигает кота игрока на соседнюю клетку и собирает монетку."""
    data = request.json or {}
    name = data.get("name")
    direction = data.get("direction")
    if direction not in DELTAS:
        return jsonify({"error": "bad direction"}), 400

    session = Session()
    try:
        player = session.query(Player).filter_by(name=name).first()
        if player is None:
            return jsonify({"error": "join first"}), 404

        dx, dy = DELTAS[direction]
        player.cell_x = max(0, min(GRID_COLS - 1, player.cell_x + dx))
        player.cell_y = max(0, min(GRID_ROWS - 1, player.cell_y + dy))
        player.map_x = player.cell_x * CELL_SIZE
        player.map_y = player.cell_y * CELL_SIZE
        player.facing = direction

        # Подбор монетки
        coin = session.query(Coin).first()
        player_cell = (player.cell_x, player.cell_y)
        if coin and (coin.cell_x, coin.cell_y) == player_cell:
            player.coins += 1
            move_coin(session)

        session.commit()
        return jsonify(player_to_dict(player))
    finally:
        session.close()


@app.get("/api/state")
def api_state():
    """Полное состояние игры для отрисовки в окне pgzero."""
    session = Session()
    try:
        players = [player_to_dict(p) for p in session.query(Player).all()]
        coin = session.query(Coin).first()
        coin_data = None
        if coin:
            coin_data = {"cell_x": coin.cell_x, "cell_y": coin.cell_y}
        return jsonify({
            "players": players,
            "coin": coin_data,
            "cell_size": CELL_SIZE,
            "grid_cols": GRID_COLS,
            "grid_rows": GRID_ROWS,
        })
    finally:
        session.close()


# --- Маршрут 2: таблица лидеров ---

@app.get("/leaderboard")
def leaderboard():
    session = Session()
    try:
        players = session.query(Player).order_by(Player.coins.desc()).all()
        now = time.time()
        rows = []
        for p in players:
            seconds = int(now - p.joined_at)
            duration = f"{seconds // 60:02d}:{seconds % 60:02d}"
            rows.append(
                {"name": p.name, "duration": duration, "score": p.coins}
            )
        return render_template("leaderboard.html", rows=rows)
    finally:
        session.close()


# --- Маршрут 3: страница об опыте в ИИ ---

@app.get("/")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    ensure_coin()
    host = config.get("SERVER_HOST", "127.0.0.1")
    port = int(config.get("SERVER_PORT", 8000))
    # Однопоточный режим — запросы обрабатываются по одному, без гонок за БД
    app.run(host=host, port=port, threaded=False)
