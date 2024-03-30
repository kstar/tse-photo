#!/usr/bin/env python3

import datetime
import os
import subprocess
import time
import tqdm
import sys
from enum import Enum

DATE = (2024, 3, 30) # FIXME FIXME FIXME: Change to eclipse date otherwise nothing will happen # FIXME: Expects eclipse to happen on a single UTC date

DEFINE_TIMINGS_UTC = [
    (0, 59, 0), # First contact (H, M, S)
    (1, 2, 0), # Second contact (H, M, S)
    (1, 6, 0), # Third contact (H, M, S)
    (1, 8, 0), # Fourth contact (H, M, S)
]

DIAMOND_RING = 25  # Go into diamond ring mode at C2/C3 ± these many seconds
BAILEYS_BEADS = 10 # Go into Bailey's beads mode at C2/C3 ± these many seconds

class Config:
    Bracketing ='/main/capturesettings/aeb'
    Aperture = '/main/capturesettings/aperture'
    ShutterSpeed = '/main/capturesettings/shutterspeed'
    EV = '/main/capturesettings/exposurecompensation'
    ISO = '/main/imgsettings/iso'

class Bracketing(Enum):
    # Obtained through `gphoto2 --get-config "/main/capturesettings/aeb"`
    OFF = 0
    EV_0_1_3 = 1
    EV_0_2_3 = 2
    EV_1 = 3
    EV_1_1_3 = 4
    EV_1_2_3 = 5
    EV_2 = 6

# class EV(Enum):
#     # gphoto2 --get-config /main/capturesettings/exposurecompensation
#     EV_m2   = 0 # -2.0
#     EV_m1p6 = 1 # -1.6
#     EV_m1p3 = 2
#     EV_m1   = 3
#     EV_m0p6 = 4
#     EV_m0p3 = 5
#     EV_0    = 6
#     EV_p0p3 = 7
#     EV_p0p6 = 8
#     EV_p0p9 = 1
#     EV_p1p3 = 10
#     EV_p1p6 = 11
#     EV_p2   = 12

# class ISO(Enum):
#     _100 = 1
#     _125 = 2
#     _160 = 3
#     _200 = 4
#     _250 = 5
#     _320 = 6
#     _400 = 7
#     _500 = 8
#     _640 = 9
#     _800 = 10
#     _1000 = 11
#     _1250 = 12
#     _1600 = 13
#     _2000 = 14
#     _2500 = 15
#     _3200 = 16

# class Aperture(Enum):
#     f4_5 = 1
#     f5 = 2
#     f5_6 = 3
#     f6_3 = 4
#     f7_1 = 5
#     f8 = 6
#     f9 = 7
#     f10 = 8
#     f11 = 9
#     f13 = 10
#     f14 = 11
#     f16 = 12
#     f18 = 13
#     f20 = 14
#     f22 = 15
#     f25 = 16
#     f29 = 17
#     f32 = 18

# class ShutterSpeed(Enum):
#     t30 = 1
#     t25 = 2
#     t20 = 3
#     t15 = 4
#     t13 = 5
#     t10_3 = 6
#     t8 = 7
#     t6_3 = 8
#     t5 = 9
#     t4 = 10
#     t3_2 = 11
#     t2_5 = 12
#     t2 = 13
#     t1_6 = 14
#     t1_3 = 15
#     t1 = 16
#     t0_8 = 17
#     t0_6 = 18
#     t0_5 = 19
#     t0_4 = 20
#     t0_3 = 21
#     s4 = 22
#     s5 = 23
#     s6 = 24
#     s8 = 25
#     s10 = 26
#     s13 = 27
#     s15 = 28
#     s20 = 29
#     s25 = 30
#     s30 = 31
#     s40 = 32
#     s50 = 33
#     s60 = 34
#     s80 = 35
#     s100 = 36
#     s125 = 37
#     s160 = 38
#     s200 = 39
#     s250 = 40
#     s320 = 41
#     s400 = 42
#     s500 = 43
#     s640 = 44
#     s800 = 45
#     s1000 = 46
#     s1250 = 47
#     s1600 = 48
#     s2000 = 49
#     s2500 = 50
#     s3200 = 51
#     s4000 = 52
#     s5000 = 53
#     s6400 = 54
#     s8000 = 55



class Settings:
    interval = 0

    # Run  !gphoto2 --get-config /main/capturesettings/aperture to get aperture options
    aperture = "4.5"

    bracketing = Bracketing.OFF
    speed = "1/8000"

    iso = 200

class Phases:
    class Partial(Settings):
        interval = 120 # Take a photo every 2 minutes
        aperture = "10" # f/10 (filtered)
        bracketing = Bracketing.EV_1 # ±1
        speed = "1/1000"

    class Diamond(Settings):
        aperture = "11" # f/11
        bracketing = Bracketing.EV_1_1_3 # ±1⅓
        speed = "1/4000"

    class Baileys(Settings):
        aperture = "16"
        bracketing = Bracketing.EV_1_2_3 # ±1⅔
        speed = "1/3200"

    class Totality(Settings):
        bracketing = Bracketing.OFF
        interval = 5
        delay_compensation = 3
        exposures = [
            ("16", "1/1600", 200), # Chromosphere
            ("11", "1/1600", 200), # Prominences
            ("10", "1/500", 200),  # Lower Corona
            ("10", "1/60", 200),   # Inner Corona
            ("8",  "1/25", 400),   # Middle Corona
            ("6.3", "1/10", 400),  # Outer Corona
            ("6.3", "0.5", 400), # Far Outer Corona
            ("6.3", "1", 400),   # Earthshine
        ]


def click(aperture: str, speed: str, iso: int, bracketing: Bracketing):
    cmd = f"gphoto2 --set-config-value {Config.Aperture}={aperture} --set-config-value {Config.ShutterSpeed}={speed} --set-config-value {Config.ISO}={iso} --set-config {Config.Bracketing}={bracketing.value} --set-config capturetarget=0 --force-overwrite --filename='Eclipse/t{int(time.time())}_%n' --no-keep --capture-image-and-download"
    if bracketing != Bracketing.OFF:
        cmd += " --capture-image-and-download --capture-image-and-download"
    print(cmd)
    os.system(cmd)

def set_bracketing(bracketing: Bracketing):
    os.system(f"gphoto2 --set-config {Config.Bracketing}={bracketing.value}")


def main():

    def say(text: str): # Thank you ChatGPT
        try:
            say.festival_proc
        except AttributeError:
            say.festival_proc = subprocess.Popen(['festival', '--pipe'], stdin=subprocess.PIPE)
        print(text)
        say.festival_proc.stdin.write(f'(SayText "{text}")\n'.encode())
        say.festival_proc.stdin.flush()

    phase = None
    TIMES = [datetime.datetime(*DATE, *time, 0, datetime.timezone.utc) for time in DEFINE_TIMINGS_UTC]

    if not os.path.isdir('Eclipse/'):
        os.makedirs('Eclipse/')

    if TIMES[0].date() != datetime.datetime.today().date():
        print(f'!!!! Warning: Eclipse does not seem to be today, i.e. {datetime.datetime.today().date()} !!!!')
        say("Warning, eclipse does not seem to be today! Please check!")

    if os.system("gphoto2 --get-config /main/capturesettings/focusmode | grep -q 'Current: Manual'") != 0:
        say("Camera seems to be in auto-focus. Please manually focus. Goodbye!")
        sys.exit(1)

    if os.system("gphoto2 --get-config /main/capturesettings/drivemode | grep -q 'Current: Single'") != 0:
        say("Camera not in single shot drive. Please check that this is intended!")

    say("Please check that the camera is in manual mode")

    now = lambda: datetime.datetime.now(tz=datetime.timezone.utc)
    seconds = lambda x: datetime.timedelta(seconds=x)
    say("Please check the times of the contacts printed")
    for i, t in enumerate(TIMES):
        print(f'{i+1}th contact at {t.ctime()} UTC in {(t - now()).total_seconds()/60.0:0.2f} minutes')

    say('Entering sequence loop')

    C1 = TIMES[0]
    C4 = TIMES[3]
    C2 = TIMES[1]
    C3 = TIMES[2]
    C2_DR = C2 - seconds(DIAMOND_RING)
    C2_BB = C2 - seconds(BAILEYS_BEADS)
    C2_BB2 = C2 + seconds(BAILEYS_BEADS)
    C3_DR = C3 + seconds(DIAMOND_RING)
    C3_BB = C3 + seconds(BAILEYS_BEADS)
    C3_BB2 = C3 - seconds(BAILEYS_BEADS)

    if now() > C4:
        say("It is after fourth contact. Nothing to do. Goodbye!")
        time.sleep(10)
        return

    pbar_c1 = None
    pbar_c2 = None
    pbar_c3 = None
    pbar_c4 = None
    while True:

        try:

            while now() < C1 or now() > C4:
                if now() < C1 and pbar_c1 is None:
                    pbar_c1 = tqdm.tqdm(total=int((C1 - now()).total_seconds()), desc='(Waiting) C1')
                if phase is not None:
                    say('Camera entering resting phase')
                    phase = None
                time.sleep(5) # Long delays are okay
                # Nothing to do
                try:
                    dt = int((C1 - now()).total_seconds())
                    pbar_c1.update(pbar_c1.total - dt - pbar_c1.n)
                except:
                    pass
                if now() > C4:
                    say('Fourth contact over. Exiting program')
                    sys.exit(0)


            c2dr_countdown = set()
            while (now() < C2_DR and now() >= C1) or (now() > C3_DR and now() <= C4):  # Partial phase, C1 to C2 or C3 to C4
                if pbar_c1 is not None:
                    pbar_c1.close()
                if pbar_c3 is not None:
                    pbar_c3.close()

                if pbar_c2 is None and now() < C2_DR:
                    pbar_c2 = tqdm.tqdm(total=int((C2_DR - now()).total_seconds()), desc='(Partial) C2 DR')

                if pbar_c4 is None and now() > C3_DR:
                    pbar_c4 = tqdm.tqdm(total=int((C4 - now()).total_seconds()), desc='(Partial) C4')

                if now() < C2_DR:
                    try:
                        dt = int((C2_DR - now()).total_seconds())
                        pbar_c2.update(pbar_c2.total - dt - pbar_c2.n)
                    except:
                        pass

                if now() > C3_DR:
                    try:
                        dt = int((C4 - now()).total_seconds())
                        pbar_c4.update(pbar_c4.total - dt - pbar_c4.n)
                    except:
                        pass

                time.sleep(0.5)
                if phase != Phases.Partial:
                    say('Camera entering partial phase. Please ensure filter is on!')
                    phase = Phases.Partial
                    set_bracketing(phase.bracketing)
                if int(time.time() % Phases.Partial.interval) == 0:
                    print('Clicking partial phase exposure')
                    click(phase.aperture, phase.speed, phase.iso, bracketing=phase.bracketing)

                dt = int((C2_DR - now()).total_seconds())
                if dt > 0 and dt < 60 and int(dt) % 10 == 0 and int(dt) not in c2dr_countdown:
                    say(f'Prepare camera for filter off in {int(dt)} seconds')
                    c2dr_countdown.add(int(dt))

            while (now() > C2_DR and now() <= C2_BB) or (now() >= C3_BB and now() < C3_DR):
                time.sleep(0.05)
                if phase != Phases.Diamond:
                    say('Camera entering diamond ring phase. Ensure filter is off!')
                    phase = Phases.Diamond
                    set_bracketing(phase.bracketing)
                click(phase.aperture, phase.speed, phase.iso, bracketing=phase.bracketing)

            while (now() > C2_BB and now() <= C2_BB2) or (now() >= C3_BB2 and now() < C3_BB):
                time.sleep(0.05)
                if phase != Phases.Baileys:
                    say('Camera entering Bailey phase. Ensure filter is off!')
                    phase = Phases.Baileys
                    set_bracketing(phase.bracketing)
                click(phase.aperture, phase.speed, phase.iso, bracketing=phase.bracketing)

            while (now() > C2_BB2 and now() < C3_BB2):
                try:
                    if pbar_c3 is None:
                        pbar_c3 = tqdm.tqdm(total=int((C3_BB2 - now()).total_seconds()), desc='(Total) C3')
                    pbar_c3.update(pbar_c3.total - int((C3_BB2 - now()).total_seconds()) - pbar_c3.n)
                except:
                    pass
                time.sleep(0.1)
                if phase != Phases.Totality:
                    say('Camera entering totality! Ensure filter is off!')
                    phase = Phases.Totality
                    set_bracketing(phase.bracketing)
                for exposure in phase.exposures:
                    click(*exposure, bracketing=phase.bracketing)
                dt = (C3_BB2 - now()).total_seconds()
                if dt < 0:
                    continue
                if dt > phase.interval + phase.delay_compensation:
                    time.sleep(phase.interval)
                else:
                    time.sleep(dt + 0.5) # Force entry into Bailey's Beads
        except Exception as e:
            say('Encountered exception!')
            print(e, file=sys.stderr)


if __name__ == "__main__":
    main()
