"""
Seeds the database with a realistic demo scenario for the hackathon
presentation: 3 farmers across 3 BRICS nations (India, Brazil, South
Africa), each with a plot, several sensor readings, satellite snapshots,
a soil score, and a federation model-update — so the dashboard has real
data to show the moment the judges open it, with zero manual clicking.

Run with:  python seed_demo_data.py
"""
import random
from datetime import datetime, timedelta, timezone

from app.core.database import Base, SessionLocal, engine
from app.models.domain import BRICSNation, Farmer, FederationModelUpdate, Plot
from app.services import satellite_service, soil_score_service
from app.models.domain import SensorReading

Base.metadata.create_all(bind=engine)
db = SessionLocal()

DEMO_FARMERS = [
    {"name": "Anup Mahato", "phone_number": "+91-9000000001", "preferred_language": "bn", "nation": "IN",
     "plot": {"name": "Haldia Paddy Field", "latitude": 22.0667, "longitude": 88.0698, "primary_crop": "rice"}},
    {"name": "Marcos Silva", "phone_number": "+55-9100000002", "preferred_language": "pt", "nation": "BR",
     "plot": {"name": "Cerrado Soy Plot", "latitude": -15.7801, "longitude": -47.9292, "primary_crop": "soybean"}},
    {"name": "Thandiwe Nkosi", "phone_number": "+27-9200000003", "preferred_language": "en", "nation": "ZA",
     "plot": {"name": "KwaZulu Maize Field", "latitude": -29.6006, "longitude": 30.3794, "primary_crop": "maize"}},
]


def run():
    print("Seeding AgriN Twin demo data...")
    for entry in DEMO_FARMERS:
        farmer = Farmer(
            name=entry["name"],
            phone_number=entry["phone_number"],
            preferred_language=entry["preferred_language"],
            nation=BRICSNation(entry["nation"]),
        )
        db.add(farmer)
        db.commit()
        db.refresh(farmer)

        plot = Plot(
            farmer_id=farmer.id,
            name=entry["plot"]["name"],
            latitude=entry["plot"]["latitude"],
            longitude=entry["plot"]["longitude"],
            area_hectares=round(random.uniform(0.5, 3.0), 2),
            primary_crop=entry["plot"]["primary_crop"],
            nation=BRICSNation(entry["nation"]),
            sensor_pod_id=f"POD-{entry['nation']}-{random.randint(1000,9999)}",
        )
        db.add(plot)
        db.commit()
        db.refresh(plot)

        # 10 days of sensor readings, trending toward drier soil to show
        # a realistic alert-worthy trajectory in the demo
        for i in range(10):
            recorded_at = datetime.now(timezone.utc) - timedelta(days=9 - i)
            moisture = max(15.0, 45 - i * 2.5 + random.uniform(-2, 2))
            db.add(
                SensorReading(
                    plot_id=plot.id,
                    soil_moisture_pct=round(moisture, 1),
                    soil_temp_c=round(24 + random.uniform(-1, 3), 1),
                    air_temp_c=round(29 + random.uniform(-2, 4), 1),
                    air_humidity_pct=round(random.uniform(55, 85), 1),
                    soil_conductivity_us_cm=round(random.uniform(200, 800), 1),
                    battery_voltage=round(random.uniform(3.6, 4.2), 2),
                    recorded_at=recorded_at,
                )
            )
        db.commit()

        # a few satellite snapshots across the last 15 days
        for i in range(3):
            when = datetime.now(timezone.utc) - timedelta(days=10 - i * 5)
            satellite_service.fetch_and_store_snapshot(db, plot, when)

        # compute the soil health trajectory score
        soil_score_service.compute_and_store_score(db, plot)

        # a federation model-update for this nation's node
        db.add(
            FederationModelUpdate(
                node_id=f"{entry['nation']}-NODE-1",
                nation=BRICSNation(entry["nation"]),
                model_name="disease-classifier",
                model_version="v0.1",
                weight_delta_uri=f"s3://agrin-federation/{entry['nation'].lower()}/disease-classifier-v0.1-delta.npz",
                training_sample_count=random.randint(800, 5000),
                eval_metric_name="f1_macro",
                eval_metric_value=round(random.uniform(0.72, 0.91), 3),
            )
        )
        db.commit()
        print(f"  seeded {entry['name']} ({entry['nation']}) -> plot {plot.id}")

    print("Done. Start the API with: uvicorn app.main:app --reload")


if __name__ == "__main__":
    run()
