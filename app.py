from flask import Flask, jsonify
import pyodbc

app = Flask(__name__)

CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=UAVTrafficDB;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def get_connection():
    return pyodbc.connect(CONNECTION_STRING)


@app.route("/")
def home():
    return jsonify({
        "message": "UAV Traffic API is running"
    })


@app.route("/api/summary")
def get_summary():
    sql = """
        SELECT
            COUNT_BIG(*) AS TotalPoints,
            COUNT(DISTINCT TrackID) AS TotalVehicles,
            AVG(Speed) AS AverageSpeed
        FROM dbo.TrajectoryRecords
        WHERE DatasetID = 1
          AND VersionID = 1;
    """

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()

        return jsonify({
            "total_points": int(row.TotalPoints or 0),
            "total_vehicles": int(row.TotalVehicles or 0),
            "average_speed": (
                round(float(row.AverageSpeed), 2)
                if row.AverageSpeed is not None
                else None
            )
        })

    except Exception as error:
        return jsonify({
            "error": str(error)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)