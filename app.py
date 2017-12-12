# -*- coding: utf-8 -*-
import os
from config import Config
from flask import Flask
from flask_ask import Ask, request, session, question, statement
from werkzeug.contrib.fixers import ProxyFix
from unidecode import unidecode
import logging
from sl import SL

try:
    from urllib.parse import quote_plus
except:
    from urllib import quote_plus

config = Config()

app = Flask(__name__)
ask = Ask(app, "/")
logging.getLogger('flask_ask').setLevel(logging.DEBUG)
sl = SL(os.environ['SL_API_KEY'])
tts_host = os.environ.get('TTS_HOST')

def get_site_id(transporatation):
    return os.environ.get('SL_%s_SITE_ID' % transporatation.upper())


@ask.launch
def launch():
    speech_text = 'Bus or Metro?'
    return question(speech_text).reprompt(speech_text).simple_card('SL', speech_text)


@ask.intent('SLRealTimeCityIntent')
def real_time_city(transportation):
    sl.reset_filter()
    if transportation in ('metro', 'subway'):
        sl.metro = True
        sl.journey_direction = 1
        sl.site_id = get_site_id('metro')
    else:
        speech_text = "I only support metro with this quetion"
        return statement(speech_text).simple_card('SL', speech_text)

    return _generate_answer(transportation)


@ask.intent('SLRealTimeIntent')
def real_time(transportation):
    sl.reset_filter()
    if transportation in ('metro', 'subway'):
        sl.metro = True
        sl.site_id = get_site_id('metro')
    elif transportation == 'bus':
        sl.bus = True
        sl.site_id = get_site_id('bus') 
    elif transportation == 'train':
        sl.train = True
        sl.site_id = get_site_id('metro') 
    else:
        speech_text = "Sorry I didn't catch what you asked for there, which transporatation did you want to go with. Bus or Metro?"
        return question(speech_text).reprompt(speech_text).simple_card('SL', speech_text)

    return _generate_answer(transportation)


@ask.intent('SLDeviationIntent')
def deviation(transportation):
    sl.reset_filter()
    if transportation in ('metro', 'subway'):
        sl.metro = True
        sl.site_id = get_site_id('metro')
    elif transportation == 'bus':
        sl.bus = True
        sl.site_id = get_site_id('bus') 
    elif transportation == 'train':
        sl.train = True
        sl.site_id = get_site_id('metro') 
    else:
        speech_text = "Sorry I didn't catch which transportation you wanted there."
        return statement(speech_text).simple_card('SL', speech_text)

    result, deviations = sl.simple_list()
    speech_text, card_text = _generate_deviation(deviations)

    speech_text = '<speak>' + speech_text + '</speak>'

    return statement(speech_text).simple_card('SL', card_text)


def _generate_deviation(deviations):
    speech_reply =  []
    card_reply =  []
    if deviations and tts_host:
        for d in deviations:
            deviation = quote_plus(d['Deviation']['Text'].encode('utf-8'))
            speech_reply.append('<s>%s <audio src="%s%s"/></s>' % (d['StopInfo']['TransportMode'].capitalize(),
                                                            tts_host, deviation))
            card_reply.append('%s - %s' % (d['StopInfo']['TransportMode'].capitalize(), d['Deviation']['Text']))
    elif deviations and not tts_host:
        speech_reply.append('<s>There are some deviations right now.</s>')
        for d in deviations:
            deviation = quote_plus(d['Deviation']['Text'].encode('utf-8'))
            card_reply.append('%s - %s' % (d['StopInfo']['TransportMode'].capitalize(), d['Deviation']['Text']))
    else:
        speech_reply.append(u'<s>There are no known deviations right now</s>')
        card_reply = speech_reply

    speech_text = ''.join(speech_reply)
    card_text = '\n'.join(card_reply)

    return speech_text, card_text


def _generate_answer(transportation):
    result, deviations = sl.simple_list()
    speech_reply =  []
    card_reply =  []

    if deviations:
        st, ct = _generate_deviation(deviations)
        speech_reply.append(st)
        card_reply.append(ct)

    if not result:
        speech_reply.append(u'<s>I can not find any departures with the %s</s>' % transportation)
        card_reply = speech_reply

        speech_text = ''.join(speech_reply)
        speech_text = '<speak>' + speech_text + '</speak>'
        card_text = '\n'.join(card_reply)

        return statement(speech_text).simple_card('SL', card_text)

    for r in result:
        r['transportation'] = transportation
        if tts_host:
            destination = quote_plus(r['destination'].encode('utf-8'))
            r['speech_destination'] = '<audio src="%s%s"/>' % (tts_host, destination) 
        else:
            r['speech_destination'] = r['destination']
        if transportation == 'bus':
            r['speech_destination'] = '%(line_number)s to ' % r + r['speech_destination']
        else:
            r['speech_destination'] = r['speech_destination']

        cnt = len(speech_reply)
        if deviations:
            cnt -= 1
        if cnt < 3:
            if cnt == 0:
                speech_reply.append(u'<s>The next %(transportation)s %(speech_destination)s will depart %(time_left)s</s>' % r)
            if cnt == 1:
                speech_reply.append(u'<s>Followed by %(speech_destination)s %(time_left)s</s>' % r)
            if cnt > 1:
                speech_reply.append(u'<s>%(speech_destination)s %(time_left)s</s>' % r)

            card_reply.append(u'%(transport_type)s %(line_number)s to %(destination)s will depart %(time_left)s.' % r)

    speech_text = ''.join(speech_reply)
    speech_text = '<speak>' + speech_text + '</speak>'
    card_text = '\n'.join(card_reply)
    return statement(unidecode(speech_text)).simple_card('Next %s' % transportation, card_text)


@ask.intent('AMAZON.HelpIntent')
def help():
    speech_text = 'You can ask me when the bus or subway goes. For example, When does the next bus go?'
    return question(speech_text).reprompt(speech_text).simple_card('SL', speech_text)


@ask.session_ended
def session_ended():
    return "", 200


if __name__ == '__main__':
    # Be sure to set config.debug_mode to False in production
    port = int(os.environ.get("PORT", config.port))
    if port != config.port:
        config.debug = False
    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.run(host='0.0.0.0', debug=config.debug_mode, port=port)
