set -a; source ./.env; set +a

uvicorn foxhole_stockpiles.server:root_app --reload --port 8010
