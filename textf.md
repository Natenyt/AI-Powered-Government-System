Hey i want you to create a precheck function that checks weather the sessions that message belongs to have assigned_department is equal null, if equal null then we shoudl ani api call to our microservice which will reside in this folder@ai and pass the message
in this type

{
"message_uuid": "91b52e2e-4f5d-4bd7-a12e-3b04c99b9f47",
"user": {
"uuid": "c6f0b2c1-55a0-4c92-86e1-89ce64f0c921",
"full_name": "Umarov Javohir",
"telegram_user_id": 556677889,
"email": null
},
"message": {
"text": "Salom, suv hisoblagichim ishlamayapti.",
"sent_at": "2025-02-03T14:22:18Z"
},

}
]
},
"settings": {
"model": "gemini-2.5-pro",
"temperature": 0.2,
"max_tokens": 500


if precheck function returns True, that assigned_department is not null, then we will need another function which we call which will route the message to that assigned department, it does two things, first it will find all the admins  telegram_chat_id that belongs to that assigned_deparment and send the message to their chat_id, and also send the message to the Department dashboard but since we don't have dashboards ready just leave a dummy message ok for now.

and now let's talk about microservice what it does.

message will be sent to microservice though drf api call and the first process it goes through it is injection_detection, you will take the message text and then forward pass it though the injection detector function to find injection, injection detector for stage 1 can be simple ok , later we will upgrade.

So if injection_detector returns True, call api to send emergency notification to System Admin dashboard but since we don't have it you can just leave a dummy message ok, and from that moment the operation in Microservice should be terminated. and everything should be saved to database, so you will have to create one more model inside app ai, called InjectResult. and save the injection_detector results ok, and plus you have to set is_injection column AIResult module, to true or false accordingly. 

But if injection_detector return false, then we have to vectorize the message and send it to the department vector database to find the best candidates, for that we will use qdrant vector database. but to vectorize the message we will use gemini embedding model. so you will have to create a function that takes the message text and returns the vectorized message. and then passes it to vector database function maybe i don't know much how it works but i have qdrant running on docker, so you can use it ok, also i have installed qdrant-client in this project, so you can use it ok. so this function needs to return the best 3 candidates ok. But first our vector database is empty and we have put all the departments name, their description and keywords in side it, so we can do matching ok. but for that you may need to create one time function which which all ask for all the departments name, description and keywords as json file, and then it will embedding with gemini embeding model and saves them to database. 
Ok once we will be done with this stage, the returned candidates with confidince rates we will take them and send them to prompt maker function which will create json prompt, prompt should include the message text, the returned candidates with name , similarity score and description. also mention that these are the result vector function, and in that we should ask for the gemini to confirm this is correct and provide routing confidince, reason for why choosing this department, ok then once we get them, we will save them to database AIResult module, ok we need to save based on the AiResult module column, for example we will save the whole prompt to save prompt column, and also i forgot one thing the gemini also should tell us if this message is complaint, suggestion or inquiry, then we will save that message_type column, routing confidence goes to routing_confidence, suggested_derpartment name get name of the department gemini said is the correct, then based on that name we will find the department from department model and get the id and save it to suggested_department_id column, and you don't have to save anything yet to to these fields corrected_by_operator = models.BooleanField(default=False)  # Auto-route overridden
    operator_uuid = models.UUIDField(null=True, blank=True)
    operator_corrected_department_id = models.IntegerField(null=True, blank=True)
    operator_corrected_department_name = models.CharField(max_length=255, null=True, blank=True)
    explanation = models.TextField(blank=True, null=True)

vector_simialrity score and v vector_top_candidates columns get their result saved to them from vector function

we will also save the raw embedding of the message to message_raw_embedding.

reason goes to reason why gemini choose that department, process_duration_ms for this one we should start a timer when we recieved the api call and untill when we finished, then we save it there. 

ok once all of this done, then we call the message_router function and provide the department id and message_uuid, and then fucntion will put the department_id to Session module, assigned_department column, and begin the routing, it will pull all the admins frist belonging to the department and send the message to their telegram_chat_id , and then aslo to the department dashboard since we don't have it yet you can leave a dummy message. 


you can put the message_router and precheck function inside core_support app, 
















call the precheck function  in telegram telegram_bot.py in line 939 right after await save_message( and based on its result call the api right in @telegram_bot.py as well, please make injection_detector, get_embedding, search_vector_db and analyze_message_with_gemini functions actually make functioning and legit, you can get the GEMINI_API_KEY from @.env file. for embedding you can call the gemini embedding model here is the documentation


<br />

The Gemini API offers text embedding models to generate embeddings for words,
phrases, sentences, and code. These foundational embeddings power advanced NLP
tasks such as semantic search, classification, and clustering, providing more
accurate, context-aware results than keyword-based approaches.

Building Retrieval Augmented Generation (RAG) systems is a common use case for
embeddings. Embeddings play a key role in significantly enhancing model outputs
with improved factual accuracy, coherence, and contextual richness. They
efficiently retrieve relevant information from knowledge bases, represented by
embeddings, which are then passed as additional context in the input prompt to
language models, guiding it to generate more informed and accurate responses.

To learn more about the available embedding model variants, see the [Model
versions](https://ai.google.dev/gemini-api/docs/embeddings#model-versions) section. For higher throughput serving at half the
price, try [Batch API Embedding](https://ai.google.dev/gemini-api/docs/embeddings#batch-embedding).

## Generating embeddings

Use the `embedContent` method to generate text embeddings:  

### Python

    from google import genai

    client = genai.Client()

    result = client.models.embed_content(
            model="gemini-embedding-001",
            contents="What is the meaning of life?")

    print(result.embeddings)

### JavaScript

    import { GoogleGenAI } from "@google/genai";

    async function main() {

        const ai = new GoogleGenAI({});

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-001',
            contents: 'What is the meaning of life?',
        });

        console.log(response.embeddings);
    }

    main();

### Go

    package main

    import (
        "context"
        "encoding/json"
        "fmt"
        "log"

        "google.golang.org/genai"
    )

    func main() {
        ctx := context.Background()
        client, err := genai.NewClient(ctx, nil)
        if err != nil {
            log.Fatal(err)
        }

        contents := []*genai.Content{
            genai.NewContentFromText("What is the meaning of life?", genai.RoleUser),
        }
        result, err := client.Models.EmbedContent(ctx,
            "gemini-embedding-001",
            contents,
            nil,
        )
        if err != nil {
            log.Fatal(err)
        }

        embeddings, err := json.MarshalIndent(result.Embeddings, "", "  ")
        if err != nil {
            log.Fatal(err)
        }
        fmt.Println(string(embeddings))
    }

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{"model": "models/gemini-embedding-001",
         "content": {"parts":[{"text": "What is the meaning of life?"}]}
        }'

You can also generate embeddings for multiple chunks at once by passing them in
as a list of strings.  

### Python

    from google import genai

    client = genai.Client()

    result = client.models.embed_content(
            model="gemini-embedding-001",
            contents= [
                "What is the meaning of life?",
                "What is the purpose of existence?",
                "How do I bake a cake?"
            ])

    for embedding in result.embeddings:
        print(embedding)

### JavaScript

    import { GoogleGenAI } from "@google/genai";

    async function main() {

        const ai = new GoogleGenAI({});

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-001',
            contents: [
                'What is the meaning of life?',
                'What is the purpose of existence?',
                'How do I bake a cake?'
            ],
        });

        console.log(response.embeddings);
    }

    main();

### Go

    package main

    import (
        "context"
        "encoding/json"
        "fmt"
        "log"

        "google.golang.org/genai"
    )

    func main() {
        ctx := context.Background()
        client, err := genai.NewClient(ctx, nil)
        if err != nil {
            log.Fatal(err)
        }

        contents := []*genai.Content{
            genai.NewContentFromText("What is the meaning of life?"),
            genai.NewContentFromText("How does photosynthesis work?"),
            genai.NewContentFromText("Tell me about the history of the internet."),
        }
        result, err := client.Models.EmbedContent(ctx,
            "gemini-embedding-001",
            contents,
            nil,
        )
        if err != nil {
            log.Fatal(err)
        }

        embeddings, err := json.MarshalIndent(result.Embeddings, "", "  ")
        if err != nil {
            log.Fatal(err)
        }
        fmt.Println(string(embeddings))
    }

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{"requests": [{
        "model": "models/gemini-embedding-001",
        "content": {
        "parts":[{
            "text": "What is the meaning of life?"}]}, },
        {
        "model": "models/gemini-embedding-001",
        "content": {
        "parts":[{
            "text": "How much wood would a woodchuck chuck?"}]}, },
        {
        "model": "models/gemini-embedding-001",
        "content": {
        "parts":[{
            "text": "How does the brain work?"}]}, }, ]}' 2> /dev/null | grep -C 5 values
        ```

## Specify task type to improve performance

You can use embeddings for a wide range of tasks from classification to document
search. Specifying the right task type helps optimize the embeddings for the
intended relationships, maximizing accuracy and efficiency. For a complete list
of supported task types, see the [Supported task types](https://ai.google.dev/gemini-api/docs/embeddings#supported-task-types)
table.

The following example shows how you can use
`SEMANTIC_SIMILARITY` to check how similar in meaning strings of texts are.
**Note:** Cosine similarity is a good distance metric because it focuses on direction rather than magnitude, which more accurately reflects conceptual closeness. Values range from -1 (opposite) to 1 (greatest similarity).  

### Python

    from google import genai
    from google.genai import types
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity

    client = genai.Client()

    texts = [
        "What is the meaning of life?",
        "What is the purpose of existence?",
        "How do I bake a cake?"]

    result = [
        np.array(e.values) for e in client.models.embed_content(
            model="gemini-embedding-001",
            contents=texts,
            config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY")).embeddings
    ]

    # Calculate cosine similarity. Higher scores = greater semantic similarity.

    embeddings_matrix = np.array(result)
    similarity_matrix = cosine_similarity(embeddings_matrix)

    for i, text1 in enumerate(texts):
        for j in range(i + 1, len(texts)):
            text2 = texts[j]
            similarity = similarity_matrix[i, j]
            print(f"Similarity between '{text1}' and '{text2}': {similarity:.4f}")

### JavaScript

    import { GoogleGenAI } from "@google/genai";
    import * as cosineSimilarity from "compute-cosine-similarity";

    async function main() {
        const ai = new GoogleGenAI({});

        const texts = [
            "What is the meaning of life?",
            "What is the purpose of existence?",
            "How do I bake a cake?",
        ];

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-001',
            contents: texts,
            taskType: 'SEMANTIC_SIMILARITY'
        });

        const embeddings = response.embeddings.map(e => e.values);

        for (let i = 0; i < texts.length; i++) {
            for (let j = i + 1; j < texts.length; j++) {
                const text1 = texts[i];
                const text2 = texts[j];
                const similarity = cosineSimilarity(embeddings[i], embeddings[j]);
                console.log(`Similarity between '${text1}' and '${text2}': ${similarity.toFixed(4)}`);
            }
        }
    }

    main();

### Go

    package main

    import (
        "context"
        "fmt"
        "log"
        "math"

        "google.golang.org/genai"
    )

    // cosineSimilarity calculates the similarity between two vectors.
    func cosineSimilarity(a, b []float32) (float64, error) {
        if len(a) != len(b) {
            return 0, fmt.Errorf("vectors must have the same length")
        }

        var dotProduct, aMagnitude, bMagnitude float64
        for i := 0; i < len(a); i++ {
            dotProduct += float64(a[i] * b[i])
            aMagnitude += float64(a[i] * a[i])
            bMagnitude += float64(b[i] * b[i])
        }

        if aMagnitude == 0 || bMagnitude == 0 {
            return 0, nil
        }

        return dotProduct / (math.Sqrt(aMagnitude) * math.Sqrt(bMagnitude)), nil
    }

    func main() {
        ctx := context.Background()
        client, _ := genai.NewClient(ctx, nil)
        defer client.Close()

        texts := []string{
            "What is the meaning of life?",
            "What is the purpose of existence?",
            "How do I bake a cake?",
        }

        var contents []*genai.Content
        for _, text := range texts {
            contents = append(contents, genai.NewContentFromText(text, genai.RoleUser))
        }

        result, _ := client.Models.EmbedContent(ctx,
            "gemini-embedding-001",
            contents,
            &genai.EmbedContentRequest{TaskType: genai.TaskTypeSemanticSimilarity},
        )

        embeddings := result.Embeddings

        for i := 0; i < len(texts); i++ {
            for j := i + 1; j < len(texts); j++ {
                similarity, _ := cosineSimilarity(embeddings[i].Values, embeddings[j].Values)
                fmt.Printf("Similarity between '%s' and '%s': %.4f\n", texts[i], texts[j], similarity)
            }
        }
    }

### REST

    curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
        "contents": [
            {"parts": [{"text": "What is the meaning of life?"}]},
            {"parts": [{"text": "What is the purpose of existence?"}]},
            {"parts": [{"text": "How do I bake a cake?"}]}
        ],
        "embedding_config": {
            "task_type": "SEMANTIC_SIMILARITY"
        }
    }'

The following shows an example output from this code snippet:  

    Similarity between 'What is the meaning of life?' and 'What is the purpose of existence?': 0.9481

    Similarity between 'What is the meaning of life?' and 'How do I bake a cake?': 0.7471

    Similarity between 'What is the purpose of existence?' and 'How do I bake a cake?': 0.7371

### Supported task types

|        Task type         |                                                                                                                    Description                                                                                                                     |                         Examples                          |
|--------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| **SEMANTIC_SIMILARITY**  | Embeddings optimized to assess text similarity.                                                                                                                                                                                                    | Recommendation systems, duplicate detection               |
| **CLASSIFICATION**       | Embeddings optimized to classify texts according to preset labels.                                                                                                                                                                                 | Sentiment analysis, spam detection                        |
| **CLUSTERING**           | Embeddings optimized to cluster texts based on their similarities.                                                                                                                                                                                 | Document organization, market research, anomaly detection |
| **RETRIEVAL_DOCUMENT**   | Embeddings optimized for document search.                                                                                                                                                                                                          | Indexing articles, books, or web pages for search.        |
| **RETRIEVAL_QUERY**      | Embeddings optimized for general search queries. Use `RETRIEVAL_QUERY` for queries; `RETRIEVAL_DOCUMENT` for documents to be retrieved.                                                                                                            | Custom search                                             |
| **CODE_RETRIEVAL_QUERY** | Embeddings optimized for retrieval of code blocks based on natural language queries. Use `CODE_RETRIEVAL_QUERY` for queries; `RETRIEVAL_DOCUMENT` for code blocks to be retrieved.                                                                 | Code suggestions and search                               |
| **QUESTION_ANSWERING**   | Embeddings for questions in a question-answering system, optimized for finding documents that answer the question. Use `QUESTION_ANSWERING` for questions; `RETRIEVAL_DOCUMENT` for documents to be retrieved.                                     | Chatbox                                                   |
| **FACT_VERIFICATION**    | Embeddings for statements that need to be verified, optimized for retrieving documents that contain evidence supporting or refuting the statement. Use `FACT_VERIFICATION` for the target text; `RETRIEVAL_DOCUMENT` for documents to be retrieved | Automated fact-checking systems                           |

## Controlling embedding size

The Gemini embedding model, `gemini-embedding-001`, is trained using the
Matryoshka Representation Learning (MRL) technique which teaches a model to
learn high-dimensional embeddings that have initial segments (or prefixes) which
are also useful, simpler versions of the same data.

Use the `output_dimensionality` parameter to control the size of
the output embedding vector. Selecting a smaller output dimensionality can save
storage space and increase computational efficiency for downstream applications,
while sacrificing little in terms of quality. By default, it outputs a
3072-dimensional embedding, but you can truncate it to a smaller size without
losing quality to save storage space. We recommend using 768, 1536, or 3072
output dimensions.  

### Python

    from google import genai
    from google.genai import types

    client = genai.Client()

    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents="What is the meaning of life?",
        config=types.EmbedContentConfig(output_dimensionality=768)
    )

    [embedding_obj] = result.embeddings
    embedding_length = len(embedding_obj.values)

    print(f"Length of embedding: {embedding_length}")

### JavaScript

    import { GoogleGenAI } from "@google/genai";

    async function main() {
        const ai = new GoogleGenAI({});

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-001',
            content: 'What is the meaning of life?',
            outputDimensionality: 768,
        });

        const embeddingLength = response.embedding.values.length;
        console.log(`Length of embedding: ${embeddingLength}`);
    }

    main();

### Go

    package main

    import (
        "context"
        "fmt"
        "log"

        "google.golang.org/genai"
    )

    func main() {
        ctx := context.Background()
        // The client uses Application Default Credentials.
        // Authenticate with 'gcloud auth application-default login'.
        client, err := genai.NewClient(ctx, nil)
        if err != nil {
            log.Fatal(err)
        }
        defer client.Close()

        contents := []*genai.Content{
            genai.NewContentFromText("What is the meaning of life?", genai.RoleUser),
        }

        result, err := client.Models.EmbedContent(ctx,
            "gemini-embedding-001",
            contents,
            &genai.EmbedContentRequest{OutputDimensionality: 768},
        )
        if err != nil {
            log.Fatal(err)
        }

        embedding := result.Embeddings[0]
        embeddingLength := len(embedding.Values)
        fmt.Printf("Length of embedding: %d\n", embeddingLength)
    }

### REST

    curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent" \
    -H "x-goog-api-key: YOUR_GEMINI_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
        "contents": [
            {"parts": [{"text": "What is the meaning of life?"}]}
        ],
        "embedding_config": {
            "output_dimensionality": 768
        }
    }'

Example output from the code snippet:  

    Length of embedding: 768

## Ensuring quality for smaller dimensions

The 3072 dimension embedding is normalized. Normalized embeddings produce more
accurate semantic similarity by comparing vector direction, not magnitude. For
other dimensions, including 768 and 1536, you need to normalize the embeddings
as follows:  

### Python

    import numpy as np
    from numpy.linalg import norm

    embedding_values_np = np.array(embedding_obj.values)
    normed_embedding = embedding_values_np / np.linalg.norm(embedding_values_np)

    print(f"Normed embedding length: {len(normed_embedding)}")
    print(f"Norm of normed embedding: {np.linalg.norm(normed_embedding):.6f}") # Should be very close to 1

Example output from this code snippet:  

    Normed embedding length: 768
    Norm of normed embedding: 1.000000

The following table shows the MTEB scores, a commonly used benchmark for
embeddings, for different dimensions. Notably, the result shows that performance
is not strictly tied to the size of the embedding dimension, with lower
dimensions achieving scores comparable to their higher dimension counterparts.

| MRL Dimension | MTEB Score |
|---------------|------------|
| 2048          | 68.16      |
| 1536          | 68.17      |
| 768           | 67.99      |
| 512           | 67.55      |
| 256           | 66.19      |
| 128           | 63.31      |

## Use cases

Text embeddings are crucial for a variety of common AI use cases, such as:

- **Retrieval-Augmented Generation (RAG):** Embeddings enhance the quality of generated text by retrieving and incorporating relevant information into the context of a model.
- **Information retrieval:** Search for the most semantically similar text or
  documents given a piece of input text.

  [Document search tutorialtask](https://github.com/google-gemini/cookbook/blob/main/examples/Talk_to_documents_with_embeddings.ipynb)
- **Search reranking**: Prioritize the most relevant items by semantically
  scoring initial results against the query.

  [Search reranking tutorialtask](https://github.com/google-gemini/cookbook/blob/main/examples/Search_reranking_using_embeddings.ipynb)
- **Anomaly detection:** Comparing groups of embeddings can help identify
  hidden trends or outliers.

  [Anomaly detection tutorialbubble_chart](https://github.com/google-gemini/cookbook/blob/main/examples/Anomaly_detection_with_embeddings.ipynb)
- **Classification:** Automatically categorize text based on its content, such
  as sentiment analysis or spam detection

  [Classification tutorialtoken](https://github.com/google-gemini/cookbook/blob/main/examples/Classify_text_with_embeddings.ipynb)
- **Clustering:** Effectively grasp complex relationships by creating clusters
  and visualizations of your embeddings.

  [Clustering visualization tutorialbubble_chart](https://github.com/google-gemini/cookbook/blob/main/examples/clustering_with_embeddings.ipynb)

## Storing embeddings

As you take embeddings to production, it is common to
use **vector databases** to efficiently store, index, and retrieve
high-dimensional embeddings. Google Cloud offers managed data services that
can be used for this purpose including
[BigQuery](https://cloud.google.com/bigquery/docs/introduction),
[AlloyDB](https://cloud.google.com/alloydb/docs/overview), and
[Cloud SQL](https://cloud.google.com/sql/docs/postgres/introduction).

The following tutorials show how to use other third party vector databases
with Gemini Embedding.

- [ChromaDB tutorialsbolt](https://github.com/google-gemini/cookbook/tree/main/examples/chromadb)
- [QDrant tutorialsbolt](https://github.com/google-gemini/cookbook/tree/main/examples/qdrant)
- [Weaviate tutorialsbolt](https://github.com/google-gemini/cookbook/tree/main/examples/weaviate)
- [Pinecone tutorialsbolt](https://github.com/google-gemini/cookbook/blob/main/examples/langchain/Gemini_LangChain_QA_Pinecone_WebLoad.ipynb)

## Model versions

|                                           Property                                            |                                                                                                            Description                                                                                                             |
|-----------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id_cardModel code                                                                             | **Gemini API** `gemini-embedding-001`                                                                                                                                                                                              |
| saveSupported data types                                                                      | **Input** Text **Output** Text embeddings                                                                                                                                                                                          |
| token_autoToken limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/embeddings#token-size)^ | **Input token limit** 2,048 **Output dimension size** Flexible, supports: 128 - 3072, Recommended: 768, 1536, 3072                                                                                                                 |
| 123Versions                                                                                   | Read the [model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions) for more details. - Stable: `gemini-embedding-001` - Experimental: `gemini-embedding-exp-03-07` (deprecating in Oct of 2025) |
| calendar_monthLatest update                                                                   | June 2025                                                                                                                                                                                                                          |

## Batch embeddings

If latency is not a concern, try using the Gemini Embeddings model with
[Batch API](https://ai.google.dev/gemini-api/docs/batch-api#batch-embedding). This
allows for much higher throughput at 50% of interactive Embedding pricing.
Find examples on how to get started in the [Batch API cookbook](https://github.com/google-gemini/cookbook/blob/main/quickstarts/Batch_mode.ipynb).

## Responsible use notice

Unlike generative AI models that create new content, the Gemini Embedding model
is only intended to transform the format of your input data into a numerical
representation. While Google is responsible for providing an embedding model
that transforms the format of your input data to the numerical-format requested,
users retain full responsibility for the data they input and the resulting
embeddings. By using the Gemini Embedding model you confirm that you have the
necessary rights to any content that you upload. Do not generate content that
infringes on others' intellectual property or privacy rights. Your use of this
service is subject to our [Prohibited Use
Policy](https://policies.google.com/terms/generative-ai/use-policy) and
[Google's Terms of Service](https://ai.google.dev/gemini-api/terms).

## Start building with embeddings

Check out the [embeddings quickstart
notebook](https://github.com/google-gemini/cookbook/blob/main/quickstarts/Embeddings.ipynb)
to explore the model capabilities and learn how to customize and visualize your
embeddings.

## Deprecation notice for legacy models

The following models will be deprecated in October, 2025:
- `embedding-001`
- `embedding-gecko-001`
- `gemini-embedding-exp-03-07` (`gemini-embedding-exp`)



for doing analyses with call gemini 2.5 flash