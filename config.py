# Простой загрузчик настроек из .env и .env.local
_settings = {}


def _load_env(filename):
    """Читает файл вида KEY=VALUE и кладёт значения в настройки."""
    try:
        file = open(filename, encoding="utf-8")
    except FileNotFoundError:
        return
    with file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            _settings[key.strip()] = value.strip()


# Сначала несекретные настройки, затем секреты (могут перезаписать)
_load_env(".env")
_load_env(".env.local")


def get(key, default=None):
    return _settings.get(key, default)
