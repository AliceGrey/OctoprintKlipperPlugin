
def key_exist(dict, key1, key2):
        try:
            dict[key1][key2]
        except KeyError:
            return False
        else:
            return True
