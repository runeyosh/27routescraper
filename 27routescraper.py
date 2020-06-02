import requests
import json
import time
from datetime import datetime
from statistics import mean
from bs4 import BeautifulSoup

MIN_AMOUNT_OF_VOTES = 5

STARSCORE = {
    'empty': 0.0,
    'full': 1.0
}

ROUTELISTPATTERN = r'https://27crags.com/crags/{}/routelist'
GENERIC_PATTERN = r'https://27crags.com{}'

CRAGLIST = [
    #use name used in the crag front page url
    r'ostmarka-bukkeberget',
    # r'ostmarka-delux-de-dype-skoger',
    # r'filmplaneten-sor',
    # r'ostmarka-haralokka',
    # r'ostmarka-katteputten',
    # r'ostmarka-korketrekkeren',
    # r'ostmarka-lia-oslo'
]


def get_routes_from_crag(crag):
    # For a given crag, traverse all route and get all public ascents
    req = requests.get(ROUTELISTPATTERN.format(crag))
    soup = BeautifulSoup(req.content, 'html.parser')
    routeinfos = soup.find_all("div", class_='route-block')
    routedict = {}
    for routeinfo in routeinfos:
        routeref = routeinfo.find("a")['href']
        routesoup = BeautifulSoup(requests.get(GENERIC_PATTERN.format(routeref)).content, 'html.parser')

        #Get route info
        routelocation = routesoup.find('h2', class_='craglocation').text.strip().split('\non\n')[1].strip(r'\n').\
            replace(',\n', '-')
        routename = routesoup.find('h1', class_='cragname').text.strip().replace(',','')
        grade = routesoup.find('div', class_='route-name').text.strip().split(',')[-1]

        # Get score and date for each public ascent
        scores = []
        dates = []
        ascents = routesoup.find_all('div', class_='ascent')
        # find all on default view of page
        ascent_dates = routesoup.find_all('div', class_='date pull-right text-right')
        for ascent, date in zip(ascents, ascent_dates):
            score = 0
            for star in ascent.find('span', class_='stars').contents:
                score = score + STARSCORE[star.attrs['class'][1]]
            scores.append(score)
            dates.append(date.text.strip().replace('FIRST ASCENT\n', '').replace('2nd ASCENT\n', ''))

        # Get the ascents only shown under "get more ascents", if it viable for the route
        more_ascents = routesoup.find('div', class_='js-more ticks text-center')
        if more_ascents:
            more_ref = more_ascents.find("a")['href']
            extra_ascents = json.loads(requests.get(GENERIC_PATTERN.format(more_ref)).content)['ticks']
            ascentsoup = BeautifulSoup(extra_ascents, 'html.parser')
            ascentstars = ascentsoup.find_all('span', class_="stars")
            ascent_dates = routesoup.find_all('div', class_='date pull-right text-right')
            for stars, date in zip(ascentstars, ascent_dates):
                score = 0
                for star in stars.contents:
                    score = score + STARSCORE[star.attrs['class'][1]]
                scores.append(score)
                dates.append(date.text.strip().replace('FIRST ASCENT\n', '').replace('2nd ASCENT\n', ''))
        # make dict entry for route with info
        routedict[routename] = {'location': routelocation, 'grade': grade, 'ratings': scores, 'crag': crag,
                                'dates': dates}
        # print(routename)

        # sleep just to be nice to the 27 servers
        time.sleep(1)
    # return the dict of all routes
    return routedict


def get_and_store_routeinfo(json_filepath):
    # scrape and save to json
    all_routes_dict = {}
    for crag in CRAGLIST:
        routesdict = get_routes_from_crag(crag)
        all_routes_dict.update(routesdict)
    json.dump(all_routes_dict, open(json_filepath, 'w'))
    return all_routes_dict


def weighted_rating(json_filepath, min_amount_of_votes=0):
    # Calculated rating weighted with number of ratings. Expression is taken from Imdb's weighted rating for best movies
    # The idea is to "normalise" the score by how many votes it's gotten. A 3 star boulder with 1 vote is not as good as
    # a 2.5 start boulder with 10 votes.
    #
    # weighted rating (WR) = (v ÷ (v+m)) × R + (m ÷ (v+m)) × C , where:
    #
    # * R = average for the movie (mean) = (Rating)
    # * v = number of votes for the movie = (votes)
    # * m = minimum votes required to be listed in the Top 250 (currently 3000)
    # * C = the mean vote across the whole report (currently 6.9)
    #

    all_routes_dict = json.load(open(json_filepath))
    gradesdict = {}
    global_votes = []
    dates = []
    for k in all_routes_dict.keys():
        # make list of ALL votes and dates, make a dict per grade
        global_votes = global_votes + all_routes_dict[k]['ratings']
        dates = dates + [datetime.strptime(d, '%Y-%m-%d')
                         for d in all_routes_dict[k]['dates']]
        if len(all_routes_dict[k]['ratings']) >= min_amount_of_votes:
            if all_routes_dict[k]['grade'] not in gradesdict.keys():
                gradesdict[all_routes_dict[k]['grade']] = {k: all_routes_dict[k]}
            else:
                gradesdict[all_routes_dict[k]['grade']].update({k: all_routes_dict[k]})
    for grade in gradesdict.keys():
        # for each grade, calculate C separately. Huge variety in how people vote at different grades.
        # Apparently harder grade = better quality :)
        routes = gradesdict[grade]
        total_votes = []
        for route in routes.keys():
            total_votes = total_votes + routes[route]['ratings']
        C = mean(global_votes)
        for k in routes.keys():
            R = mean(routes[k]['ratings'])
            v = len(routes[k]['ratings'])
            m = MIN_AMOUNT_OF_VOTES
            wr = (v / (v+m)) * R + (m / (v+m)) * C
            # just printing for now. Can also be saves as CSV or something. Works well to just copy/paste output to
            # Google sheets and convert text to columns
            print('Route: {}, Crag: {}, Grade: {}, Votes: {}, Mean: {}, WR: {}'. format(k,
                                                                                        routes[k]['location'],
                                                                                        routes[k]['grade'], v, R, wr))


if __name__ == "__main__":
    jsonfilename = "{}.json".format('all_boulders_test')
    # get_and_store_routeinfo(jsonfilename)
    weighted_rating(jsonfilename, min_amount_of_votes=MIN_AMOUNT_OF_VOTES)

