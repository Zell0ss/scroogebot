"""Seed baskets and assets from config/config.yaml. Idempotent."""
import asyncio
from src.config import app_config
from src.db.base import async_session_factory
from src.db.models import Asset, Basket, BasketAsset
from sqlalchemy import select


async def seed() -> None:
    async with async_session_factory() as session:
        for basket_cfg in app_config["baskets"]:
            result = await session.execute(
                select(Basket).where(Basket.name == basket_cfg["name"])
            )
            basket = result.scalar_one_or_none()
            if not basket:
                basket = Basket(
                    name=basket_cfg["name"],
                    strategy=basket_cfg["strategy"],
                    risk_profile=basket_cfg.get("risk_profile", "moderate"),
                    cash=basket_cfg.get("cash", 0),
                )
                session.add(basket)
                await session.flush()
                print(f"Created basket: {basket.name}")

            for asset_cfg in basket_cfg.get("assets", []):
                result = await session.execute(
                    select(Asset).where(Asset.ticker == asset_cfg["ticker"])
                )
                asset = result.scalar_one_or_none()
                if not asset:
                    asset = Asset(
                        ticker=asset_cfg["ticker"],
                        name=asset_cfg.get("name"),
                        market=asset_cfg.get("market"),
                        currency=asset_cfg.get("currency", "USD"),
                    )
                    session.add(asset)
                    await session.flush()

                result = await session.execute(
                    select(BasketAsset).where(
                        BasketAsset.basket_id == basket.id,
                        BasketAsset.asset_id == asset.id,
                    )
                )
                if not result.scalar_one_or_none():
                    session.add(BasketAsset(basket_id=basket.id, asset_id=asset.id))

        await session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
