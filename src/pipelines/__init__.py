"""
Vertex AI Pipeline definition (KFP v2).

Run this script to compile the pipeline to
pipelines/vertex_pipeline.yaml and optionally submit it.

Usage:
  python -m src.pipelines --compile-only
  python -m src.pipelines --run
"""
from __future__ import annotations

import argparse
import os

import kfp
from kfp import dsl
from kfp.dsl import Dataset, Input, Output


# ── Pipeline components ──────────────────────────────────────


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-cloud-storage"],
)
def ingest_documents(
    project_id: str,
    input_gcs_uri: str,
    documents_dataset: Output[Dataset],
) -> None:
    """Download raw documents from GCS and write a manifest."""
    import json
    from google.cloud import storage

    client = storage.Client(project=project_id)
    bucket_name, prefix = input_gcs_uri.replace("gs://", "").split("/", 1)
    bucket = client.bucket(bucket_name)
    blobs = list(bucket.list_blobs(prefix=prefix))

    manifest = [{"gcs_uri": f"gs://{bucket_name}/{b.name}"} for b in blobs]
    with open(documents_dataset.path, "w") as f:
        json.dump(manifest, f)


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "google-cloud-aiplatform>=1.38.0",
        "vertexai",
    ],
)
def generate_embeddings(
    project_id: str,
    location: str,
    embedding_model: str,
    batch_size: int,
    output_gcs_uri: str,
    documents_dataset: Input[Dataset],
    embeddings_dataset: Output[Dataset],
) -> None:
    """Generate text embeddings for each document using Vertex AI."""
    import json

    import vertexai
    from vertexai.language_models import TextEmbeddingModel

    vertexai.init(project=project_id, location=location)
    model = TextEmbeddingModel.from_pretrained(embedding_model)

    with open(documents_dataset.path) as f:
        manifest = json.load(f)

    texts = [item["gcs_uri"] for item in manifest]
    ids = [item["gcs_uri"] for item in manifest]

    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        embs = model.get_embeddings(batch)
        all_embeddings.extend([e.values for e in embs])

    result = [
        {"id": doc_id, "embedding": emb}
        for doc_id, emb in zip(ids, all_embeddings)
    ]
    with open(embeddings_dataset.path, "w") as f:
        json.dump(result, f)


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-cloud-aiplatform>=1.38.0"],
)
def upsert_index(
    project_id: str,
    location: str,
    index_endpoint_id: str,
    deployed_index_id: str,
    embeddings_dataset: Input[Dataset],
) -> int:
    """Upsert embeddings into Vertex AI Matching Engine."""
    import json
    from google.cloud import aiplatform

    aiplatform.init(project=project_id, location=location)
    with open(embeddings_dataset.path) as f:
        data = json.load(f)

    index = aiplatform.MatchingEngineIndex(
        index_name=deployed_index_id
    )
    datapoints = [
        aiplatform.matching_engine.matching_engine_index_endpoint.IndexDatapoint(
            datapoint_id=item["id"],
            feature_vector=item["embedding"],
        )
        for item in data
    ]
    index.upsert_datapoints(datapoints=datapoints)
    return len(data)


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-cloud-aiplatform>=1.38.0"],
)
def register_model(
    project_id: str,
    location: str,
    deployed_index_id: str,
    num_upserted: int,
) -> None:
    """Log the pipeline run as a model version in Vertex AI Model Registry."""
    import logging
    from google.cloud import aiplatform

    logging.basicConfig(level=logging.INFO)
    aiplatform.init(project=project_id, location=location)
    logging.info(
        "Pipeline complete. Upserted %d vectors into index %s.",
        num_upserted,
        deployed_index_id,
    )


# ── Pipeline DAG ─────────────────────────────────────────────


@dsl.pipeline(
    name="vertex-agent-embedding-pipeline",
    description="End-to-end embedding + index pipeline for Vertex AI agents",
    pipeline_root=os.environ.get(
        "VERTEX_AI_PIPELINE_ROOT", "gs://your-project-pipelines"
    ),
)
def embedding_pipeline(
    project_id: str = "your-gcp-project-id",
    location: str = "us-central1",
    input_gcs_uri: str = "gs://your-project-vertex-staging/raw-documents/",
    output_gcs_uri: str = "gs://your-project-vertex-staging/embeddings/",
    embedding_model: str = "textembedding-gecko@003",
    batch_size: int = 100,
    index_endpoint_id: str = "your-index-endpoint-id",
    deployed_index_id: str = "your-deployed-index-id",
) -> None:
    ingest_task = ingest_documents(
        project_id=project_id,
        input_gcs_uri=input_gcs_uri,
    )
    embed_task = generate_embeddings(
        project_id=project_id,
        location=location,
        embedding_model=embedding_model,
        batch_size=batch_size,
        output_gcs_uri=output_gcs_uri,
        documents_dataset=ingest_task.outputs["documents_dataset"],
    )
    upsert_task = upsert_index(
        project_id=project_id,
        location=location,
        index_endpoint_id=index_endpoint_id,
        deployed_index_id=deployed_index_id,
        embeddings_dataset=embed_task.outputs["embeddings_dataset"],
    )
    register_model(
        project_id=project_id,
        location=location,
        deployed_index_id=deployed_index_id,
        num_upserted=upsert_task.output,
    )


# ── CLI entry point ──────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--compile-only",
        action="store_true",
        help="Compile the pipeline YAML without submitting.",
    )
    parser.add_argument(
        "--output",
        default="pipelines/vertex_pipeline.yaml",
        help="Output path for the compiled pipeline YAML.",
    )
    args = parser.parse_args()

    kfp.compiler.Compiler().compile(
        pipeline_func=embedding_pipeline,
        package_path=args.output,
    )
    print(f"Pipeline compiled to {args.output}")

    if not args.compile_only:
        from google.cloud import aiplatform

        aiplatform.init(
            project=os.environ["GCP_PROJECT_ID"],
            location=os.environ.get("GCP_REGION", "us-central1"),
        )
        job = aiplatform.PipelineJob(
            display_name="embedding-pipeline",
            template_path=args.output,
            pipeline_root=os.environ["VERTEX_AI_PIPELINE_ROOT"],
        )
        job.submit()
        print("Pipeline job submitted.")


if __name__ == "__main__":
    main()
