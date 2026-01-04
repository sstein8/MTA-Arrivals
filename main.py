import os
import requests
import time
from datetime import datetime, timedelta
from flask import Flask, Response, jsonify, render_template
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
            if trip.route_id != "M34+":
                continue
            
            stop_time_updates = entity.trip_update.stop_time_update
            # Filter by stop (1st ave westbound)
            for stu in stop_time_updates:
                stop_id = stu.stop_id
                if stop_id == "403359" and stu.HasField("arrival"):
                    arrival = int(stu.arrival.time)
                    now = int(time.time())
                    if arrival > now:
                        arrival_in_minutes = int((arrival - now) / 60)
                        arrival_times.append(arrival_in_minutes)
        arrival_times = sorted(list(arrival_times)[:4])
        arrival_cache["Westbound M34 Arrivals"] = arrival_times

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
        arrival_times = sorted(list(arrival_times)[:4])
        arrival_cache["Downtown 6 Arrivals"] = arrival_times
    except Exception as e:
        return None, (f"Error parsing MTA train data: {str(e)}", 500)

def log_cache():
    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        f"Downtown 6 Arrivals: {arrival_cache['Downtown 6 Arrivals']} | "
        f"M34 Westbound Arrivals: {arrival_cache['Westbound M34 Arrivals']}"
    )


    
@app.route("/times")
def downtown_6():
    return jsonify(arrival_cache)

@app.route("/")
def index():
    return render_template("index.html")
    


# Setting up scheduler to fetch from cache every 30 seconds
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(
    func=get_train_feed,
    trigger="interval",
    seconds=30,
    # next_run_time=datetime.now(),
    # max_instances=1, # prevents overlapping fetches
    # replace_existing=True
)
scheduler.add_job(
    func=get_bus_feed,
    trigger="interval",
    seconds=30,
    # next_run_time=datetime.now(),
    # max_instances=1,
    # replace_existing=True
)
scheduler.add_job(
    log_cache,
    "interval",
    seconds=30,
    next_run_time=datetime.now() + timedelta(seconds=1)
)



if __name__ == "__main__":
    #Start cache on run 
    get_bus_feed()
    get_train_feed()
    scheduler.start()
    app.run(host="0.0.0.0", port=5001, debug=False)