import argparse
from cs50 import SQL
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
import requests
from tabulate import tabulate


def main():


    # Create the parser
    parser = argparse.ArgumentParser(description="This program imports a JSON fixutre list and processes the results")

    # Add an argument
    parser.add_argument('--url', type=str, help="This is the URL of the JSON file to be imported")
    parser.add_argument('--date', type=str, help="The date in YYYY-MM-DD format to process results though. Everything after will be treated as a future match")
    parser.add_argument('--historic', type=bool, help="If True it will calculate the SOS for each week from the beinging of the season to the date specified (or todays date if no date is specified).")
    parser.add_argument('--teams', type=str, help="A list in [team1, team2, ..., teamn] format listing the teams to be plotted")
                        
    # Parse the arguments
    args = parser.parse_args()

    # the intialization code at the top of the page only needs to be run when there is a new .json file to load
    # this code loads the json into memory, parses it to figure out what teams played this season
    # then loads all available results for the teams into the db

    # this program has been designed to work with the json from "https://fixturedownload.com/feed/json/epl-2023"

    # load data from .json source
    new_Data = False # set defaul value to be no new data

    if args.url:
        new_Data = True
        data = load_fixtures(args.url)
        
        # get team names
        teams = extract_teams(data)

        load_teamDB(teams)
        load_resultsDB(teams, data)


    # end initialization code    
    if args.date:
        date = args.date
    else:
        date = datetime.today()
    
    db = SQL("sqlite:///premier_league.db")
    teams = db.execute("SELECT COUNT(*) AS num_teams FROM teams")
    team_count = teams[0]["num_teams"]

    if args.historic:
        match_days = db.execute("SELECT DISTINCT DATE(match_date) AS match_date FROM matches WHERE match_date <= ?;", date)
        match_days = [d['match_date'] for d in match_days]
    else:
        match_days = []
        match_days.append(date)

    if new_Data:
        processRecords(match_days) # process match results through this date

    
        for team_id in range(1, team_count + 1):
            if args.historic:
                #compute SOS for every day there is a match
                for match_day in match_days:
                    compute_SOS(team_id, match_day)
                    # input("PAUSE......press ANYKEY")
            else:
                #compute SOS for single date
                compute_SOS(team_id, date)

    display_results()
    plot_results()

    return 0

def compute_SOS(team_id, date=None):
    if date is None:
        date = datetime.today()

    # print(f"\n\nProcessing team {team_id} through {date}...")

    # Configure CS50 Library to use SQLite database
    db = SQL("sqlite:///premier_league.db")
    db.execute("DELETE FROM remaining_fixture_data WHERE team_id = ? AND as_of_date =?;", team_id, date)
    
    home_schedule = db.execute("SELECT matches.away_id AS opponent, matches.match_date, teams.name, records.p FROM matches JOIN teams ON matches.away_id = teams.id JOIN records ON matches.away_id = records.team_id WHERE (matches.home_id = ?) AND matches.match_date > ?;",team_id,date)

    if len(home_schedule) == 0:
        # print("No home games remaining")
        home_pts = [0]
    else:
        home_pts = []
        # print("\n\nHome Schedule\n----------")
        for match in home_schedule:
            home_pts.append(match["p"])
            # print(f"{match["match_date"]} - {match["name"]}: {match["p"]} pts")

   
    away_schedule = db.execute("SELECT matches.home_id AS opponent, matches.match_date, teams.name, records.p FROM matches JOIN teams ON matches.home_id = teams.id JOIN records ON matches.home_id = records.team_id WHERE (matches.away_id = ?) AND matches.match_date > ?;",team_id,date)
    
    if len(away_schedule) == 0:
        # print("No away games remaining")
        away_pts = [0]
    else:
        away_pts = []
        # print("\n\nAway Schedule\n----------")
        for match in away_schedule:
            away_pts.append(match["p"])
            # print(f"{match["match_date"]} - {match["name"]}: {match["p"]} pts")

    if not (len(home_schedule) == 0  and len(away_schedule) == 0):
        total_pts = sum(home_pts) + sum(away_pts)
        total_ave = total_pts / (len(home_pts) + len(away_pts))

        # print(f"Avg Remaining -- HomePts: {sum(home_pts)/len(home_pts):.1f}; AwayPts: {sum(away_pts)/len(away_pts):.1f}; Total: {total_ave:.1f}")
        db.execute("INSERT INTO remaining_fixture_data (team_id, opp_home_pts, opp_home_matches, opp_home_avg, opp_away_pts, opp_away_matches, opp_away_avg, total_avg, total_matches, as_of_date) VALUES (?,?,?,?,?,?,?,?,?,?);", team_id, sum(away_pts), len(away_pts), sum(away_pts)/len(away_pts), sum(home_pts), len(home_pts), sum(home_pts)/len(home_pts),total_ave,len(home_pts)+len(away_pts), date)


def display_results():
    db = SQL("sqlite:///premier_league.db")
    results = db.execute("select name, total_avg, opp_home_avg, opp_away_avg, total_matches, as_of_date from remaining_fixture_data JOIN teams ON id = team_id  ORDER BY name;")

    print(f"\n\nSummary\n-----------\n")
    
    print(tabulate(results, headers="keys", tablefmt="pretty") + "\n")


def extract_teams(data):
    # teams are not hard coded, they are extracted from the list of fixtures
    teams_set = set()
    for record in data:
       teams_set.add(record["HomeTeam"] + "-" + record["Location"])
    
    #once extracted they are returned in a sorted list
    teams = []
    for i, team in enumerate(sorted(teams_set), start=1):
        name, stadium = team.split("-")
        teams.append({"id": i, "name": name, "stadium": stadium})

    return teams   


def get_id_by_name(target_name, list_of_dicts):
    for dict in list_of_dicts:
        if dict["name"] == target_name:
            return dict["id"]
        

def load_fixtures(URL):

    response = requests.get(URL)
    return response.json()
    

def load_resultsDB(teams, data):

    # Configure CS50 Library to use SQLite database
    db = SQL("sqlite:///premier_league.db")
    db.execute("DELETE FROM matches")

    for record in data:
        home_id = get_id_by_name(record["HomeTeam"], teams)
        home_score = record["HomeTeamScore"]
        away_id = get_id_by_name(record["AwayTeam"], teams)
        away_score = record["AwayTeamScore"]
        match_date = record["DateUtc"]
        round_no = record["RoundNumber"]

        print(f"Round {round_no}:{home_id}: {home_score} vs {away_id}: {away_score} at {match_date}")

        db.execute("INSERT INTO matches (match_date, match_round, home_id, home_score, away_id, away_score) VALUES (?,?,?,?,?,?);", match_date, round_no, home_id, home_score, away_id, away_score)
    
    print("Match Load Scucessful")

    return True


def load_teamDB(teams):
    # Configure CS50 Library to use SQLite database
    db = SQL("sqlite:///premier_league.db")
    db.execute("DELETE FROM teams")

    for team in teams:
        db.execute("INSERT INTO teams (id, name, stadium) values (?, ?, ?);", team["id"], team["name"], team["stadium"])

    return True


def plot_results():
    db = SQL("sqlite:///premier_league.db")
    sql_query = "select total_avg, as_of_date from remaining_fixture_data JOIN teams ON id = team_id WHERE id = 1 ORDER BY as_of_date;"
    results = db.execute(sql_query)

    x = []
    y = []
    for result in results:
        x.append(datetime.strptime(result["as_of_date"], "%Y-%m-%d"))
        y.append(result["total_avg"])
    
    plt.plot(x, y)

    sql_query = "select total_avg, as_of_date from remaining_fixture_data JOIN teams ON id = team_id WHERE id = 2 ORDER BY as_of_date;"
    results = db.execute(sql_query)

    x = []
    y = []
    for result in results:
        x.append(datetime.strptime(result["as_of_date"], "%Y-%m-%d"))
        y.append(result["total_avg"])
    
    plt.plot(x, y)

    plt.show()


def process_matches(team_score, opponent_score, record):
    if int(team_score) > int(opponent_score):
        record["w"] += 1
        record["p"] += 3     

    elif int(team_score) < int(opponent_score):
        record["l"] += 1
    else:
        record["d"] += 1
        record["p"] += 1
    
    record["gd"] += team_score - opponent_score
    record["gf"] += team_score
    record["ga"] += opponent_score


def processRecords(dates=None):
    if dates is None:
        dates = []
        dates.append(datetime.today())

    db = SQL("sqlite:///premier_league.db")
    db.execute("DELETE FROM records")

    teams = db.execute("SELECT id, name FROM teams;")
    for team in teams:
        print(f"\n\nTeam {team["id"]} - {team["name"]}\n----------")
        
        for date in dates:
            record = {"w": 0, "d": 0, "l": 0, "p": 0, "gd": 0, "gf": 0, "ga": 0} # reinitialize records
            #select and process home matches
            results = db.execute("SELECT * FROM matches WHERE home_id = ? AND match_date <= ?;", team["id"], date)
            for result in results:
                process_matches(result["home_score"], result["away_score"], record)
            
            #select and process away matches
            results = db.execute("SELECT * FROM matches WHERE away_id = ? AND match_date <= ?;", team["id"], date)
            for result in results:
                process_matches(result["away_score"], result["home_score"], record)

            print(record)
            db.execute("INSERT INTO records (team_id, w, d, l, p, gd, gf, ga, as_of_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);", team["id"], record["w"], record["d"], record["l"], record["p"], record["gd"], record["gf"], record["ga"], date)    
        

def team_selection(teams):
    print(f"\nTeams\n----------")
    for team in teams:
        print(f"{team["id"]} - {team["name"]}")
    return input("Enter the number of the team to compute strength of schedule: ")


if __name__ == "__main__":
    main()