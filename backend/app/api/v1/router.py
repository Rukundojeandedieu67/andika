"""API version 1 route registration."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, posts, system, users

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
