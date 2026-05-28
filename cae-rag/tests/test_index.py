from cae_rag.index import embed_texts

class _FakeEmb:
    def __init__(self, dim): self.dim = dim; self.calls = []
    def create(self, model, input):
        self.calls.append(list(input))
        class _D:  # mimic openai response
            def __init__(self, v): self.embedding = v
        class _R:
            pass
        r = _R(); r.data = [_D([float(len(t))] * self.dim) for t in input]
        return r

class _FakeClient:
    def __init__(self, dim): self.embeddings = _FakeEmb(dim)

def test_embed_texts_batches_and_orders():
    client = _FakeClient(dim=3)
    texts = [f"t{i}" for i in range(5)]
    vecs = embed_texts(client, texts, model="m", batch_size=2)
    assert len(vecs) == 5
    assert all(len(v) == 3 for v in vecs)
    # 3 batches for 5 items at batch_size 2
    assert len(client.embeddings.calls) == 3
    # order preserved: vec i corresponds to text i (len("t0")==2 -> [2,2,2])
    assert vecs[0] == [2.0, 2.0, 2.0]
