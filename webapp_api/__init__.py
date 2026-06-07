"""FastAPI-бэкенд для Telegram Mini App Yaride.

Тонкий REST-слой поверх той же yaride.db через app.repo / app.services — без дублирования
бизнес-логики. Авторизация по Telegram initData (HMAC с BOT_TOKEN).
"""
