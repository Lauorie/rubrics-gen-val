"""One-shot check that Milvus Lite works on this machine."""
from pymilvus import MilvusClient

def main() -> None:
    client = MilvusClient("outputs/_smoke.db")
    client.create_collection(collection_name="smoke", dimension=4, metric_type="COSINE", auto_id=False)
    client.insert("smoke", [
        {"id": 0, "vector": [0.1, 0.2, 0.3, 0.4], "text": "a", "doc": "d1"},
        {"id": 1, "vector": [0.9, 0.8, 0.7, 0.6], "text": "b", "doc": "d2"},
    ])
    res = client.search("smoke", data=[[0.1, 0.2, 0.3, 0.4]], limit=2, output_fields=["text", "doc"])
    print("OK", [(h["id"], h["entity"]["text"]) for h in res[0]])

if __name__ == "__main__":
    main()
