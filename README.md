# ghostfolio-skill

A [Claude Code](https://claude.ai/code) skill that lets Claude query and operate a self-hosted [Ghostfolio](https://ghostfol.io) portfolio tracker via natural language.

## Requirements

- Python 3.8+
- A running [Ghostfolio](https://github.com/ghostfolio/ghostfolio) instance

## Installation

```bash
npx skills add https://github.com/jesuspb2/ghostfolio-skill
```

Then configure credentials:

```bash
cp ~/.agents/skills/ghostfolio-skill/scripts/.env.example ~/.agents/skills/ghostfolio-skill/scripts/.env
```

Edit `.env`:

```env
GHOSTFOLIO_URL=http://your-ghostfolio-host:3333
ACCESS_TOKEN=your_anonymous_access_token_here
```

## License

MIT
