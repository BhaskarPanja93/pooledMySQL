__version__ = "4.0.0"
__packagename__ = "pooledmysql"


def updatePackage():
    from time import sleep
    from json import loads
    import http.client
    print(f"Checking updates for Package {__packagename__}")
    try:
        host = "pypi.org"
        conn = http.client.HTTPSConnection(host, 443)
        conn.request("GET", f"/pypi/{__packagename__}/json")
        data = loads(conn.getresponse().read())
        latest = data['info']['version']
        if latest != __version__:
            try:
                import subprocess
                from pip._internal.utils.entrypoints import (
                    get_best_invocation_for_this_pip,
                    get_best_invocation_for_this_python,
                )
                from pip._internal.utils.compat import WINDOWS
                if WINDOWS:
                    pip_cmd = f"{get_best_invocation_for_this_python()} -m pip"
                else:
                    pip_cmd = get_best_invocation_for_this_pip()
                subprocess.run(f"{pip_cmd} install {__packagename__} --upgrade")
                print(f"\nUpdated package {__packagename__} v{__version__} to v{latest}\nPlease restart the program for changes to take effect")
                sleep(3)
            except:
                print(f"\nFailed to update package {__packagename__} v{__version__} (Latest: v{latest})\nPlease consider using pip install {__packagename__} --upgrade")
                sleep(3)
        else:
            print(f"Package {__packagename__} already the latest version")
    except:
        print(f"Ignoring version check for {__packagename__} (Failed)")


class Imports:
    from time import sleep, time
    from threading import Thread
    from customisedLogs import CustomisedLogs
    import mysql.connector as MySQLConnector
    from mysql.connector.abstracts import MySQLConnectionAbstract
    from typing import Any


class PooledMySQL:
    def __init__(self, user:str, password:str, dbName:str, host:str="127.0.0.1", port:int=3306, closeConnectionOnIdle:bool=True, logOnTerminal:bool|int=True):
        """
        Initialise the PooledMySQL and use the execute() functions to use the MySQL connection pool for executing MySQL queries
        :param user: Username to log in to the DB with
        :param password: Password for the username provided
        :param dbName: DataBase name to connect to
        :param host: Server hostname or IP address
        :param port: Port on which the server is connected to
        :param logOnTerminal: Boolean if logging is needed on terminal, Integer to provide verbosity of logging
        """
        self.__connections:list[PooledMySQL.__connectionWrapper] = []
        self.__logger = Imports.CustomisedLogs((0 if not logOnTerminal else 100) if type(logOnTerminal)==bool else logOnTerminal)
        self.__password = password
        self.user = user
        self.dbName = dbName
        self.host = host
        self.port = port
        self.closeConnectionOnIdle = closeConnectionOnIdle


    def __removeConnCallback(self, connection):
        """
        Callback to remove a connection object from available list (Called from the object itself)
        :param connection: Connection who calls to be removed from list
        :return:
        """
        if connection in self.__connections:
            _old = len(self.__connections)
            self.__connections.remove(connection)
            _new = len(self.__connections)
            self.__logger.log(self.__logger.Colors.red_100_accent, "POOL-CONN", f"conn-{connection.id} closed (#Current: {_old}->{_new})")


    def execute(self, statement:str, params:list=None, dbRequired:bool=True, catchErrors:bool=True)-> None | list[dict[str, Imports.Any]]:
        """
        :param statement: Statement to execute
        :param params: Parameters (if any) to pass to the statement to form prepared statement
        :param dbRequired: Boolean specifying if the syntax is supposed to be executed on the database or not. A database creation syntax doesn't need the database to be already present, so the argument should be False for those cases
        :param catchErrors: If errors are supposed to be caught promptly or sent to the main thread
        :return: None or list of tuples depending on the syntax passed
        """
        _destroyAfterUse = False
        _appendAfterUse = False
        _connectionFound = False
        while not _connectionFound:
            connObj = None
            data = None
            try:
                if not dbRequired:
                    connObj = self.__connectionWrapper(Imports.MySQLConnector.connect(user=self.user, host=self.host, port=self.port, password=self.__password, autocommit=True), self.closeConnectionOnIdle, self.__removeConnCallback, self.__logger)
                    self.__logger.log(self.__logger.Colors.light_green_400, "POOL-CONN", f"New DB-LESS Connection conn-{connObj.id}")
                    _destroyAfterUse = True
                    _connectionFound = True
                elif len(self.__connections)!=0:
                    for connObj in self.__connections:
                        if connObj.idle:
                            self.__logger.log(self.__logger.Colors.blue_grey_600, "POOL-CONN", f"conn-{connObj.id} reused (#Current: {len(self.__connections)})")
                            _connectionFound = True
                            break
                if not _connectionFound:
                    connObj = self.__connectionWrapper(Imports.MySQLConnector.connect(user=self.user, host=self.host, port=self.port, password=self.__password, database=self.dbName, autocommit=True), self.closeConnectionOnIdle, self.__removeConnCallback, self.__logger)
                    self.__logger.log(self.__logger.Colors.light_green_400, "POOL-CONN", f"New Connection conn-{connObj.id}")
                    _appendAfterUse = True
                    _connectionFound = True
                try:
                    if params is None: params = []
                    data = connObj.internalExecute(statement, params)
                    if data is None:
                        continue
                except Exception as e:
                    data = None
                    self.__logger.log(self.__logger.Colors.red_900, "POOL-EXEC", repr(e), f"\n{{{statement}}}" , tuple(params))
                    if not catchErrors:
                        raise e
            except Exception as e:
                self.__logger.log(self.__logger.Colors.red_700_accent, "POOL-CONN", repr(e))
                if not catchErrors:
                    raise e
                Imports.sleep(0.5)
            finally:
                if _destroyAfterUse:
                    connObj.__safeDeleteConnection()
                elif _appendAfterUse:
                    _old = len(self.__connections)
                    self.__connections.append(connObj)
                    _new = len(self.__connections)
                    self.__logger.log(self.__logger.Colors.light_green_700_accent, "POOL-CONN", f"conn-{connObj.id} saved (#Current: {_old}->{_new})")
                return data


    class __connectionWrapper:
        def __init__(self, connection:Imports.MySQLConnector.pooling.PooledMySQLConnection|Imports.MySQLConnectionAbstract, closeConnectionOnIdle, cleanupCallback, logger:Imports.CustomisedLogs):
            self.id = connection.connection_id
            self.idle = True
            self.alive = True
            self.closeOnIdle = closeConnectionOnIdle
            self.maxIdlePeriod = 5
            self.raw = connection
            self.lastUsed = Imports.time()
            self.logger = logger
            self.cleanupCallback = cleanupCallback


        def __pinger(self):
            """
            If connection object is alive, recursively ping after every fixed interval
            Makes sure there is only one ping function running per connection
            """
            Imports.sleep(self.maxIdlePeriod)
            if self.alive and self.idle and self.lastUsed + self.maxIdlePeriod < Imports.time():
                try:
                    self.idle = False
                    self.raw.ping(True, 1, 1)
                    self.logger.log(self.logger.Colors.grey_400, "POOL-IDLE", f"conn-{self.id} pinged")
                    self.idle = True
                    self.__pinger()
                except Imports.MySQLConnector.InterfaceError:
                    self.logger.log(self.logger.Colors.amber_700, "POOL-IDLE", f"conn-{self.id} Ping Failed")
                    self.__safeDeleteConnection()


        def __killer(self):
            """
            If connection object is alive, kill connection on n seconds of idling
            Makes sure there is only one kill function running per connection
            """
            Imports.sleep(self.maxIdlePeriod)
            if self.alive and self.idle and self.lastUsed + self.maxIdlePeriod < Imports.time():
                self.logger.log(self.logger.Colors.yellow_300, "POOL-IDLE", f"conn-{self.id} idled")
                self.__safeDeleteConnection()


        def __safeDeleteConnection(self):
            """
            Safely close raw connection and cleanup itself
            :return:
            """
            if self.alive:
                self.alive = False
                self.cleanupCallback(self)
                self.raw.disconnect()
                self.raw.close()


        def internalExecute(self, operation: str, params:list)->None|list[dict[str, Imports.Any]]:
            """
            Internally execute a MySQL syntax
            :param operation: Main string to be executed
            :param params:
            :return:
            """
            error = None
            data = None
            start = Imports.time()
            while self.alive and not self.idle and Imports.time() - start < 4: Imports.sleep(0.1)
            if not self.alive: return None
            self.idle = False
            try:
                self.raw.consume_results()
                cursor = self.raw.cursor(dictionary=True, prepared=True)
                cursor.execute(operation, params)
                data = cursor.fetchall()
            except Exception as e:
                error = e
            self.lastUsed = Imports.time()
            self.idle = True
            if self.closeOnIdle: Imports.Thread(target=self.__killer).start()
            else: Imports.Thread(target=self.__pinger).start()
            if error: raise error
            return data
