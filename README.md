# pooledMySQL v4.0.0

```pip install pooledMySQL --upgrade```

###### <br>A well maintained program to have MySQL connection pool which auto-scales infinitely as required. This would help remove problems caused by multithreading, also removed user hassle of manually creating and deleting connections manually.


<br>To install: 
```
pip install pooledMySQL --upgrade
pip3 install pooledMySQL --upgrade
python -m pip install pooledMySQL --upgrade
python3 -m pip install pooledMySQL --upgrade
```


#### <br><br>Using this program is as simple as:
```
from pooledMySQL import Manager as MySQLManager

executorMySQL = MySQLManager("SomeUsername", "SomePassword", "DatabaseName")

listOfDict = executorMySQL.execute("SELECT * from someTable where someColumn = ?", ["someValue"])

for individualDict in listOfDict:
    print(individualDict)
```


### <br>Future implementations:
* Classes for individual tables to make reading and writing of rows way easier for the user
* Table and database creation syntaxes

###### <br>This project is always open to suggestions and feature requests.