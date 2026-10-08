"""Local kernel routing. No UI, app proxy, navigation or account state."""

from .kernel_api import KernelApi
from .router import Router


def build_router(kernel: KernelApi) -> Router:
    router = Router()
    kernel.register(router)
    router.get("/health", kernel.health)
    return router
