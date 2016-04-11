#!/usr/bin/python

# wanReset
version = '1.5'
# Clay Michaels
# Feb-2014
#
# To be used to quickly reset a one or more WANs on a target vehicle.
# Kills the WAN process and also does reset-usb.
#
# Usage:
# python wanReset <target CCU> <WAN#>
#
# Example:
# python wanReset.py acela.4 2   (resets WAN 2 on TS04)
# python wanReset.py facebook.198 45 (resets WANs 4 and 5 on 198)

 
import paramiko
import sys
from cStringIO import StringIO
import logging
from logging.handlers import RotatingFileHandler
from time import sleep


# CCU CREDENTIALS
CCU_USER = 'root'
SSH_KEY_NAME = 'helpdesk.ssh'
SSH_KEY = ('''-----BEGIN DSA PRIVATE KEY-----
           <SNIPPED>
          -----END DSA PRIVATE KEY-----''')


# PARSE ARGUMENTS
if len(sys.argv) != 3:
    print('USAGE:')
    print('reset-wan [target CCU] [WAN#]')
    print('Note: [target CCU] must include the fleet prefix, e.g. facebook.198')
    print('Note: [WAN#] must be one or more WAN numbers, e.g. "3" or "46"')
    sys.exit()
else:
    targetCCU = sys.argv[1]
    wan_list = sys.argv[2]


# Set up logging
LOG_FILE = '/var/log/clay/wanReset.log'
#LOG_FILE = 'wanReset.log'
logging.basicConfig(
    filename=LOG_FILE,
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
handler = RotatingFileHandler(LOG_FILE, maxBytes=1000000)
logger.addHandler(handler)


class Connection:
    def __init__(self, target):
        """Connect to CCU and iterate through enabled flags"""
        self.target = target
        self.ccu = paramiko.SSHClient()
        self.key = paramiko.DSSKey.from_private_key(StringIO(SSH_KEY))
        self.ccu.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            logger.info('Creating SSH connection to CCU %s' % self.target)
            self.ccu.connect(self.target, username=CCU_USER, pkey=self.key, timeout=10)
            logger.info('SSH connection successful')
            self.online = True
        except paramiko.BadAuthenticationType:
            logger.error('Error: Bad SSH password or wrong key type.')
            logger.error('Attempted to log in as %s with key %s' % (CCU_USER, SSH_KEY_NAME))
            self.online = False
        except paramiko.SSHException:
            logger.error('SSH Error')
            self.online = False
        except KeyboardInterrupt:
            logger.info('Keyboard interrupt received!')
            exit()
        except:
            logger.info('CCU %s offline' % self.target)
            self.online = False

    def execute_command(self, command, wait):
        """Executes the command. Can be run multiple times."""
        logger.debug('Sending command %s' % command)
        try:
            stdin, stdout, stderr = self.ccu.exec_command(command)
            sleep(wait)
            cmd_out = stdout.read()
            logger.debug('CMD:\n%s' % command)
            logger.debug('STDOUT:\n%s' % cmd_out)
            logger.debug('STDERR:\n%s' % stderr.read())
            return cmd_out
        except KeyboardInterrupt:
            logger.info('Keyboard interrupt received!')
            exit()

    def disconnect(self):
        """Close the Paramiko connection"""
        logger.debug('Closing SSH session')
        self.ccu.close()
        logger.info('SSH session closed')


def main():
    try:
        con = Connection(targetCCU)
        if con.online:
            for wan in wan_list:
                wan_name = ''
                pid = ''
                ps_response = con.execute_command('ps ax | grep " unif"', 1).splitlines()
                iccid = con.execute_command('cat /var/local/unified/0%s/iccid' % wan, 1)
                if not iccid:
                    iccid = 'Not Found!'
                imei = con.execute_command('cat /var/local/unified/0%s/imei' % wan, 1)
                if not imei:
                    imei = 'Not Found!'
                for line in ps_response:
                    if wan in line[-2:]:
                        wan_name = line[27:]
                        pid = line[:5].replace(' ', '')
                print('\nWAN NAME: %s' % (wan_name))
                print('ICCID:    %s' % (iccid))
                print('IMEI:     %s' % (imei))
                if iccid is 'Not Found!' or imei is 'Not Found!':
                    print('Note that it is normal for EVDO and WiMAX WANs not to return ICCID or IMEI.')
                kill_response = con.execute_command('kill %s;/usr/local/bin/reset-usb %s' % (pid, wan), 10)
                logger.debug('Reset-usb response:\n%s' % kill_response)
                if ('Powered up wan%s' % wan) in kill_response:
                    print('-------------------------------------')
                    print('WAN %s killed and reset successfully.' % (wan))
                    logger.info('WAN %s killed and reset successfully.' % (wan))
                else:
                    print('Expected output not seen; confirm success manually.')
                    logger.info('Expected output not seen; confirm success manually.')
            con.disconnect()
    except KeyboardInterrupt:
        logger.error('Keyboard interrupt received!')
        exit()


main()
