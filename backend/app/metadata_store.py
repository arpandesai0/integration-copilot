import threading
from uuid import uuid4

from sqlalchemy import delete, insert, select

from app.chat_store import get_chat_store


class MongoMetadataStore:
    """Durable MongoDB snapshots for the relational application state.

    SQLite remains the process-local query cache. Each snapshot is written as a
    new generation and made visible atomically by switching the manifest.
    """

    def __init__(self, database):
        self.database = database
        self.manifest = database.app_metadata_manifest

    def current_generation(self):
        record = self.manifest.find_one({"_id": "current"})
        return record.get("generation") if record else None

    def snapshot(self, engine, metadata):
        generation = str(uuid4())
        table_names = []
        with engine.connect() as connection:
            for table in metadata.sorted_tables:
                table_names.append(table.name)
                records = []
                for position, row in enumerate(connection.execute(select(table)).mappings()):
                    records.append(
                        {
                            "_id": f"{generation}:{position}",
                            "generation": generation,
                            "data": dict(row),
                        }
                    )
                if records:
                    self.database[f"app_metadata_{table.name}"].insert_many(records)

        self.manifest.replace_one(
            {"_id": "current"},
            {"_id": "current", "generation": generation, "tables": table_names},
            upsert=True,
        )
        for table_name in table_names:
            self.database[f"app_metadata_{table_name}"].delete_many(
                {"generation": {"$ne": generation}}
            )
        return generation

    def restore(self, engine, metadata):
        generation = self.current_generation()
        if not generation:
            return False

        with engine.begin() as connection:
            for table in reversed(metadata.sorted_tables):
                connection.execute(delete(table))
            for table in metadata.sorted_tables:
                documents = list(
                    self.database[f"app_metadata_{table.name}"].find(
                        {"generation": generation}, {"_id": 0, "generation": 0}
                    )
                )
                rows = [document["data"] for document in documents]
                if table.name == "threads":
                    rows.sort(key=lambda row: row.get("parent_thread_id") is not None)
                if rows:
                    connection.execute(insert(table), rows)
        return True


_store = None
_store_lock = threading.Lock()
_snapshot_lock = threading.Lock()
_timer = None
_pending = None


def get_metadata_store():
    global _store
    chat_store = get_chat_store()
    if not chat_store:
        return None
    with _store_lock:
        if _store is None:
            _store = MongoMetadataStore(chat_store.database)
    return _store


def _run_snapshot():
    global _timer, _pending
    with _snapshot_lock:
        pending = _pending
        _pending = None
        _timer = None
    if pending:
        engine, metadata = pending
        get_metadata_store().snapshot(engine, metadata)


def schedule_metadata_snapshot(engine, metadata, delay=0.25):
    global _timer, _pending
    if not get_metadata_store():
        return
    with _snapshot_lock:
        _pending = (engine, metadata)
        if _timer:
            _timer.cancel()
        _timer = threading.Timer(delay, _run_snapshot)
        _timer.daemon = True
        _timer.start()


def flush_metadata_snapshot():
    global _timer
    with _snapshot_lock:
        if _timer:
            _timer.cancel()
    _run_snapshot()
