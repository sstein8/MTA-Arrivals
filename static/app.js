async function refresh() {
    const res = await fetch("/times");
    const data = await res.json();
  
    document.getElementById("six-times").textContent =
      data["Downtown 6 Arrivals"].join(",  ") + " min";
  
    document.getElementById("bus-times").textContent =
      data["Westbound M34 Arrivals"].join(",  ") + " min";
  }
  
  refresh();
  setInterval(refresh, 10000); // UI refresh every 10s
  