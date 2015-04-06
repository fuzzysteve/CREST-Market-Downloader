import select
import wx
from wx.lib.pubsub import setupkwargs
from wx.lib.pubsub import pub
import ConfigParser
from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
from SocketServer import ThreadingMixIn
import threading
import urlparse
import base64
import os
import webbrowser
import json
import time
import csv
import requests
import grequests
import time
import locale
from datetime import date

class authHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/favicon.ico":
            return;
        parsed_path = urlparse.urlparse(self.path)
        parts=urlparse.parse_qs(parsed_path.query)
        self.send_response(200)
        self.end_headers()
        self.wfile.write('Login successful. you can close this window now')
        wx.CallAfter(pub.sendMessage, 'login', message=str(parts['code'][0]))
    def log_message(self, format, *args):
        return
    
 
# Create a new frame class, derived from the wxPython Frame.
class MarketView(wx.Frame):

    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, id, title)
        panel = wx.Panel(self, -1)
        self.panel = panel
        self.login=wx.Button(panel,id=wx.ID_ANY,label='Login')
        self.regionCombo = wx.ComboBox(panel,-1,"Login to populate regions",style=wx.CB_READONLY|wx.CB_SORT)
        self.get_region=wx.Button(panel,id=wx.ID_ANY,label='Dump Region')
        self.save=wx.Button(panel,id=wx.ID_ANY,label='Export Location')
        self.filter=wx.Button(panel,id=wx.ID_ANY,label='Filter File')
        self.get_region.Disable()
        menubar = wx.MenuBar()
        login=wx.Menu()

        self.statusbar=self.CreateStatusBar(style=0)
        self.statusbar.SetFieldsCount(2)
        self.statusbar.SetStatusWidths([-2, -1])
        self.SetStatusText("Please Log in",0)   
        sizer = wx.FlexGridSizer(2, 3, 5, 5)
        sizer.Add(self.login)
        sizer.Add(self.regionCombo)
        sizer.Add(self.get_region)
        sizer.Add(self.save)
        sizer.Add(self.filter)
        border = wx.BoxSizer()
        border.Add(sizer, 0, wx.ALL, 15)
        panel.SetSizerAndFit(border)
        self.Fit()
        self.Centre()

    def update_status(self,data,extra1=0):
        self.SetStatusText(data,extra1)
        
        
    def update_regions(self,regions):
        self.regionCombo.Clear()
        for item in regions['items']:
            self.regionCombo.Append(item['name'],item)
    
    def show_dir(self):
        path= os.getcwd()
        dlg = wx.DirDialog(
            self, "Save file in ...", 
            style=wx.DD_DEFAULT_STYLE|wx.DD_DIR_MUST_EXIST|wx.DD_CHANGE_DIR
            )
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
        dlg.Destroy()
        return path
    
    def select_filter_file(self):
        file = 'nofile'
        wildcard="CSV (*.csv)|*.csv"
        dlg = wx.FileDialog(
            self, "Select Filter File", os.getcwd(),"",wildcard,wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            file = dlg.GetPath()
        dlg.Destroy()
        return file
    

class MarketModel:
    def __init__(self,settings):
        self.settings=dict()
        self.settings['PORT'] = settings.getint('Config','Port')
        self.settings['CLIENTID'] = settings.get('Config','Clientid')
        self.settings['SECRET'] = settings.get('Config','Secret')
        self.settings['USERAGENT'] = settings.get('Config','UserAgent')
        self.settings['BASEURL'] = settings.get('Config','BaseUrl')
        self.settings['accessToken'] = ''
        self.settings['refreshToken'] =''
        self.settings['endPoints'] = ''
        self.settings['expires']=-1
        self.cert_path = os.path.dirname(os.path.abspath(__file__))+os.sep+'cacert.pem'
        self.directory = os.getcwd()
        self.filterfile = 'nofile'
    
        
    def get_region(self,event):
        self.set_status_text("Dump beginning.",0)
        filterlist={}
        filterme=False
        if self.filterfile != 'nofile' and os.path.isfile(self.filterfile):
            with open(self.filterfile,'rb') as filterfile:
                filterreader=csv.reader(filterfile,dialect='excel')
                for row in filterreader:
                    filterlist[int(row[0])]=True;
            filterme=True
        itemCount=len(self.marketItems)
        count=0
        batch=0
        startTime=time.time()
        buyUrls=[]
        sellUrls=[]
        for item in self.marketItems:
         count+=1
         wx.Yield()
         if filterme:
             if (int(item['id']) in filterlist):
                 buyUrls.append(self.currentRegion['marketBuyOrders']['href']+"?type="+item['href'])
                 sellUrls.append(self.currentRegion['marketSellOrders']['href']+"?type="+item['href'])
                 batch+=1
         else:
                 buyUrls.append(self.currentRegion['marketBuyOrders']['href']+"?type="+item['href'])
                 sellUrls.append(self.currentRegion['marketSellOrders']['href']+"?type="+item['href'])
                 batch+=1
         if (itemCount==count) or (batch==20):
             buy=self.get_multiple_endpoint(buyUrls, 'application/vnd.ccp.eve.MarketOrderCollection-v1+json; charset=utf-8')
             sell=self.get_multiple_endpoint(sellUrls, 'application/vnd.ccp.eve.MarketOrderCollection-v1+json; charset=utf-8')
             batch=0
             now=time.time()
             sofar=now-startTime
             fraction=float(count)/float(itemCount)
             total=sofar/fraction
             remaining=total-sofar
             self.set_status_text("Completion: "+locale.format("%d",count,grouping=True)+'/'+locale.format("%d",itemCount,grouping=True),0)
             self.set_status_text(locale.format("%d",sofar,grouping=True)+'/'+locale.format("%d",remaining,grouping=True)+'/'+locale.format("%d",total,grouping=True),1)
             wx.Yield()
             buyUrls=[]
             sellUrls=[]
             types=list(set(buy.keys() + sell.keys()))
             for type in types:
                with open(self.directory+os.sep+self.currentRegion['name']+'-'+type+'-'+date.today().isoformat()+'.csv', 'wb') as csvfile:
                    writer = csv.writer(csvfile,dialect='excel')
                    writer.writerow(['Buy','typeid','volume','issued','duration','Volume Entered','Minimum Volume','range','price','locationid','locationname'])
                    if type in buy:
                        for buyitem in buy[type]:
                            writer.writerow([1,buyitem['type']['id'],buyitem['volume'],buyitem['issued'],buyitem['duration'],buyitem['volumeEntered'],buyitem['minVolume'],buyitem['range'],buyitem['price'],buyitem['location']['id'],buyitem['location']['name']])
                    if type in sell:
                        for sellitem in sell[type]:
                            writer.writerow([0,sellitem['type']['id'],sellitem['volume'],sellitem['issued'],sellitem['duration'],sellitem['volumeEntered'],1,sellitem['range'],sellitem['price'],sellitem['location']['id'],sellitem['location']['name']])
        self.set_status_text("Complete.",0)
        self.set_status_text("",1)
        pub.sendMessage('completedDump',data='done')
        
        
    def get_multiple_endpoint(self,endpoints,accept):
        if self.settings['expires']<time.time():
            self.refresh_tokens()
        items={}
        headers = {'Authorization':'Bearer '+ self.settings['accessToken'],
            'Accept':accept,
            'User-Agent':self.settings['USERAGENT']
            }
        rs = (grequests.get(u,headers=headers,verify=self.cert_path) for u in endpoints)
        responses=grequests.map(rs)
        for response in responses:
            add=response.json()
            if len(add['items']):
                items[str(add['items'][0]['type']['name'])]=add['items']
            response.close()
        return items
        
    def do_login(self,message):
        headers = {'User-Agent':self.settings['USERAGENT']}
        query = {'grant_type':'authorization_code','code':message}
        r = requests.get(self.settings['BASEURL'],headers=headers,verify=self.cert_path)
        self.settings['endPoints']=r.json()
        headers = {'Authorization':'Basic '+ base64.b64encode(self.settings['CLIENTID']+':'+self.settings['SECRET']),'User-Agent':self.settings['USERAGENT']}
        r = requests.post(self.settings['endPoints']['authEndpoint']['href'],params=query,headers=headers,verify=self.cert_path)
        response = r.json()
        self.settings['accessToken']=response['access_token']
        self.settings['refreshToken']=response['refresh_token']
        self.settings['expires']=time.time()+float(response['expires_in'])-20
        self.load_base_data()
        
    def refresh_tokens(self):
        headers = {'Authorization':'Basic '+ base64.b64encode(self.settings['CLIENTID']+':'+self.settings['SECRET']),'User-Agent':self.settings['USERAGENT']}
        query = {'grant_type':'refresh_token','refresh_token':self.settings['refreshToken']}
        r = requests.post(endPoints['authEndpoint']['href'],params=query,headers=headers,verify=self.cert_path)
        response = r.json()
        self.settings['accessToken']=response['access_token']
        self.settings['refreshToken']=response['refresh_token']
        self.settings['expires']=time.time()+float(response['expires_in'])-20

        
    def load_base_data(self):
        headers = {'Authorization':'Bearer '+ self.settings['accessToken'],'User-Agent':self.settings['USERAGENT']}
        self.set_status_text("Loading Regions",0)
        r = requests.get(self.settings['endPoints']['regions']['href'],headers=headers,verify=self.cert_path)
        self.regions=r.json()
        pub.sendMessage('update_regions')
        self.set_status_text("Loading Market Types",0)
        self.marketItems=self.walk_market_types('application/vnd.ccp.eve.MarketTypeCollection-v1+json; charset=utf-8');
        self.set_status_text("Select a region to continue.",0)
              
        
    
    def get_endpoint(self,endpoint,accept,parameters=None):
        if self.settings['expires']<time.time():
            self.refresh_tokens()
        headers = {'Authorization':'Bearer '+ self.settings['accessToken'],
            'Accept':accept,
            'User-Agent':self.settings['USERAGENT']
            }
        if parameters is not None:
            r = requests.get(endpoint,params=parameters,headers=headers,verify=self.cert_path)
        else:
            r = requests.get(endpoint,headers=headers,verify=self.cert_path)
        return r.json()
    
    def walk_market_types(self,accept):
        returnCollection=[]
        url=self.settings['endPoints']['marketTypes']['href']
        page=0
        while True:
            page=page+1
            self.set_status_text("Loading Market Types:",0)
            self.set_status_text(str(page),1)
            wx.Yield()
            walker=self.get_endpoint(url,accept)
            for item in walker['items']:
                returnCollection.append(item['type'])
            if walker.has_key('next'):
                url=walker['next']['href']
            else:
                break
        self.set_status_text('',1)
        return returnCollection
        
    def set_status_text(self,data,id):
        pub.sendMessage('update_status',data=data,extra1=id)

    




class MarketController:
    
    def __init__(self,app,inifile):
        
        self.view = MarketView(None, -1, "Market Loader")

        self.view.login.Bind(wx.EVT_BUTTON,self.on_login)
        self.view.regionCombo.Bind(wx.EVT_COMBOBOX,self.on_region_select)
        self.view.save.Bind(wx.EVT_BUTTON, self.on_save_dir)
        self.view.filter.Bind(wx.EVT_BUTTON, self.on_filter_file)

        self.view.Show(True)        
        app.SetTopWindow(self.view)
        settings = ConfigParser.ConfigParser()
        settings.read(inifile)
        self.model=MarketModel(settings)
        
        self.view.get_region.Bind(wx.EVT_BUTTON,self.model.get_region)
        
        server = HTTPServer(('', settings.getint('Config','Port')), authHandler)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        pub.subscribe(self.do_login_controller,'login')
        pub.subscribe(self.update_status_controller,'update_status')
        pub.subscribe(self.update_regions_controller,'update_regions')
        pub.subscribe(self.completed_dump,'completedDump')

    def on_login(self,event):
        webbrowser.open('https://login.eveonline.com/oauth/authorize?response_type=code&redirect_uri=http://localhost:'+`self.model.settings['PORT']`+'/&client_id='+self.model.settings['CLIENTID']+'&scope=publicData&state=')

    def on_region_select(self,event):
        selected=self.view.regionCombo.GetClientData(self.view.regionCombo.GetSelection())
        self.model.currentRegion=self.model.get_endpoint(selected['href'], 'application/vnd.ccp.eve.Region-v1+json; charset=utf-8')
        self.view.get_region.Enable()
        self.view.SetStatusText("Ready.",0)
        
    def do_login_controller(self,message):
        self.view.login.Disable()
        self.model.do_login(message)

    def on_save_dir(self,event):
        self.model.directory=self.view.show_dir()
    
    def on_filter_file(self,event):
        self.model.filterfile=self.view.select_filter_file()
    
    def update_status_controller(self,data,extra1=0):
        self.view.update_status(data,extra1)
    
    def get_region_controller(self,event):
        self.view.get_region.Disable()
        self.view.regionCombo.Disable()
        self.model.get_region()
    
    def completed_dump(self,data):
        self.view.get_region.Enable()
        self.view.regionCombo.Enable()

    def update_regions_controller(self):
        self.view.update_regions(self.model.regions)

if __name__ == '__main__':
    inifile=os.path.dirname(os.path.abspath(__file__))+os.sep+"downloader.ini"
    app = wx.App(False)
    controller = MarketController(app,inifile)     # Create an instance of the application class
    app.MainLoop()     # Tell it to start processing events
