import textwrap
from .races import races
from . import languagetools as lang


"""
object hierarchy:

MudObject
  |
  +-- Location
  |
  +-- Thing
  |     |
  |     +-- Item
  |           |
  |           +-- Weapon
  |           +-- Armour
  |           +-- Bag
  |
  +-- Living
  |     |
  |     +-- Player
  |     +-- NPC
  |          |
  |          +-- Monster


Exit
ExitStub
Effect

"""


class MudObject(object):
    """
    Root class of all objects in the mud world
    All objects have an identifying short name,
    an optional short title (shown when listed in a room),
    and an optional longer description (shown when explicitly 'examined').
    The long description is 'dedented' first, which means you can put it between triple-quoted-strings easily.
    """
    def __init__(self, name, title=None, description=None):
        self.name = name
        self.title = title or name
        self.description = textwrap.dedent(description).strip() if description else ""

    def __repr__(self):
        return "<%s.%s '%s' @ %s>" % (self.__class__.__module__, self.__class__.__name__, self.name, hex(id(self)))


class Item(MudObject):
    """
    Root class of all Items in the mud world. Items are physical objects.
    Items can usually be moved, carried, or put inside other items.
    They have a name and optional short and longer descriptions.
    """
    def __init__(self, name, title=None, description=None):
        super(Item, self).__init__(name, title, description)


class Weapon(Item):
    """
    An item that can be wielded by a Living (i.e. present in a weapon itemslot),
    and that can be used to attack another Living.
    """
    def __init__(self, name, title=None, description=None):
        super(Weapon, self).__init__(name, title, description)


class Armour(Item):
    """
    An item that can be worn by a Living (i.e. present in an armour itemslot)
    """
    def __init__(self, name, title=None, description=None):
        super(Armour, self).__init__(name, title, description)


class Location(MudObject):
    """
    A location in the mud world. Livings and Items are in it.
    Has connections ('exits') to other Locations.
    """
    def __init__(self, name, description=None):
        super(Location, self).__init__(name, description=description)
        self.livings = set()  # set of livings in this location
        self.items = set()    # set of all items in the room
        self.exits = {}       # dictionary of all exits: exit_direction -> Exit object with target & descr

    def tell(self, room_msg, exclude_living=None, specific_targets=None, specific_target_msg=""):
        """
        Tells something to the livings in the room (excluding the living from exclude_living).
        This is just the message string! If you want to react on events, consider not doing
        that based on this message string. That will make it quite hard because you need to
        parse the string again to figure out what happened...
        """
        specific_targets = specific_targets or set()
        for living in self.livings:
            if living == exclude_living:
                continue
            if living in specific_targets:
                living.tell(specific_target_msg)
            else:
                living.tell(room_msg)

    def look(self, exclude_living=None, short=False):
        """returns a string describing the surroundings, possibly excluding one living from the description list"""
        r = ["[" + self.name + "]"]
        if self.description:
            if not short:
                r.append(self.description)
        if self.items:
            if short:
                item_names = sorted(item.name for item in self.items)
                r.append("You see: " + ", ".join(item_names))
            else:
                titles = sorted(item.title for item in self.items)
                titles = [lang.a(title) for title in titles]
                r.append("You see " + lang.join(titles) + ".")
        if self.exits:
            # r.append("You can see the following exits:")
            if short:
                r.append("Exits: " + ", ".join(sorted(set(self.exits.keys()))))
            else:
                exits_seen = set()
                for exit_name in sorted(self.exits):
                    exit = self.exits[exit_name]
                    if exit not in exits_seen:
                        exits_seen.add(exit)
                        r.append(exit.description)
        if self.livings:
            if short:
                living_names = sorted(living.name for living in self.livings if living != exclude_living)
                if living_names:
                    r.append("Present: " + ", ".join(living_names))
            else:
                titles = sorted(living.title for living in self.livings if living != exclude_living)
                if titles:
                    titles = lang.join(titles)
                    if len(self.livings) > 1:
                        titles += " are here."
                    else:
                        titles += " is here."
                    r.append(lang.capital(titles))
        return "\n".join(r)

    def search_living(self, name, suggest=False):   # @todo: unittest for suggest
        """
        Search for a living in this location by its name (and title, if no names match)
        If there's more than one match, returns the first
        """
        name = name.lower()
        result = [living for living in self.livings if living.name == name]
        if not result:
            result = [living for living in self.livings if living.title.lower() == name]
        return result[0] if result else None

    def enter(self, object):
        self.livings.add(object)

    def leave(self, object):
        if object in self.livings:
            self.livings.remove(object)

    def add_item(self, item):
        self.items.add(item)

    def remove_item(self, item):
        self.items.remove(item)


class Exit(object):
    """
    An 'exit' that connects one location to another.
    """
    def __init__(self, target_location, description):
        if type(target_location) is not Location:
            raise TypeError("target of Exit must be a Location")
        self.target = target_location
        self.description = description


class ExitStub(object):
    """
    An 'exit' that connects one location to another.
    This one is a stub in the sense that the target location is not
    the actual location, but a string path to it so that it can be
    retrieved at runtime.
    """
    def __init__(self, target_location_name, description):
        if type(target_location_name) is not str:
            raise TypeError("target of ExitStub must be a str")
        self.target = target_location_name
        self.description = description


class Living(MudObject):
    """
    Root class of the living entities in the mud world.
    Livings tend to have a heart beat 'tick' that makes them interact with the world (or a callback).
    They are always inside a Location (Limbo when not specified yet).
    They also have an inventory object.
    """
    __Limbo = Location("Limbo", "The intermediate or transitional place or state. Livings end up here if they're not inside a proper location yet.")

    def __init__(self, name, gender, title=None, description=None, race=None):
        super(Living, self).__init__(name, title, description)
        self.gender = gender
        self.subjective = lang.SUBJECTIVE[self.gender]
        self.possessive = lang.POSSESSIVE[self.gender]
        self.objective = lang.OBJECTIVE[self.gender]
        self.location = Living.__Limbo  # set transitional location
        self.race = None
        self.stats = {}
        if race:
            self.set_race(race)
        self.inventory = set()

    def set_race(self, race):
        """set the race for this Living and copy the initial set of stats from that race"""
        self.race = race
        # Make a copy of the race stats, because they can change dynamically.
        # There's no need to copy the whole race data dict because it's available
        # from mudlib.races, look it up by the race name.
        self.stats = {}
        for stat_name, (stat_avg, stat_class) in races[race]["stats"].items():
            self.stats[stat_name] = stat_avg

    def tell(self, *messages):
        """
        Every living thing in the mud can receive one or more action messages.
        For players this is usually printed to their screen, but for all other
        livings the default is to do nothing.
        They could react on it but this is not advisable because you will need
        to parse the string again to figure out what happened...
        """
        pass

    def move(self, target_location):
        """leave the current location, enter the new location"""
        if self.location:
            self.location.leave(self)
        target_location.enter(self)
        self.location = target_location

    def search_item(self, name, include_inventory=True, include_location=True, suggest=False):     # @todo: unittest
        """
        Searches an item within the 'visible' world around the living including his inventory.
        If there's more than one hit, just return the first.
        """
        name = name.lower()
        matches = None
        if include_inventory:
            matches = [item for item in self.inventory if item.name == name] or \
                      [item for item in self.inventory if item.title.lower() == name]
        if not matches and include_location:
            matches = [item for item in self.location.items if item.name == name] or \
                      [item for item in self.location.items if item.title.lower() == name]
        return matches[0] if matches else None

    def search_name(self, name, suggest=False):    # @todo: unittest
        """
        Searches an object within the 'visible' world around the living including his inventory.
        If there's more than one hit, just return the first.
        """
        name = name.lower()
        if self.name == name or self.title.lower() == name:
            return self
        return self.search_item(name, suggest=suggest) or self.location.search_living(name, suggest) or None


class Bag(Item):
    """
    A bag-type container (i.e. an item that acts as a container)
    """
    def __init__(self, name, title=None, description=None):
        super(Bag, self).__init__(name, title, description)
        self.contents = set()


class Effect(object):
    """
    An abstract effect or alteration that is present on or in another object.
    This could be a curse or buff, or some other spell effect such as darkness.
    """
    def __init__(self, name, description=None):
        self.name = name
        self.description = description
