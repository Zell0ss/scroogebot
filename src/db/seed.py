"""Seed baskets and assets from config/config.yaml. Idempotent."""
import asyncio
from src.config import app_config
from src.db.base import async_session_factory, engine
from src.db.models import Asset, Basket, BasketAsset
from src.utils.text import normalize_basket_name
from sqlalchemy import select


async def seed() -> None:
    async with async_session_factory() as session:
        for basket_cfg in app_config["baskets"]:
            result = await session.execute(
                select(Basket).where(Basket.name_normalized == normalize_basket_name(basket_cfg["name"]))
            )
            basket = result.scalar_one_or_none()
            if not basket:
                basket = Basket(
                    name=basket_cfg["name"],
                    name_normalized=normalize_basket_name(basket_cfg["name"]),
                    strategy=basket_cfg["strategy"],
                    risk_profile=basket_cfg.get("risk_profile", "moderate"),
                    cash=basket_cfg.get("cash", 0),
                    broker=basket_cfg.get("broker", "paper"),
                    stop_loss_pct=basket_cfg.get("stop_loss_pct"),
                )
                session.add(basket)
                await session.flush()
                print(f"Created basket: {basket.name}")
            else:
                basket.strategy = basket_cfg["strategy"]
                basket.broker = basket_cfg.get("broker", "paper")
                basket.stop_loss_pct = basket_cfg.get("stop_loss_pct")

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
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
