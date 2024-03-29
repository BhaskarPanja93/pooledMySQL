__version__ = "2.4.0"
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
                import pip
                pip.main(["install", __packagename__, "--upgrade"])
                print(f"\nUpdated package {__packagename__} v{__version__} to v{latest}\nPlease restart the program for changes to take effect")
                sleep(3)
            except:
                print(f"\nFailed to update package {__packagename__} v{__version__} (Latest: v{latest})\nPlease consider using pip install {__packagename__} --upgrade")
                sleep(3)
        else:
            print(f"Package {__packagename__} already the latest version")
    except:
        print(f"Ignoring version check for {__packagename__} (Failed)")


class Manager:
    def __init__(self, user:str, password:str, dbName:str, host:str="127.0.0.1", port:int=3306, logFile=None):
        """
        Initialise the Manager and use the execute() functions to use the MySQL connection pool for executing MySQL queries
        :param user: Username to log in to the DB with
        :param password: Password for the username provided
        :param dbName: DataBase name to connect to
        :param host: Server hostname or IP address
        :param port: Port on which the server is connected to
        :param logFile: Filename to log errors to, pass None to turn off file logging
        """
        from time import sleep as __sleep
        import mysql.connector as __mysqlConnector
        import customisedLogs as __customisedLogs
        self.__sleep = __sleep
        self.__mysqlConnector = __mysqlConnector
        self.__customisedLogs = __customisedLogs
        self.__connections:list[Manager.__connectionWrapper] = []
        self.__logger = self.__customisedLogs.Manager()
        self.__password = password
        self.user = user
        self.dbName = dbName
        self.host = host
        self.port = port
        self.logFile = logFile


    def __removeConnCallback(self, connection):
        """
        Callback to remove a connection object from available list (Called from the object itself)
        :param connection: Connection who calls to be removed from list
        :return:
        """
        if connection in self.__connections:
            self.__connections.remove(connection)
            self.__logger.info("MYSQL-POOL", "CLOSE", f"Total Connections: {len(self.__connections)}")


    def checkDatabaseStructure(self):
        """
        Override this function and implement code to check and create the database and the corresponding tables (if needed).

        Example code to create the database:
        if not self.run(f"SHOW DATABASES LIKE \"{self.db_name}\"", commit_required=False, database_required=False):
            self.execute(f"CREATE database {self.dbName};", database_required=False, commit_required=False)

        Example code to create a sample table:
        table_name = "song_data"
        if not self.run(f"SHOW TABLES LIKE \"{table_name}\"", commit_required=False):
            self.execute(f'''
                       CREATE TABLE IF NOT EXISTS `{self.db_name}`.`{table_name}` (
                       `_id` VARCHAR(100) NOT NULL,
                       `duration` INT ZEROFILL NULL,
                       `thumbnail` VARCHAR(100) NULL,
                       `audio_url` VARCHAR(2000) NULL,
                       `audio_url_created_at` TIMESTAMP NULL,
                       PRIMARY KEY (`_id`),
                       UNIQUE INDEX `_id_UNIQUE` (`_id` ASC) VISIBLE)
                       ''', commit_required=True))
        """
        pass


    def defaultErrorWriter(self, category:str="", text:str="", extras:str="", ignoreLog:bool=False):
        """
        Default function to write MySQL logs to terminal and logfile
        :param category: Category of the error
        :param text: Main text of the error
        :param extras: Additional text
        :param ignoreLog: Boolean specifying if logging for current execution be ignored from log file
        """
        logString = self.__logger.fatal("MYSQL-POOL", category, text, extras)
        if not ignoreLog and self.logFile: open(self.logFile, "a").write(logString + "\n")


    def execute(self, syntax:str, catchErrors:bool=False, logIntoFile:bool=True, dbRequired:bool=True)-> None | list:
        """
        :param syntax: The MySQL syntax to execute
        :param catchErrors: If errors are supposed to be caught promptly or sent to the main application
        :param logIntoFile: Bool to say if logging into file is needed for this syntax. Skipped if ignoreErrors is set to False
        :param dbRequired: Boolean specifying if the syntax is supposed to be executed on the database or not. A database creation syntax doesn't need the database to be already present, so the argument should be False for those cases
        :return: None or list of tuples depending on the syntax passed
        """
        _destroyAfterUse = False
        _appendAfterUse = False
        _newNeeded = False
        _connectionFound = False
        while not _connectionFound:
            try:
                if not dbRequired:
                    connObj = self.__connectionWrapper(self.__mysqlConnector.connect(user=self.user, host=self.host, port=self.port, password=self.__password, autocommit=True), self.__removeConnCallback, self.__logger)
                    self.__logger.info("MYSQL-POOL", "NEW", "New DB-LESS Connection")
                    _destroyAfterUse = True
                    _connectionFound = True
                elif self.__connections and not _newNeeded:
                    for connObj in self.__connections:
                        if connObj.idle:
                            self.__logger.info("MYSQL-POOL", "REUSE", f"Total Connections: {len(self.__connections)}")
                            _connectionFound = True
                            break
                    else:
                        _newNeeded = True
                else:
                    connObj = self.__connectionWrapper(self.__mysqlConnector.connect(user=self.user, host=self.host, port=self.port, password=self.__password, database=self.dbName, autocommit=True), self.__removeConnCallback, self.__logger)
                    _appendAfterUse = True
                    _connectionFound = True
            except Exception as e:
                self.defaultErrorWriter("CONNECTION FAIL", repr(e))
                if not catchErrors:
                    raise e
                self.__sleep(0.5)
        try:
            data = connObj.execute(syntax)
        except Exception as e:
            data = None
            if not catchErrors:
                self.defaultErrorWriter("EXECUTION FAIL", repr(e), syntax, ignoreLog=not logIntoFile)
                raise e
        if _destroyAfterUse: connObj.safeDeleteConnection()
        elif _appendAfterUse:
            _old = len(self.__connections)
            self.__connections.append(connObj)
            _new = len(self.__connections)
            self.__logger.info("MYSQL-POOL", "NEW", f"Total Connections: {_old}->{_new}")
        return data

    class __connectionWrapper:
        import mysql.connector as __mysqlConnector
        from mysql.connector.pooling import PooledMySQLConnection
        from mysql.connector.abstracts import MySQLConnectionAbstract
        from customisedLogs import Manager as LogManager
        def __init__(self, connection:PooledMySQLConnection|MySQLConnectionAbstract, cleanupCallback, logger:LogManager):
            from time import time as __time, sleep as __sleep
            from threading import Thread as __Thread
            self.__time = __time
            self.__sleep = __sleep
            self.__Thread = __Thread
            self.idle = True
            self.alive = True
            self.sendKeepAliveAfter = 15
            self.raw = connection
            self.lastUsed = self.__time()
            self.logger = logger
            self.cleanupCallback = cleanupCallback
            self.__Thread(target=self.__pinger).start()


        def __pinger(self):
            """
            While connection object is alive, keep pinging after every fixed interval
            :return:
            """
            while self.alive:
                while True:
                    timeUntilNextHeartbeat = self.sendKeepAliveAfter - (self.__time() - self.lastUsed)
                    if timeUntilNextHeartbeat>0:
                        self.logger.skip("PING", f"Waiting {int(timeUntilNextHeartbeat)} secs")
                        self.__sleep(timeUntilNextHeartbeat)
                    else: break
                self.idle = False
                try:
                    self.raw.ping(True, 1, 1)
                    self.lastUsed = self.__time()
                    self.logger.skip("PING", f"Success")
                except self.__mysqlConnector.InterfaceError:
                    self.logger.skip("PING", f"Failed")
                    self.safeDeleteConnection()
                self.idle = True
            self.safeDeleteConnection()


        def safeDeleteConnection(self):
            """
            Safely close and cleanup itself
            :return:
            """
            self.alive = False
            self.cleanupCallback(self)
            self.raw.disconnect()
            self.raw.close()


        def execute(self, syntax:str):
            """
            Internally execute a MySQL syntax
            :param syntax: Syntax to execute
            :return:
            """
            start = self.__time()
            while not self.idle and self.__time()-start<4:
                self.__sleep(1)
            if self.__time()-start>=4:
                raise self.__mysqlConnector.InterfaceError("Couldn't Idle Connection")
            self.idle = False
            self.raw.consume_results()
            cursor = self.raw.cursor()
            cursor.execute(syntax)
            data = cursor.fetchall()
            self.lastUsed = self.__time()
            self.idle = True
            return data

