# Kioxus 核心接口

## Kioxus 类

```python
from main import Kioxus

kioxus = Kioxus(base_dir=".")
kioxus.initialize()
response = kioxus.chat("你好")
```

## LLMClient

```python
from core.llm import LLMClient, LLMMessage, ProviderConfig

client = LLMClient()
client.register_provider(ProviderConfig(
    name="xiaomi",
    api_url="https://...",
    api_key="***",
    model="mimo-v2.5-pro",
))
response = client.generate([LLMMessage(role="user", content="你好")])
```

## MemoryStore

```python
from memory.memory import MemoryStore

store = MemoryStore(base_dir="data/memory")
store.save(entry)
results = store.search("关键词")
```

## ProviderRegistry

```python
from core.provider_registry import get_registry

registry = get_registry()
registry.load_from_config("config/kioxus.json")
registry.list_providers()
```
