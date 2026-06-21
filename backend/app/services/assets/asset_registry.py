from app.domain.assets import AssetId, AssetResolution
from .asset_resolver import AssetResolver


class AssetRegistry:
    _resolvers: dict[str, AssetResolver] = {}

    @classmethod
    def register_resolver(cls, venue: str, resolver: AssetResolver) -> None:
        cls._resolvers[venue] = resolver

    @classmethod
    def get_resolver(cls, venue: str) -> AssetResolver | None:
        return cls._resolvers.get(venue)

    @classmethod
    def list_venues(cls) -> list[str]:
        return list(cls._resolvers.keys())

    @classmethod
    async def resolve(cls, asset_id: AssetId) -> AssetResolution:
        resolver = cls._resolvers.get(asset_id.venue)
        if resolver:
            return await resolver.resolve(asset_id)

        # Fallback if no resolver
        from app.domain.assets import Asset, AssetMetadata
        return AssetResolution(
            asset=Asset(
                asset_id=asset_id,
                decimals=18,  # Default
                metadata=AssetMetadata()
            ),
            source="fallback",
            confidence=0.0
        )

    @classmethod
    async def resolve_many(cls, asset_ids: list[AssetId]) -> list[AssetResolution]:
        import asyncio
        return await asyncio.gather(*(cls.resolve(aid) for aid in asset_ids))
