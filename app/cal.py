from __future__ import print_function
import requests
from bs4 import BeautifulSoup
import os
import datetime
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import logging
import sys
import configparser


logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
handlers=[logging.StreamHandler()]
if os.path.exists('/var/log/kucal'):
    handlers.append(logging.FileHandler("/var/log/kucal/{}.log".format(datetime.datetime.now().date().isoformat())))

logging.basicConfig(
    handlers=handlers,
    format='%(asctime)s[%(levelname)-8s]:%(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

class KU_Calendar:
    under_url = 'http://registrar.korea.ac.kr/eduinfo/affairs/schedule.do'
    gradue_url = 'http://graduate.korea.ac.kr/grad/department/calendar.do'

    def __init__(self):
        try:
            self.dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            self.dir = os.getcwd()
        self.service = self.__init_service()
        config = configparser.ConfigParser()
        config.read(os.path.join(self.dir,'setting.ini'))
        self.graduate_id = config['graduate']['id']
        self.under_id = config['under']['id']        


    def get_sem_list(self, url:str):
        req = requests.get(url)
        html = req.text
        soup = BeautifulSoup(html, 'html.parser')
        sems = soup.select('.category > option')
        return list(tuple(map(lambda x: int(''.join( c for c in x if c.isdigit())), sem.text.split())) for sem in sems)

    def get_sem(self, url:str, year:int, hakGi:int):
        req = requests.get(url + '?cYear={}&hakGi={}'.format(year,hakGi))
        html = req.text
        soup = BeautifulSoup(html, 'html.parser')
        trs = soup.select('div.t_list > table > tr')
        cal = {}
        for tr in trs:
            m = tr.select('th')
            if len(m) > 0:
                cur_m = int(''.join( c for c in m[0].text if c.isdigit()))
                cal[cur_m] = []
            days = tuple(int(n) for n in ''.join(c if c.isdigit() else ' ' for c in tr.select('td')[0].text ).split())
            if len(days) == 1:
                days = days + (days[0],)
            cal[cur_m].append(days + (tr.select('td')[1].text,))
        return cal

    def __init_service(self):
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        token_file_name = os.path.join(self.dir,'token.pickle')
        if not os.path.exists(token_file_name):
            logging.critical('No \'token.pickle\' file for crds')
            sys.exit('No token file')
        with open(token_file_name, 'rb') as token:
            creds = pickle.load(token)
        if not creds.valid:
            logging.warning('creds is not valid')
            if creds and creds.expired and creds.refresh_token:
                logging.info('Try to refresh creds')
                try:
                    creds.refresh(Request())
                except:
                    logging.critical('Failt to refresh creds')
                    sys.exit('Failt to refresh creds')
            else:
                logging.critical('Can not refresh creds')
                sys.exit('Can not refresh creds')
            # Save the credentials for the next run
            with open(token_file_name, 'wb') as token:
                pickle.dump(creds, token)

        service = build('calendar', 'v3', credentials=creds)
        return service

    def get_events(self, year, month, cal_id):
        timeMin = datetime.datetime(year=year,month=month,day=1).isoformat()+'Z'
        if month == 12:
            timeMax = datetime.datetime(year=year+1,month=1,day=1).isoformat()+'Z'
        else:
            timeMax = datetime.datetime(year=year,month=month+1,day=1).isoformat()+'Z'
        events_result = self.service.events().list(calendarId=cal_id, timeMin=timeMin, timeMax=timeMax, singleEvents=True, orderBy='startTime').execute()
        cal = {}
        for item in events_result['items']:
            start = datetime.datetime.strptime(item['start']['date'],'%Y-%m-%d').day
            end = datetime.datetime.strptime(item['end']['date'],'%Y-%m-%d').day
            cal[(start, end, item['summary'])] = item['id']
        return cal
            


    def del_event(self, cal_id, e_id):
        events_result = self.service.events().delete(calendarId=cal_id, eventId=e_id).execute()
        return events_result

    def create_event(self, cal_id, year, month, dates, content:str=''):
        start = datetime.datetime(year=year,month=month,day=dates[0]).strftime('%Y-%m-%d')
        if dates[0] <= dates[1]:
            end = (datetime.datetime(year=year,month=month,day=dates[1])+datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            if month == 12:
                end = (datetime.datetime(year=year+1,month=1,day=dates[1])+datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                end = (datetime.datetime(year=year,month=month+1,day=dates[1])+datetime.timedelta(days=1)).strftime('%Y-%m-%d')

        event = {
        'summary': content,
        #'description': '',
        'start': {
            'date': start,
            #'timeZone': 'America/Los_Angeles',
        },
        'end': {
            'date': end,
            #'timeZone': 'America/Los_Angeles',
        },
        }
        event = self.service.events().insert(calendarId=cal_id, body=event).execute()
        return event
        
    def sync(self, url, cal_id, year, sem):
        s_cals = self.get_sem(url, year,sem)
        for month, s_cal in s_cals.items():
            

            if sem == 2 and month < 6:
                y = year + 1            
            else:
                y = year
                
            g_cal = self.get_events(y, month, cal_id)

            for event in list(g_cal.keys()):
                if event not in s_cal:
                    self.del_event(cal_id, g_cal[event])
                    g_cal.pop(event)
            
            if len(s_cal[0]) != 1:
                for event in s_cal:
                    if event not in g_cal:
                        self.create_event(cal_id, y, month, event[0:2],event[2])
            logging.info("{}.{} done".format(y,month))



    def sync_all_sem(self, url, cal_id):
        sems = self.get_sem_list(url)
        year = datetime.datetime.now().year
        sems = [sem for sem in sems if sem[0] >= year]
        
        for year, sem in sems:
            self.sync(url, cal_id, year, sem)
    def sync_all_grad(self):
        self.sync_all_sem(self.gradue_url, self.graduate_id)
    def sync_all_under(self):
        self.sync_all_sem(self.under_url, self.under_id)
    def sync_all(self):
        self.sync_all_under()
        self.sync_all_grad()
        
        
if __name__ == '__main__':
    logging.info('start')
    try:
        cal = KU_Calendar()
        cal.sync_all()
    except:
        logging.error("Fatal error", exc_info=True)
