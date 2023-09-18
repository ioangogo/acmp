# acmp (Animal Crossing Music Player) - main.py
# Michael D'Argenio
# mjdargen@gmail.com
# https://dargenio.dev
# https://github.com/mjdargen
import os, sys
import time
import random
import datetime
import argparse
import multiprocessing
from dotenv import load_dotenv
from pydub import AudioSegment
from pydub.playback import _play_with_simpleaudio
from homeassistant_api import Client as homeClient
import json
import xdg_base_dirs


rain_state=["hail", "lightning", "lightning-rainy", "pouring", "rainy"]
snow_states=["snowy", "snowy-rainy"]


def get_weather(hassc):
    api_url=hassc.get("auth").get("api_url")
    token=hassc.get("auth").get("token")
    hass_client=homeClient(api_url, token)

    weather=hass_client.get_entity(entity_id=hassc.get("entity", "weather.home")).get_state().state

    if weather.lower() in rain_state:
        return 'raining'
    elif weather.lower() in snow_states:
        return 'snowing'
    else:
        return 'sunny'


# process for handling timeing to switch over
def timing(conn, hassc):
    prev = None
    while True:

        weather = get_weather(hassc)
        # get current time
        now = datetime.datetime.now().strftime("%I%p").lower()
        if now[0] == '0':
            now = now[1:]
        # send message with time and date
        if prev != now:
            conn.send(f'{now}_{weather}')
            prev = now

        # compute how long to sleep for
        now = datetime.datetime.now()
        delta = datetime.timedelta(hours=1)
        next_hour = (now + delta).replace(microsecond=0, second=0, minute=0)
        wait_seconds = (next_hour - now).seconds
        time.sleep(wait_seconds)


# process for handling audio
def audio(conn, game):
    DIR_PATH = os.path.dirname(os.path.realpath(__file__))

    # start with silence to initialize objects before loop
    file = f'{DIR_PATH}/silence.mp3'
    clip = AudioSegment.from_mp3(file)
    playback = _play_with_simpleaudio(clip)

    while True:
        # check for new message
        if conn.poll():
            name = conn.recv()
            print(f'Switching to {name}.')
            file = f'{DIR_PATH}/{game}/{name}.mp3'
            # stop old song and play new one
            playback.stop()
            clip = AudioSegment.from_mp3(file)
            playback = _play_with_simpleaudio(clip)
        # song finished, repeat
        if not playback.is_playing():
            # Waiting a random amount of time(30s to 2 minutes)
            time.sleep(random.randrange(30, 2*60))
            # stop old song and play new one
            playback.stop()
            clip = AudioSegment.from_mp3(file)
            playback = _play_with_simpleaudio(clip)
        time.sleep(2)

default_config={
    "game":"new-horizons",
    "home_assistant":{
        "auth":{
            "api_url":"",
            "token":""
        },
        "entity":"",
    }
}

def main():
    load_dotenv()
    config_path=os.path.join(xdg_base_dirs.xdg_config_dirs()[0], "acamp.json")
    if not os.path.exists(config_path):
        with open(config_path, "w") as f:
            json.dump(default_config, f)
            print(f"config written to {config_path} please edit before continuing")
            sys.exit(1)
    
    config={}
    with open(config_path, "r") as f:
        config=json.load(f)

        


    # handle arguments
    games = ['new-horizons', 'new-leaf', 'wild-world', 'animal-crossing']
    if not config.get("game"):
        game = 'new-horizons'
    if config.get("game") not in games:
        print('Game not recognized... Choosing New Horizons.')
        game = 'new-horizons'
    else:
        game = config.get("game")

    # creating a pipe to communicate between processes
    parent_conn, child_conn = multiprocessing.Pipe()

    # creating processes
    timing_process = multiprocessing.Process(target=timing, args=(child_conn,config.get("home_assistant")))
    audio_process = multiprocessing.Process(
        target=audio, args=(parent_conn, game))

    # be sure to kill processes if keyboard interrupted
    try:
        # starting timing process
        timing_process.start()
        # starting audio process
        audio_process.start()

        # wait until audio is finished
        audio_process.join()
        # wait until timing is finished
        timing_process.join()
    except KeyboardInterrupt:
        print('Interrupted')
        audio_process.terminate()
        timing_process.terminate()


if __name__ == '__main__':
    main()
