# Individual Bot Launch Guide

## Overview
You can now launch bots individually using separate commands instead of running all bots at once through `main.py`.

## Usage

### Option 1: Using Python script directly

```bash
# Launch bot by index
python run_bot.py <bot_index>

# Examples:
python run_bot.py 0      # Launch bot_0
python run_bot.py 1      # Launch bot_1
python run_bot.py 5      # Launch bot_5
```

### Option 2: Using shell scripts (convenience)

```bash
# Launch specific bot
./run_bot_0.sh    # Launch bot_0
./run_bot_1.sh    # Launch bot_1
./run_bot_2.sh    # Launch bot_2
./run_bot_3.sh    # Launch bot_3
./run_bot_4.sh    # Launch bot_4
./run_bot_5.sh    # Launch bot_5
```

### Option 3: Custom config files

```bash
# Specify custom config paths
python run_bot.py 0 config_main.yaml config_bots.yaml
```

## Running Multiple Bots in Parallel

You can launch multiple bots in separate terminal sessions:

### Using tmux (recommended)
```bash
# Terminal 1
tmux new -s bot0
python run_bot.py 0

# Terminal 2 (new tmux session)
tmux new -s bot1
python run_bot.py 1

# Terminal 3
tmux new -s bot3
python run_bot.py 3
```

### Using background processes
```bash
python run_bot.py 0 &
python run_bot.py 1 &
python run_bot.py 3 &
```

### Using nohup (for long-running bots)
```bash
nohup python run_bot.py 0 > bot0.log 2>&1 &
nohup python run_bot.py 1 > bot1.log 2>&1 &
```

## Available Bots (from config_bots.yaml)

| Bot Index | Bot Key | Site | Model | Profile |
|-----------|---------|------|-------|---------|
| 0 | bot_0 | qwen | qwen | karvinoir@gmail.com |
| 1 | bot_1 | qwen | qwen | dsmldlql0@gmail.com |
| 2 | bot_2 | qwen | qwen | alexanderborchun@gmail.com |
| 3 | bot_3 | qwen | qwen | karvinior@gmail.com |
| 4 | bot_4 | qwen | qwen | rxmzge8117@outlook.com |
| 5 | bot_5 | qwen | qwen | dsmldlql@gmail.com |
| 6 | bot_6 | gpt | gpt | janskisheikh042@outlook.com |
| 7 | bot_7 | gpt | gpt | halseycusenza35@outlook.com |
| 8 | bot_8 | gpt | gpt | rxmzge8117@outlook.com |
| 9 | bot_9 | gpt | gpt | kacalbsullo03467p@outlook.com |
| - | bot_3_ | claude | claude | leinswdolenfnk4@outlook.com |
| - | bot_4_ | claude | claude | sweetozewdur0ye@outlook.com |
| - | bot_5_ | claude | claude | touchxdimespgq6d4@outlook.com |
| - | bot_6_ | claude | claude | meachjhayamegl@outlook.com |

## Benefits

- **Independent control**: Start/stop bots individually
- **Easier debugging**: Isolate issues to specific bots
- **Resource management**: Run only the bots you need
- **Flexible scheduling**: Launch bots at different times
- **Better logging**: Separate log output per bot

## Notes

- Each bot runs in its own process with isolated browser instance
- VNC monitor is started per bot (for single-bot monitoring)
- Bot configurations are loaded from `config_bots.yaml`
- Main settings (sites, scenarios) are loaded from `config_main.yaml`
