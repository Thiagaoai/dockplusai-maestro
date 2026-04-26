from maestro.config import get_settings
from maestro.repositories.store import InMemoryStore
from maestro.repositories.supabase_store import SupabaseStore


def create_store():
    settings = get_settings()
    if settings.storage_backend == "supabase":
        return SupabaseStore(settings)
    return InMemoryStore()


store = create_store()

__all__ = ["InMemoryStore", "SupabaseStore", "create_store", "store"]
