import os
import requests
import time
from datetime import datetime
from flask import Flask, Response, jsonify
from google.transit import gtfs_realtime_pb2
from google.protobuf.json_format import MessageToDict
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

BUS_API_KEY = os.getenv("MTA_BUS_API_KEY")

SUBWAY_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"
BUS_URL = "https://gtfsrt.prod.obanyc.com/tripUpdates"

arrival_cache = {
    "Downtown 6 Arrivals": [],
    "Westbound M34 Arrivals": []
}

def get_bus_feed():
    global arrival_cache
    try:
        response = requests.get(BUS_URL, params={"key": BUS_API_KEY}, timeout=10)
        response.raise_for_status()
        
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        arrival_times = []

        for entity in feed.entity:
            if not entity.HasField("trip_update"):
                continue
            
            trip = entity.trip_update.trip
            if not trip.route_id == "M34":
                continue
            
            stop_time_updates = entity.trip_update.stop_time_update
            # Filter by stop
            for stu in stop_time_updates:
                stop_id = stu.stop_id
                if stop_id == "403359" and stu.HasField("arrival"):
                    arrival = int(stu.arrival.time)
                    now = int(time.time())
                    if arrival > now:
                        arrival_in_minutes = int((arrival - now) / 60)
                        arrival_times.append(arrival_in_minutes)
        arrival_times = sorted(list(arrival_times))
        arrival_cache["Westbound M34 Arrivals"] = arrival_times
        # print("Updated arrivals:", arrival_cache)


    except Exception as e:
        return None, (f"Error parsing MTA bus data: {str(e)}", 500)
#FeedMessage -> Entity -> TripUpdate -> Trip -> NyctTripDescriptor -> Direction

def get_train_feed():
    global arrival_cache
    try:
        response = requests.get(SUBWAY_URL, timeout=10)
        response.raise_for_status()
        
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        arrival_times = []

        for entity in feed.entity:
            # Check if the entity has a trip update
            if not entity.HasField("trip_update"):
                continue
            
            stop_time_updates = entity.trip_update.stop_time_update
            # Filter by train route
            for stu in stop_time_updates:
                # print(stu)
                stop_id = stu.stop_id
                if stop_id == "632S" and stu.HasField("arrival"):
                    arrival = int(stu.arrival.time)
                    now = int(time.time())
                    if arrival > now:
                        arrival_in_minutes = int((arrival - now) / 60)
                        arrival_times.append(arrival_in_minutes)
        arrival_times = sorted(list(arrival_times))
        arrival_cache["Downtown 6 Arrivals"] = arrival_times
        print("Updated arrivals:", arrival_cache)
    except Exception as e:
        return None, (f"Error parsing MTA train data: {str(e)}", 500)
   
    
@app.route("/downtown_6")
def downtown_6():
    return jsonify(arrival_cache)

@app.route("/m_34")
def m_34():
    return jsonify(arrival_cache)
    


# Setting up scheduler to fetch from cache every 30 seconds
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(
    func=get_train_feed,
    trigger="interval",
    seconds=30,
    next_run_time=datetime.now(),
    max_instances=1, # prevents overlapping fetches
    replace_existing=True
)
scheduler.add_job(
    func=get_bus_feed,
    trigger="interval",
    seconds=30,
    next_run_time=datetime.now(),
    max_instances=1,
    replace_existing=True
)
scheduler.start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)