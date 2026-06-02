from vishnu_retrieval.textutil import cosine, sparse_vector, tokenize


def test_tokenize_preserves_devanagari_words():
    assert "विष्णु" in tokenize("श्री विष्णु सहस्रनाम")


def test_sparse_vector_similarity_self_is_positive():
    vec = sparse_vector("विष्णु sahasranama")
    assert cosine(vec, vec) > 0.99

