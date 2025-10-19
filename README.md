# Semantic News

## Setup

1. Copy the example environment file and adjust values as needed:

```bash
cp .env.example .env
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run database migrations and start the development server as usual.

### Upgrading existing deployments

If you previously applied the `agenda` app's migrations, the new
`0000_vector_extension` migration only records the already-installed
`vector` PostgreSQL extension. Fake-apply it to keep the migration history
consistent:

```bash
python manage.py migrate agenda 0000_vector_extension --fake
```

## Installing as a dependency

To include Semantic News in another project, reference the Git repository directly in your `pyproject.toml` or `requirements.txt`:

```bash
pip install "semantic-news @ git+https://github.com/onurmatik/semantic-news.git@main"
```

## Agenda utilities

Use the `find_major_events` management command to request suggested agenda entries for a specific day. The command accepts an ISO date and filters out suggestions rated below the configured significance threshold:

```bash
python manage.py find_major_events 2024-06-15
```

Set `--min-significance` (1 = very low, 5 = very high, default = 4) to adjust the cut-off when running the command manually or from cron jobs.
