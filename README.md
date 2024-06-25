A python program that intakes the premier league fixture list and computes strength of the remaining schdule.

This is based on the results so far and the fixtures remaining.

The program currently works entirely from the command line. If given a --url argument it will import resuts from that URL.
It is currently configured to work with .json results from: https://fixturedownload.com/feed/json, such as
"https://fixturedownload.com/feed/json/epl-2023"

If given the argument --date "YYYY-MM-DD" it will process the resuts up through that day as if all other
fixures are in the future.


