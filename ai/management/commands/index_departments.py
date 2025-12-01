from django.core.management.base import BaseCommand
from departments.models import Department
from ai.logic import get_embedding, qdrant_client
from qdrant_client.models import PointStruct, VectorParams, Distance
import uuid
import time

class Command(BaseCommand):
    help = 'Index all departments into Qdrant vector database'

    def handle(self, *args, **options):
        self.stdout.write("Starting department indexing...")
        
        # Ensure collection exists
        try:
            qdrant_client.get_collection("departments")
        except Exception:
            self.stdout.write("Collection 'departments' not found. Creating it...")
            qdrant_client.create_collection(
                collection_name="departments",
                vectors_config=VectorParams(size=768, distance=Distance.COSINE)
            )

        departments = Department.objects.filter(is_active=True, is_deleted=False)
        # Fetch existing IDs to skip re-indexing
        existing_ids = set()
        try:
            offset = None
            while True:
                points_batch, offset = qdrant_client.scroll(
                    collection_name="departments",
                    limit=100,
                    offset=offset,
                    with_payload=False,
                    with_vectors=False
                )
                existing_ids.update(p.id for p in points_batch)
                if offset is None:
                    break
            self.stdout.write(f"Found {len(existing_ids)} existing points.")
        except Exception:
            self.stdout.write("Collection might not exist or empty.")
        # 1. Check if we should clear (default: no, unless specified)
        # For this session, let's assume we want to clear ONLY if we haven't already started a successful run, 
        # but since we crashed, we want to RESUME.
        # So I will comment out the recreation part and enable skip logic.
        
        # Ensure collection exists
        try:
            qdrant_client.get_collection("departments")
        except Exception:
            qdrant_client.create_collection(
                collection_name="departments",
                vectors_config=VectorParams(size=768, distance=Distance.COSINE)
            )

        # Get existing points to skip
        existing_points = set()
        offset = 0
        limit = 100
        while True:
            res = qdrant_client.scroll(
                collection_name="departments",
                limit=limit,
                offset=offset,
                with_payload=False,
                with_vectors=False
            )
            points_batch = res[0]
            if not points_batch:
                break
            for p in points_batch:
                existing_points.add(p.id)
            offset = res[1]
            if offset is None:
                break
        
        self.stdout.write(f"Found {len(existing_points)} existing points. Resuming...")

        departments = Department.objects.all()
        points = []
        
        self.stdout.write(f"Found {departments.count()} departments. Indexing...")

        for dept in departments:
            # Index for each language: uz, ru
            for lang in ['uz', 'ru']:
                name = getattr(dept, f"name_{lang}", "")
                description = getattr(dept, f"description_{lang}", "")
                keywords = getattr(dept, f"keywords_{lang}", "")
                
                # Skip if empty
                if not name and not description:
                    # self.stdout.write(f"Skipping department {dept.id} ({lang}) - empty content.")
                    continue

                # Create Point ID
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{dept.id}_{lang}"))
                
                if point_id in existing_points:
                    # self.stdout.write(f"Skipping {name} ({lang}) - already indexed.")
                    continue

                text_to_embed = f"{name}. {description}"
                if keywords:
                    text_to_embed += f" Keywords: {keywords}"
                
                # Generate embedding with retry
                embedding = None
                retries = 3
                for attempt in range(retries):
                    try:
                        embedding = get_embedding(text_to_embed)
                        if embedding and len(embedding) == 768:
                             break
                    except Exception as e:
                        if "429" in str(e):
                            self.stdout.write(self.style.WARNING(f"Rate limit hit. Waiting 10s... (Attempt {attempt+1}/{retries})"))
                            time.sleep(10)
                        else:
                            self.stdout.write(self.style.ERROR(f"Error embedding {name} ({lang}): {e}"))
                            break
                    time.sleep(2) # Standard rate limit wait

                if not embedding or len(embedding) != 768:
                     self.stdout.write(self.style.ERROR(f"Failed to get embedding for {name} ({lang})"))
                     continue

                points.append(PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "dept_id": dept.id,
                        "name": name,
                        "description": description,
                        "keywords": keywords,
                        "lang": lang
                    }
                ))
                self.stdout.write(f"Prepared embedding for {name} ({lang})")

        if points:
            qdrant_client.upsert(
                collection_name="departments",
                points=points
            )
            self.stdout.write(self.style.SUCCESS(f"Successfully indexed {len(points)} points."))
        else:
            self.stdout.write("No departments found to index.")
