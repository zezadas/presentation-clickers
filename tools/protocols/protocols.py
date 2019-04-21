from enum import Enum

class Protocols(Enum):
  HS304 = 'hs304'
  AmazonBasics = 'amazon'
  Canon = 'canon'
  TBBSC = 'tbbsc'
  RII = 'rii'
  Logitech = 'logitech'
  def __str__(self):
    return self.value