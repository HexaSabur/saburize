# saburize

saburize is a local FastAPI dashboard that turns a website brief and a set of design rules into static site files. You can follow a generation job from the model request through file creation and an attempted Surge deployment. The dashboard uses Turkish labels.

## Run locally

From the repository root, with Python 3.10+ installed, run these commands in a Python virtual environment:

```shell
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 in your browser. Use a Gemini or Groq API key and a model available to your account. The backend also reads `GEMINI_API_KEY` from the environment. Connections saved through the dashboard store credentials in plain text in `baglantilar.json`. Keep that file private and run the dashboard on localhost.

## Try a brief

For example, ask for a violin practice timer with start, pause and reset buttons. In the rules field, request HTML, CSS and vanilla JavaScript. When you start the job, the backend sends the brief and rules to the selected provider. It reports progress and token counts through Server-Sent Events and writes the generated files to `Musteri_Projesi/`.

Every generation run then attempts to publish the contents of that directory to Surge. Publishing requires Node.js with npx and valid Surge credentials. The output directory is shared across runs, so matching filenames are overwritten and older files can remain. Use a clean output directory before starting a project intended for publication. Open the resulting URL to verify a deployment.

## Inspect a run

| Endpoint | Purpose |
| --- | --- |
| `POST /calistir` | Start a job with a brief and rules |
| `GET /durum/{job_id}` | Stream progress, token counts and generated filenames |
| `GET /gecmis` | List up to 20 recent jobs held in memory |
| `GET /dosya/{job_id}/{dosya_adi}` | Retrieve a generated file from the running server |

The backend and generation workflow are in `app.py`. The browser interface is in `dashboard/index.html`. See [the architecture plan](MIMARI_PLAN.md) for the original design.
