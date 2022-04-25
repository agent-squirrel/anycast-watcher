#!/usr/bin/env python3

import socket
import signal
import dns.resolver
import dbus
import time
#from discord_webhook import DiscordWebhook
import systemd.daemon
import os.path
import pygochook

def sigint_handler(signal_received, frame):
        print('SIGINT or CTRL-C detected')
        gchat_hook("SIGINT received, Anycast watcher shutting down!!")
        exit(0)

def sigterm_handler(signal_received, frame):
        print('SIGTERM detected')
        gchat_hook("SIGTERM received, systemd is likely restarting this service, please investigate!!")
        exit(0)

def query(resolver):
        print('Trying to resolve launtel.net.au via the loopback interface')
        query = resolver.resolve('launtel.net.au', 'A')
        for rdata in query: 
            print(rdata)


def gchat_hook(webhook_string):
   hostname = socket.gethostname()
   gchat_webhook_string = hostname + ": " + webhook_string
   webhook = 'https://chat.googleapis.com/v1/spaces/AAAAjWWIYLY/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=W0eUjOi9gvr08EEZaWp2ROVjL3qMBewE5ADxHVw1zys%3D'
   msg_sender = pygochook.MsgSender(gchat_webhook_string, webhook)
   msg_sender.send()

def dns_check_loop(dns_running, manager, sysbus, resolver):
    while dns_running == 0:
        job = manager.RestartUnit('named.service', 'replace')

        service = sysbus.get_object('org.freedesktop.systemd1',
            object_path=manager.GetUnit('named.service'))
        interface = dbus.Interface(service,
            dbus_interface='org.freedesktop.DBus.Properties')
        bind_state = (interface.Get('org.freedesktop.systemd1.Unit', 'ActiveState'))
        time.sleep(3)
        if bind_state == "failed" or bind_state == "activating":
            print('BIND has not restarted, going to sleep for 30 minutes')
            gchat_hook("BIND failed to restart, waiting 30 minutes to try again")
            time.sleep(1800)
        else:
            print('BIND restarted, testing DNS queries')
            try:
                query(resolver)
                print ('Success, nothing to do so going to sleep for 30 seconds')
                gchat_hook("BIND recovered, restarting BGPd")
                dns_running = 1
                return
            except dns.exception.DNSException:
                print('BIND is not resolving, going back to sleep')
                gchat_hook("BIND is operational but not resolving, sleeping")
                time.sleep(1800)
def main():
    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGTERM, sigterm_handler)
    dns_running = 1
    
    sysbus = dbus.SystemBus()
    systemd1 = sysbus.get_object('org.freedesktop.systemd1', '/org/freedesktop/systemd1')
    manager = dbus.Interface(systemd1, 'org.freedesktop.systemd1.Manager')
    
    resolver = dns.resolver.Resolver(configure=False)
    resolver.timeout = 3
    resolver.lifetime = 3
    resolver.nameservers=['127.0.0.1']
    print ('Anycast watcher coming online')
    gchat_hook('Anycast watcher coming online')
    systemd.daemon.notify('READY=1')
    while True:
        if not os.path.isfile('/etc/systemd/system/multi-user.target.wants/bgpd.service'):
            print('BGPd not installed or not enabled, sleeping for 30 minutes')
            time.sleep(1800)
            continue
        service = sysbus.get_object('org.freedesktop.systemd1',
            object_path=manager.GetUnit('bgpd.service'))
        interface = dbus.Interface(service,
            dbus_interface='org.freedesktop.DBus.Properties')
        bgpd_state = (interface.Get('org.freedesktop.systemd1.Unit', 'ActiveState'))
        if bgpd_state == "failed" or bgpd_state == "activating" or bgpd_state == "inactive":
            print('BGPd not running, sleeping for 5 minutes')
            time.sleep(300)
            continue
        try: 
            query(resolver)
            print ('Success, nothing to do so going to sleep for 30 seconds')
            time.sleep(30)
        except dns.exception.DNSException:
            dns_running = 0
            print('launtel.net.au did not resolve via loopback, killing bgpd')
            gchat_hook("DNS SERVFAIL has occurred. Taking BGP down and attempting restart of BIND")
            job = manager.StopUnit('bgpd.service', 'replace')
            gchat_hook("BGPd stopped")
            print('BGPd stopped and now attempting restart of BIND')
            dns_check_loop(dns_running, manager, sysbus, resolver)
            job = manager.StartUnit('bgpd.service', 'replace')
            gchat_hook("Restarted BGPd successfully")
            print("Restarted BGPd successfully")
            time.sleep(30)
        
if __name__ == '__main__':
	main()
