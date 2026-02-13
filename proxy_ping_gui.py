import subprocess
import platform
import re
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import ttk

# ---------------- CONFIG ----------------

PROXIES = {
    "Spain": "0.0.0.0",
    "Miami": "0.0.0.0",
    "United Kingdom": "0.0.0.0",
    "Poland": "0.0.0.0",
    "France": "0.0.0.0",
    "New York": "0.0.0.0",
    "Middle East": "0.0.0.0",
    "Brazil": "0.0.0.0",
    "Australia": "0.0.0.0",
    "Philippines": "38.60.245.148",
    "Indonesia": "38.60.179.187",
    "Malaysia": "130.94.69.118",
}

PING_COUNT = 4
REFRESH_INTERVAL = 5


# ----------------------------------------


class PingResult:
    def __init__(self, sent=0, received=0, times=None):
        self.sent = sent
        self.received = received
        self.times = times or []

    @property
    def packet_loss(self):
        if self.sent == 0:
            return 100.0
        return round((1 - self.received / self.sent) * 100, 2)

    @property
    def avg(self):
        return round(statistics.mean(self.times), 2) if self.times else None

    @property
    def minimum(self):
        return min(self.times) if self.times else None

    @property
    def maximum(self):
        return max(self.times) if self.times else None

    @property
    def jitter(self):
        if len(self.times) < 2:
            return 0
        return round(statistics.stdev(self.times), 2)


def run_ping(host: str, count: int = 4) -> PingResult:
    if platform.system().lower() == "windows":
        cmd = ["ping", "-n", str(count), host]
    else:
        cmd = ["ping", "-c", str(count), host]

    process = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    output = process.stdout

    times = re.findall(r"time[=<]?\s*([\d\.]+)ms", output, re.IGNORECASE)
    times = [float(t) for t in times]

    sent_match = re.search(r"Sent = (\d+), Received = (\d+)", output)
    if sent_match:
        sent = int(sent_match.group(1))
        received = int(sent_match.group(2))
    else:
        sent = count
        received = len(times)

    return PingResult(sent, received, times)


class PingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Proxy Monitor")
        self.root.geometry("1000x525")
        self.root.configure(bg="#121212")

        self.style = ttk.Style()
        self.setup_theme()

        self.executor = ThreadPoolExecutor(max_workers=len(PROXIES))
        self.countdown_seconds = 0  # Start at 0 to trigger immediate first update
        self.is_pinging = False  # Flag to prevent countdown during ping operations

        self.create_widgets()
        self.countdown_tick()

    def setup_theme(self):
        self.style.theme_use("default")

        self.style.configure(
            "Treeview",
            background="#1E1E1E",
            foreground="#E0E0E0",
            fieldbackground="#1E1E1E",
            rowheight=30,
            font=("Segoe UI", 10)
        )

        self.style.configure(
            "Treeview.Heading",
            background="#1E1E1E",
            foreground="#BB86FC",
            font=("Segoe UI", 10, "bold")
        )

        self.style.map(
            "Treeview",
            background=[("selected", "#2A2A2A")]
        )

    def create_widgets(self):
        header = tk.Label(
            self.root,
            text="Proxy Ping Monitor",
            bg="#121212",
            fg="#BB86FC",
            font=("Segoe UI", 18, "bold")
        )
        header.pack(pady=15)

        self.timestamp = tk.Label(
            self.root,
            text="Updating...",
            bg="#121212",
            fg="#9E9E9E",
            font=("Segoe UI", 10)
        )
        self.timestamp.pack()

        columns = ("Location", "IP", "Avg", "Min", "Max", "Jitter", "Loss")

        self.tree = ttk.Treeview(
            self.root,
            columns=columns,
            show="headings"
        )

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor="center", width=120)

        self.tree.pack(expand=True, fill="both", padx=20, pady=20)

        for name, ip in PROXIES.items():
            self.tree.insert("", "end", iid=name, values=(
                name, ip, "Loading...", "-", "-", "-", "-"
            ))

    def update_row(self, name, result: PingResult):
        if result.received == 0:
            self.tree.item(name, values=(
                name,
                PROXIES[name],
                "DOWN",
                "-",
                "-",
                "-",
                "100%"
            ))
            self.tree.tag_configure(name, foreground="#CF6679")
            self.tree.item(name, tags=(name,))
            return

        avg = result.avg
        color = "#4CAF50" if avg < 100 else "#FB8C00" if avg < 200 else "#CF6679"

        self.tree.item(name, values=(
            name,
            PROXIES[name],
            f"{avg} ms",
            result.minimum,
            result.maximum,
            result.jitter,
            f"{result.packet_loss}%"
        ))

        self.tree.tag_configure(name, foreground=color)
        self.tree.item(name, tags=(name,))

    def countdown_tick(self):
        """Update display and trigger pings when countdown reaches 0"""
        if self.is_pinging:
            # Don't count down while pinging - just show "Updating..."
            self.timestamp.config(text="Updating...")
        elif self.countdown_seconds > 0:
            # Display countdown
            self.timestamp.config(text=f"Next Update: {self.countdown_seconds}s")
            self.countdown_seconds -= 1
        else:
            # Time to update - run pings
            self.run_pings()

        # Schedule next tick in 1 second
        self.root.after(1000, self.countdown_tick)

    def run_pings(self):
        """Execute ping operations"""
        self.is_pinging = True  # Block countdown from running

        futures = {}
        for name, ip in PROXIES.items():
            futures[name] = self.executor.submit(run_ping, ip, PING_COUNT)

        def collect_results():
            # Collect ALL results first
            results = {}
            for name, future in futures.items():
                try:
                    results[name] = future.result()
                except Exception:
                    results[name] = PingResult()

            # Update GUI with all results
            for name, result in results.items():
                self.root.after(0, self.update_row, name, result)

            # Reset countdown only AFTER all pings are done
            def finish_pinging():
                self.countdown_seconds = REFRESH_INTERVAL
                self.is_pinging = False  # Re-enable countdown

            self.root.after(0, finish_pinging)

        threading.Thread(target=collect_results, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = PingApp(root)
    root.mainloop()