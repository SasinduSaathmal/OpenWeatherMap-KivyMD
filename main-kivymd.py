from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.relativelayout import MDRelativeLayout
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from kivymd.uix.menu import MDDropdownMenu
from kivy.clock import Clock
import pandas
import aiohttp
import json
import datetime
import geocoder
import pytz
import platform
import asyncio
import requests
import os
import certifi
import ssl


ssl.default_ca_certs = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class WeatherUI(MDRelativeLayout):
    pass


class ChangeDialog(MDBoxLayout):
    pass


class MessageHandler():
    def __init__(self, **kwargs):
        super(MessageHandler, self).__init__(**kwargs)

    def cityNotFound(self):
        print("City Not Found")
        if not self.alert_dialog:
            self.alert_dialog = MDDialog(
                title="City Not Found!",
                text="The city or the country you typed is probably wrong.",
                buttons=[
                    MDFlatButton(
                        text="OK",
                        theme_text_color="Custom",
                        text_color=self.theme_cls.primary_color,
                        on_release=lambda x: self.closeDialog(alert=True, dialog=True),
                    )
                ],
            )

        self.root.ids.city.text = self.city = self.old_city
        self.root.ids.country.text = self.country = self.old_country
        self.country_code = self.old_country

        self.alert_dialog.open()

    def connectionError(self):
        self.retry_event = Clock.schedule_interval(self.retry, 1)
        self.conn_error_dialog = MDDialog(
            title = "Connection Error",
            text = "Failed to connect to the api after 10 max retries.",
            widget_style = "android",
            buttons = [
                MDFlatButton(
                    text = "RETRY",
                    text_color = "red",
                    on_release = self.retry,
                    )
                ],
            )

        self.conn_error_dialog.open()

    def get_city(self, *args):
        if not self.dialog:
            self.dialog = MDDialog(
                title="Change the city",
                type="custom",
                content_cls=self.cdialog,
                buttons=[
                    MDFlatButton(
                        text="CANCEL",
                        theme_text_color="Custom",
                        text_color=self.theme_cls.primary_color,
                        on_release=lambda x: self.closeDialog(dialog=True, alert=False),
                    ),
                    MDFlatButton(
                        text="UPDATE",
                        theme_text_color="Custom",
                        text_color=self.theme_cls.primary_color,
                        on_release=self.get_data,
                    ),
                ],
            )
        self.dialog.open()
        print(self.city, self.country)


    def closeDialog(self, *args, **kwargs):
        if kwargs["dialog"] == True:
            self.dialog.dismiss(force=True)
        if kwargs["alert"] == True:
            self.alert_dialog.dismiss(force=True)


class DataHandler():
    def __init__(self, **kwargs):
        super(DataHandler, self).__init__(**kwargs)

    def checkConnection(self):
        self.is_retrying = True
        try:
            resp = requests.get("https://www.google.com")
            data = resp.text
            status = resp.status_code
            return True, status
        except Exception as e:
            return False, e


    async def get_my_current_location(self):
        try:
            g = geocoder.ip("me")
            if g.latlng is not None:
                coordinates = g.latlng
                if coordinates is not None:
                    latitude, longitude = coordinates
                    self.root.ids.city.text = self.city = g.city
                    self.root.ids.country.text = self.country_code = g.country
                    index = list(self.country_codes).index(self.country_code)
                    self.country = self.countries[index]
                    self.is_ip = False
                    return latitude, longitude
                else:
                    print("Unable to retrieve your GPS coordinates.")
            else:
                return None

        except Exception as e:
            print(f"GPS Location Exception: {e}")
        return None

    async def get_location(self, location_url):
        async with aiohttp.ClientSession() as self.session:
            async with self.session.get(location_url) as location_response:
                if location_response.status == 200:
                    json_data = await location_response.json()

                    try:
                        lat = json_data[0]["lat"]
                        lon = json_data[0]["lon"]
                    except Exception as e:
                        lat, lon = 1, 1
                        with open("Errors.txt", "a") as error_file:
                            dt = datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S")
                            error_file.write(f"[{dt}] {str(e)}\n")

                    return lat, lon

                else:
                    print(
                        "Error",
                        f"An error occurred! Error code {location_response.status}",
                    )

    async def get_weather_data(self, weather_url):
        async with aiohttp.ClientSession() as self.session:
            async with self.session.get(weather_url) as weather_response:
                if weather_response.status == 200:
                    json_data = await weather_response.json()
                    with open("response.json", "w") as file:
                        json.dump(json_data, file, indent=4, sort_keys=True)

                    return "Success"
                else:
                    print(f"An error occurred! Error code {weather_response.status}")

    def extractCountryData(self):
        data = pandas.read_csv("assets/country-data.csv")
        countries = data.Name.values
        country_codes = data.Code.values
        return countries, country_codes

    def modify_time(self, json_data, key, subkey=None, tz=False, timezone=None):
        if subkey == None:
            json_utc_time = json_data[key]
        else:
            json_utc_time = json_data[key][subkey]
        utc_datetime = datetime.datetime.utcfromtimestamp(json_utc_time)
        my_timezone = pytz.timezone("Asia/Colombo")
        datetime_change = utc_datetime.astimezone(my_timezone).strftime("%z")
        mins = int(datetime_change[3:])
        hours = int(datetime_change[1:3])
        op = datetime_change[0]
        if tz == True:
            hours, mins, op = self.modify_timezone(timezone)
        if op == "+":
            time_to_add = datetime.timedelta(hours=hours, minutes=mins)
            new_time = utc_datetime + time_to_add
            time = new_time.strftime("%H:%M:%S")
        else:
            time_to_substract = datetime.timedelta(hours=hours, minutes=mins)
            new_time = utc_datetime - time_to_substract
            time = new_time.strftime("%H:%M:%S")

        return time

    def modify_timezone(self, utc_timezone):
        timezone = utc_timezone / 3600
        if timezone > 0:
            hour, min = tuple(str(round(timezone, 1)).split("."))
            op = "+"
        else:
            hour, min = tuple(str(round(timezone, 1)).replace("-", "").split("."))
            op = "-"
        min = int(int(min) * 6)
        return int(hour), min, op

    def kelvin2celsius(self, value):
        celsius_value = round(value - 273.15, 2)
        return celsius_value

    async def modify(self):
        with open("response.json", "r") as file:
            json_data = json.load(file)

        timezone = json_data["timezone"]
        time = self.modify_time(json_data, "dt", tz=True, timezone=timezone)
        feels_like_temp = self.kelvin2celsius(json_data["main"]["feels_like"])
        humidity = json_data["main"]["humidity"]
        temperature = self.kelvin2celsius(json_data["main"]["temp"])
        sunrise = self.modify_time(json_data, "sys", "sunrise", True, timezone)
        sunset = self.modify_time(json_data, "sys", "sunset", True, timezone)
        wind = json_data["wind"]["speed"]
        icon = json_data["weather"][0]["icon"]
        description = json_data["weather"][0]["description"]
        main = json_data["weather"][0]["main"]
        self.icon_url = f"https://openweathermap.org/img/wn/{icon}@2x.png"
        self.weather_data = {
            "time": str(time),
            "temp": str(temperature),
            "feels_like": str(feels_like_temp),
            "humidity": str(humidity),
            "sunset": str(sunset),
            "sunrise": str(sunrise),
            "weather": str(main),
            "weather-info": str(description),
            "icon": str(icon),
            "wind": str(wind),
        }


class WeatherApp(MDApp, MessageHandler, DataHandler):
    def __init__(self, **kwargs):
        super(WeatherApp, self).__init__(**kwargs)

        self.request_in_progress = False  # Flag to track request status
        self.first_run = True
        self.called = False
        self.alert_dialog = None
        self.dialog = None
        self.conn_error_dialog = None
        self.is_retrying = False
        self.is_ip = True
        self.city = "City"
        self.country_code = "Country code"
        self.country = "Country"
        self.max_retries = 10

    def build(self):
        # self.theme_cls.colors = colours
        self.icon = "images/weather-icon.png"
        self.theme_cls.theme_style_switch_animation = True
        self.theme_cls.primary_palette = "DeepPurple"
        self.theme_cls.theme_style = "Dark"
        Builder.load_file("weather-md.kv")

        return WeatherUI()

    def on_start(self):
        self.initMenu()
        Clock.schedule_once(self.start_request)
        Clock.schedule_interval(
            self.check_request_status, 0.5
        )  # Check status every 0.5 seconds

    def changeTheme(self, x):
        # "#607D8B"
        self.theme_cls.theme_style = (
            "Dark" if self.theme_cls.theme_style == "Light" else "Light"
        )

    def initMenu(self):
        countries, country_codes = self.extractCountryData()
        self.countries = countries
        self.country_codes = country_codes

        self.cdialog = ChangeDialog()

        self.menu_items = [
            {
                "viewclass": "OneLineListItem",
                "text": str(i),
                "on_press": lambda x=str(i): self.changeCountry(x),
            }
            for i in self.countries
        ]

        self.menu = MDDropdownMenu(
            caller=self.cdialog.ids.country_input,
            items=self.menu_items,
            ver_growth="down",
            hor_growth="right",
            position="center",
            width_mult=4,
            max_height=200,
            elevation=5,
        )

    def filterCountries(self, *args):
        country_input = self.cdialog.ids.country_input.text.lower()

        def filterCountry(country):
            if country_input in country:
                return True

        if (not country_input == "") and (not self.called == True):
            items = list(filter(filterCountry, self.countries))
            self.menu_items = [
                {
                    "viewclass": "OneLineListItem",
                    "text": str(i),
                    "on_press": lambda x=str(i): self.changeCountry(x),
                }
                for i in items
            ]
            self.menu.items = self.menu_items
            self.menu.dismiss()
            self.menu.open()

            self.menu_items = [
                {
                    "viewclass": "OneLineListItem",
                    "text": str(i),
                    "on_press": lambda x=str(i): self.changeCountry(x),
                }
                for i in self.countries
            ]

        self.called = False

    def retry(self, *args):
        if self.conn_error_dialog:
            self.conn_error_dialog.dismiss(force=True)
        status, code = self.checkConnection()
        if status == True:
            Clock.schedule_once(self.start_request)
        else:
            print(code)

    def changeCountry(self, text):
        self.called = True
        print(text)
        self.cdialog.ids.country_input.text = text
        index = list(self.countries).index(text.lower())
        self.city = self.cdialog.ids.city_input.text
        self.country = text
        self.country_code = self.country_codes[index]
        self.menu.dismiss()

    def doProgress(self, state):
        if state == "off":
            print("Start")
            self.root.ids.progress.start()
        if state == "on":
            print("Stop")
            self.root.ids.progress.stop()

    def get_data(self, *args):
        self.dialog.dismiss(force=True)
        if not self.request_in_progress:
            self.root.ids.progress.start()
            self.old_city = self.city
            self.old_country = self.country
            self.old_country_code = self.country_code
            self.country = self.cdialog.ids.country_input.text
            try:
                index = list(self.countries).index(self.country.lower())
                self.country_code = self.country_codes[index]
            except Exception:
                self.country = self.old_country
                self.dialog.dismiss(force=True)
                self.cityNotFound()
                return
            self.city = self.cdialog.ids.city_input.text
            Clock.schedule_once(self.start_request)
        self.root.ids.progress.stop()

    def start_request(self, *args):
        self.request_in_progress = True
        Clock.schedule_once(
            lambda dt: asyncio.run(self.make_request(self.city, self.country_code))
        )
        print(self.city, self.country, self.country_code)

    async def make_request(self, city, country_code):
        api_key = "c4fd92f2363b707ff8f8f192e5d3f02c"
        if not self.first_run:
            if not self.is_ip:
                location_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city},{country_code}&limit=3&appid={api_key}"
                for i in range(self.max_retries):
                    self.doProgress("off")
                    try:
                        lat, lon = await self.get_location(location_url)
                        self.doProgress("on")
                        break
                    except Exception as e:
                        print(f"Error at getting location: {e}")

                else:
                    self.connectionError()
                    return

        else:
            for i in range(self.max_retries):
                self.doProgress("off")
                try:
                    lat, lon = await self.get_my_current_location()
                    if self.is_retrying == True:
                        self.is_retrying = False
                        self.retry_event.cancel()
                    self.doProgress("on")
                    break
                except Exception as e:
                    print(f"Error at ip getting location: {e}")

            else:
                print("[error]connection error")
                self.connectionError()
                return

        if lat == 1 and lon == 1:
            self.root.ids.city.text = self.city = self.old_city
            self.root.ids.country.text = self.country = self.old_country
            self.country_code = self.old_country
            self.dialog.dismiss(force=True)
            self.cityNotFound()
            return "City not found!"
        else:
            weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}"
            for i in range(self.max_retries):
                self.doProgress("off")
                try:
                    status = await self.get_weather_data(weather_url)
                    self.doProgress("on")
                    break
                except Exception as e:
                    print(f"Error at getting weather data: {e}")
            else:
                self.connectionError()
                return

            if not status == "Success":
                self.city = status
                return status
            data = await self.modify()
            self.first_run = False
            return data

    def check_request_status(self, dt):
        if self.request_in_progress:
            if not self.first_run:
                self.request_in_progress = False
                self.root.ids.image.source = f"images/{self.weather_data['icon']}.png"
                self.root.ids.weather.text = self.weather_data["weather"]
                self.root.ids.weather_info.text = self.weather_data["weather-info"]
                self.root.ids.temperature.text = self.weather_data["temp"] + "°C"
                self.root.ids.feels_like_temp.text = f"Feels Like {self.weather_data['feels_like']}°C"
                self.root.ids.humidity.text = self.weather_data["humidity"] + "%"
                self.root.ids.sunrise.text = self.weather_data["sunrise"]
                self.root.ids.sunset.text = self.weather_data["sunset"]
                self.root.ids.wind.text = self.weather_data["wind"] + "m/s"

            self.root.ids.city.text = self.city.capitalize()
            self.root.ids.country.text = self.country.capitalize()

    


weather_instance = WeatherApp()
weather_instance.run()
