def number_to_hindi_words(n: float | int) -> str:
    """
    Convert a number into Hindi words (e.g. 5000 -> paanch hazaar).
    Supports up to 99,99,999 (99 Lakhs) for POC.
    """
    n = int(n)
    if n == 0:
        return "shunya"

    # Pre-defined mapping for 1-99 due to Hindi irregularities
    hindi_1_to_99 = {
        1: 'ek', 2: 'do', 3: 'teen', 4: 'chaar', 5: 'paanch', 6: 'chhe', 7: 'saat', 8: 'aath', 9: 'nau', 10: 'das',
        11: 'gyarah', 12: 'barah', 13: 'terah', 14: 'chaudah', 15: 'pandrah', 16: 'solah', 17: 'satrah', 18: 'atharah', 19: 'unnis', 20: 'bees',
        21: 'ikkis', 22: 'bais', 23: 'teis', 24: 'chaubis', 25: 'pachis', 26: 'chhabis', 27: 'sattais', 28: 'athais', 29: 'unnatis', 30: 'tees',
        31: 'ikatis', 32: 'battis', 33: 'taitis', 34: 'chautis', 35: 'paintis', 36: 'chhattis', 37: 'saintis', 38: 'adatis', 39: 'untalis', 40: 'chalis',
        41: 'iktalis', 42: 'bayalis', 43: 'taitalis', 44: 'chavalis', 45: 'paintalis', 46: 'chiyalis', 47: 'saintalis', 48: 'adatalis', 49: 'unachas', 50: 'pachaas',
        51: 'ikyavan', 52: 'baavan', 53: 'tirpan', 54: 'chauvan', 55: 'pachpan', 56: 'chhappan', 57: 'satavan', 58: 'athavan', 59: 'unsath', 60: 'saath',
        61: 'iksath', 62: 'basath', 63: 'tirsath', 64: 'chausath', 65: 'painsath', 66: 'chhiyasath', 67: 'sarsath', 68: 'arsath', 69: 'unhattar', 70: 'sattar',
        71: 'ikhattar', 72: 'bahattar', 73: 'tihattar', 74: 'chauhattar', 75: 'pachhattar', 76: 'chhihattar', 77: 'satahattar', 78: 'athahattar', 79: 'unnasi', 80: 'assi',
        81: 'ikyasi', 82: 'bayasi', 83: 'tirasi', 84: 'chaurasi', 85: 'pachasi', 86: 'chhiyasi', 87: 'satasi', 88: 'athasi', 89: 'navasi', 90: 'nabbe',
        91: 'ikyanve', 92: 'banve', 93: 'tiranve', 94: 'chauranve', 95: 'pachanve', 96: 'chhiyanve', 97: 'sattanve', 98: 'atthanve', 99: 'ninyanve'
    }

    words = []

    # Lakhs
    if n >= 100000:
        lakhs = n // 100000
        words.append(hindi_1_to_99.get(lakhs, str(lakhs)))
        words.append("lakh")
        n %= 100000

    # Thousands
    if n >= 1000:
        thousands = n // 1000
        words.append(hindi_1_to_99.get(thousands, str(thousands)))
        words.append("hazaar")
        n %= 1000

    # Hundreds
    if n >= 100:
        hundreds = n // 100
        words.append(hindi_1_to_99.get(hundreds, str(hundreds)))
        words.append("sau")
        n %= 100

    # Tens and Ones
    if n > 0:
        words.append(hindi_1_to_99.get(n, str(n)))

    return " ".join(words)
