# Discord Music Bot

## Overview
A Discord music bot that streams audio from YouTube using yt-dlp and discord.py. Features include queue management, volume control, auto-disconnect, and an interactive dashboard with buttons.

## Project Structure
- `main.py` - Main bot application with all commands and music streaming logic
- `youtube_cookies.txt` - Optional cookies file for YouTube authentication
- `requirements.txt` - Python dependencies

## Setup
1. Set the `DISCORD_TOKEN` environment variable with your Discord bot token
2. Run `python main.py` to start the bot

## Dependencies
- discord.py[voice] - Discord API wrapper with voice support
- yt-dlp - YouTube audio extraction
- PyNaCl - Voice encryption
- ffmpeg - Audio processing (system dependency)

## Features
- `/play` - Play music from YouTube
- `/queue` - View and manage the music queue
- `/help` - Show available commands
- Interactive dashboard with play/pause, skip, stop, and volume controls
- Auto-disconnect when voice channel is empty
- Search and select from multiple YouTube results

## Recent Changes
- 2026-01-05: Initial setup in Replit environment
