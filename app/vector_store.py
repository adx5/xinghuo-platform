import json
from collections import Counter
from app.database import SessionLocal, Resource


def get_text_vector(text: str):
    return Counter(list(text))


def cosine_similarity(vec1: Counter, vec2: Counter):
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum([vec1[x] * vec2[x] for x in intersection])
    sum1 = sum([vec1[x] ** 2 for x in vec1.keys()])
    sum2 = sum([vec2[x] ** 2 for x in vec2.keys()])
    denominator = (sum1 ** 0.5) * (sum2 ** 0.5)
    return float(numerator) / denominator if denominator else 0.0


def sync_resources_to_vector_db():
    # 云端环境无需写入本地文件，留空即可
    pass


def search_similar_resources(query_text: str, n_results: int = 10):
    db = SessionLocal()
    try:
        resources = db.query(Resource).all()
        if not resources: return []

        query_vector = get_text_vector(query_text)
        results = []

        for r in resources:
            text_to_match = f"{r.name} {r.industry} {r.region} {r.resource_type} {r.description}"
            db_vector = get_text_vector(text_to_match)
            similarity = cosine_similarity(query_vector, db_vector)

            results.append({
                "id": str(r.id), "name": r.name, "industry": r.industry,
                "region": r.region, "resource_type": r.resource_type,
                "description": r.description, "similarity": similarity
            })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:n_results]
    finally:
        db.close()